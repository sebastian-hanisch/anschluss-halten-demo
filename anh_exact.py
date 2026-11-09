"""Das Optimum: eine binäre Variable je kritischem Anschluss (CP-SAT), und die Vollaufzählung als Gegenprobe.

nach der Messreihe `delaylib.solve_opt` und `e6_folgezug.solve_opt_ext` (schiene-planung, fahrplan-planung), angepasst: ein Aufruf für Grundmodell und Erweiterung,
Ergebnis als Datensatz mit Status und unterer Schranke. Das Optimum sieht den ganzen Störtag im Voraus; es ist der Maßstab, kein online umsetzbares Verfahren.
Ein Anschluss ist **kritisch**, wenn die Verspätung des Zubringers (bei „immer halten“, dem Maximum aller Entscheidungen) seinen Puffer übersteigt.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from anh_propagate import propagate, total_cost

LIVE_TIME_LIMIT = 10.0       # Sekunden je Störtag in der App; bei Überschreitung gilt „nicht bewiesen“
MEASURE_TIME_LIMIT = 60.0    # Sekunden je Störtag in der vorgerechneten Messreihe


@dataclass(frozen=True)
class Optimum:
    cost: int | None          # Kosten der besten gefundenen Entscheidung, nachgerechnet per Fortpflanzung (None: keine Lösung gefunden)
    held: frozenset           # gehaltene kritische Anschlüsse
    status: str               # OPTIMAL, FEASIBLE (nicht bewiesen), NOCRIT (nichts zu entscheiden)
    bound: float | None       # untere Schranke des Lösers
    seconds: float

    @property
    def proven(self) -> bool:
        return self.status in ("OPTIMAL", "NOCRIT")


def upper_delays(net, prim: dict):
    """Verspätungen bei „immer halten“: obere Schranke jeder Entscheidung (die Fortpflanzung ist monoton)."""
    return propagate(net, prim, range(net.nconn))


def critical_connections(net, Dup) -> list:
    """Anschlüsse, deren Zubringer bei „immer halten“ über den Puffer hinaus verspätet ist."""
    return [c for c in range(net.nconn) if Dup[net.conn_A[c]] > net.conn_sl[c]]


def solve_optimum(net, prim: dict, M: int, time_limit: float = LIVE_TIME_LIMIT, workers: int = 1, follow: bool = False) -> Optimum:
    """Optimale Menge gehaltener Anschlüsse. `follow`: Verlust beim Verpassen M + D' statt M (Erweiterung „Folgezug ebenfalls verspätet“)."""
    t0 = time.perf_counter()
    Dup = upper_delays(net, prim)
    crit = critical_connections(net, Dup)
    if not crit:
        return Optimum(total_cost(net, propagate(net, prim, ()), M, follow), frozenset(), "NOCRIT", None, time.perf_counter() - t0)
    N = net.N
    R = [e for e in range(N) if Dup[e] > 0]
    Rs = set(R)
    m = cp_model.CpModel()
    Dv = {e: m.NewIntVar(prim.get(e, 0), int(Dup[e]), f"D{e}") for e in R}
    for e in R:
        for s, sl in net.preds[e]:
            if s in Rs and Dup[s] - sl > prim.get(e, 0):
                m.Add(Dv[e] >= Dv[s] - sl)
    obj = []
    for e, w in zip(net.dir_e, net.dir_w):
        if int(e) in Rs:
            obj.append(int(w) * Dv[int(e)])
    ys = {}
    nxt_of = {int(e): int(n) for e, n in zip(net.g_e, net.nxt_g)}
    for c in range(net.nconn):
        a, b, sl = net.conn_A[c], net.conn_B[c], net.conn_sl[c]
        y = None
        if Dup[a] > sl:
            y = m.NewBoolVar(f"y{c}")
            ys[c] = y
            m.Add(Dv[b] >= Dv[a] - sl).OnlyEnforceIf(y)
        for de, w in net.conn_groups[c]:
            de2 = nxt_of.get(de, -1) if follow else -1
            dn_up = int(Dup[de2]) if (de2 >= 0 and de2 in Rs) else 0
            dn = Dv[de2] if dn_up > 0 else 0
            big = Dup[de] > M          # nur dann kann die Deckelung min(D, Verlust) greifen
            if y is None and not big:
                if de in Rs:
                    obj.append(w * Dv[de])
                continue
            u = m.NewIntVar(0, max(M + dn_up, int(Dup[de])), f"u{c}_{de}")
            if y is not None:
                m.Add(u >= M + dn).OnlyEnforceIf(y.Not())
            z = m.NewBoolVar(f"z{c}_{de}") if big else None     # z: Fahrgast nimmt den Folgezug trotz erreichtem Anschluss
            if z is not None:
                m.Add(u >= M + dn).OnlyEnforceIf(z)
            if de in Rs:
                cond = ([y] if y is not None else []) + ([z.Not()] if z is not None else [])
                if cond:
                    m.Add(u >= Dv[de]).OnlyEnforceIf(cond)
                else:
                    m.Add(u >= Dv[de])
            obj.append(w * u)
    m.Minimize(sum(obj) if obj else 0)
    s = cp_model.CpSolver()
    s.parameters.num_workers = workers
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.random_seed = 1
    st = s.Solve(m)
    status = s.StatusName(st)
    secs = time.perf_counter() - t0
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Optimum(None, frozenset(), status, None, secs)
    held = frozenset(c for c, y in ys.items() if s.Value(y) == 1)
    cost = total_cost(net, propagate(net, prim, held), M, follow)    # nachgerechnet per Fortpflanzung, nicht der Modellwert
    return Optimum(cost, held, status, s.BestObjectiveBound(), secs)


def brute_force(net, prim: dict, M: int, crit: list, follow: bool = False):
    """Minimum über alle Teilmengen der kritischen Anschlüsse (Kosten per Fortpflanzung). Rückgabe (Kosten, Menge); nur für kleine Fälle."""
    best, best_w = None, None
    k = len(crit)
    for mask in range(1 << k):
        w = frozenset(crit[i] for i in range(k) if mask >> i & 1)
        c = total_cost(net, propagate(net, prim, w), M, follow)
        if best is None or c < best:
            best, best_w = c, w
    return best, best_w
