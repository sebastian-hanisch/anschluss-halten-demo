"""Netz, Routen der Fahrgäste und Ereignisnetz (Delay Management).

Netzgenerator und Linienkonstruktion: aus taktfahrplan-demo (tkt_network.py), angepasst; Ereignisnetz und Fahrgastgruppen: nach der Messreihe
`delaylib.py` (schiene-planung), angepasst und mit Präfix. Die Umsteigeaktivitäten des Takts und die Anschlüsse des Ereignisnetzes stammen aus
**einer** Ableitung (`route_pairs`, Gleichstand der Umsteigehaltestelle: kleinste Nummer). Die Vormessung fand, dass zwei getrennte Ableitungen bei
Gleichstand verschiedene Haltestellen wählen (3 von 10 Netzen); hier gibt es sie nur einmal. Zufall nur über SplitMix64.

Ereignisse tragen Planminuten; Verspätungen D[e] sind ganzzahlige Minuten gegenüber dem Plan. Aktivitäten (s -> e, Puffer) bedeuten
D[e] >= D[s] - Puffer (max-plus-Fortpflanzung).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isqrt

import numpy as np

import anh_timetable as TT
from anh_rng import SplitMix64
from anh_timetable import Instance, Line

HORIZON = 240          # Minuten, die das Ereignisnetz abdeckt
T_DEFAULT = 60
MAX_LINE_LENGTH = 6    # Halte je Linie (alle Linien haben im Ereignisnetz 6 Halte, sofern der Generator sie so lang bekommt)
VARIANTEN = {
    # run_pct: Fahrzeitzuschlag in % der Fahrzeit (Mindestfahrzeit = Plan - Zuschlag); dwell_slack: Haltezeitpuffer; turn_cap: Obergrenze der Wendepuffer
    "normal": {"run_pct": 7, "dwell_slack": 1, "turn_cap": None},
    "knapp": {"run_pct": 0, "dwell_slack": 0, "turn_cap": 10},
}


# ---------------------------------------------------------------- Netzgenerator (aus tkt_network.py)
def generate_network(n_stops: int, seed: int, hub_pct: int = 50, n_hubs: int = 2):
    """Ganzzahlige Haltestellen (Raster 5..95) und symmetrische ganzzahlige Nachfrage mit Hub-Konzentration."""
    rng = SplitMix64(seed)
    coords = np.array([[5 + rng.below(91), 5 + rng.below(91)] for _ in range(n_stops)], dtype=np.int64)
    base = [[0] * n_stops for _ in range(n_stops)]
    for i in range(n_stops):
        for j in range(i + 1, n_stops):
            base[i][j] = base[j][i] = 1 + rng.below(10)
    pool = list(range(n_stops))
    hubs = []
    for _ in range(max(1, min(n_hubs, n_stops))):
        hubs.append(pool.pop(rng.below(len(pool))))
    boost = 100 + 6 * hub_pct
    b = [boost if i in hubs else 100 for i in range(n_stops)]
    demand = np.zeros((n_stops, n_stops), dtype=np.int64)
    for i in range(n_stops):
        for j in range(n_stops):
            if i != j:
                demand[i, j] = (base[i][j] * b[i] * b[j] + 5000) // 10000
    return coords, demand, hubs


def sq_dist(coords, a: int, b: int) -> int:
    dx = int(coords[a][0]) - int(coords[b][0])
    dy = int(coords[a][1]) - int(coords[b][1])
    return dx * dx + dy * dy


def demand_greedy(coords, demand, n_lines: int, max_line_length: int) -> list:
    """Nachfrage-Greedy-Linienkonstruktion (Wachstumsbonus 2,5 = 5/2; alle Bewertungen mit 2 multipliziert, damit ganzzahlig; Gleichstand: erster Kandidat)."""
    n = len(coords)
    GROW, ONE = 5, 2
    lines, covered, network = [], set(), set()
    for line_num in range(n_lines):
        best_pair, best_score, best_pair_demand = None, -1, 0
        for i in range(n):
            for j in range(i + 1, n):
                if (i, j) in covered:
                    continue
                i_in, j_in = i in network, j in network
                if line_num > 0 and not (i_in or j_in):
                    continue
                d = int(demand[i][j])
                score = ONE * d
                if line_num > 0 and (i_in != j_in):
                    score = GROW * d
                if score > best_score:
                    best_score, best_pair, best_pair_demand = score, (i, j), d
        if best_pair is None or best_pair_demand <= 0:
            break
        line = list(best_pair)
        while len(line) < max_line_length:
            best_ext, best_ext_score = None, 0
            for cand in range(n):
                if cand in line:
                    continue
                gain = sum(int(demand[cand][s]) for s in line)
                score = gain * (GROW if cand not in network else ONE)
                if score > best_ext_score:
                    best_ext_score, best_ext = score, cand
            if best_ext is None:
                break
            if sq_dist(coords, best_ext, line[0]) <= sq_dist(coords, best_ext, line[-1]):
                line.insert(0, best_ext)
            else:
                line.append(best_ext)
        lines.append(line)
        network.update(line)
        for a in range(len(line)):
            for c in range(a + 1, len(line)):
                covered.add(tuple(sorted((line[a], line[c]))))
    while len(lines) < n_lines:
        lines.append([])
    return lines


# ---------------------------------------------------------------- die eine Ableitung der Routen
@dataclass(frozen=True)
class Route:
    """Route eines Haltestellenpaars (i < j) mit Nachfrage d: direkt auf Linie `la` oder mit einem Umstieg von `la` auf `lb` an Haltestelle `s`."""
    i: int
    j: int
    d: int
    la: int
    lb: int | None = None
    s: int | None = None

    @property
    def direct(self) -> bool:
        return self.lb is None


def route_pairs(lines: list, demand, tie_rule: str = "sortiert") -> list:
    """Je Haltestellenpaar mit Nachfrage die Route: direkt, wenn eine Linie beide bedient (kürzeste Fahrzeit, Gleichstand kleinere Liniennummer), sonst
    der Umstieg mit der kürzesten Fahrzeit über genau einen Umstieg.

    `tie_rule` regelt die Reihenfolge der gemeinsamen Haltestellen bei Gleichstand der Fahrzeit: "sortiert" (kleinste Nummer, **die** Regel dieser Demo)
    oder "menge" (Python-Mengenreihenfolge, so wie die Fall-Demo `derive_transfers` sie früher nutzte; nur für den Test, der den Unterschied zeigt)."""
    if tie_rule not in ("sortiert", "menge"):
        raise ValueError(tie_rule)
    pos = [{s: k for k, s in enumerate(l.stops)} for l in lines]
    n = demand.shape[0]
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            d = int(demand[i][j])
            if d <= 0:
                continue
            li = [x for x in range(len(lines)) if i in pos[x]]
            lj = [x for x in range(len(lines)) if j in pos[x]]
            common = set(li) & set(lj)
            if common:
                l = min(common, key=lambda x: (TT.run_between(lines[x], pos[x][i], pos[x][j]), x))
                out.append(Route(i, j, d, l))
                continue
            best = None
            for la in li:
                for lb in lj:
                    shared = set(pos[la]) & set(pos[lb])
                    for s in (sorted(shared) if tie_rule == "sortiert" else shared):
                        cost = TT.run_between(lines[la], pos[la][i], pos[la][s]) + TT.run_between(lines[lb], pos[lb][s], pos[lb][j])
                        if best is None or cost < best[0]:
                            best = (cost, la, lb, s)
            if best is None:
                continue
            _, la, lb, s = best
            out.append(Route(i, j, d, la, lb, s))
    return out


def derive_connections(lines: list, demand, tie_rule: str = "sortiert") -> dict:
    """Umsteigeaktivitäten für den Takt: (la, da, ka, lb, db, kb) -> Gewicht (Nachfrage je zur Hälfte in jede Richtung), aus `route_pairs`."""
    pos = [{s: k for k, s in enumerate(l.stops)} for l in lines]
    out = defaultdict(float)
    for r in route_pairs(lines, demand, tie_rule):
        if r.direct:
            continue
        ai, as_, bs, bj = pos[r.la][r.i], pos[r.la][r.s], pos[r.lb][r.s], pos[r.lb][r.j]
        dA, dB = TT.direction(ai, as_), TT.direction(bs, bj)
        out[(r.la, dA, as_, r.lb, dB, bs)] += r.d / 2
        out[(r.lb, TT.opposite(dB), bs, r.la, TT.opposite(dA), as_)] += r.d / 2
    return dict(out)


def build_instance(n_stops: int, n_lines: int, seed: int, T: int = T_DEFAULT, hub_pct: int = 50, tie_rule: str = "sortiert"):
    """Netz + Linien + Umsteiger für den Takt; Fahrzeit = Entfernung (isqrt, ganzzahlig) / 5 gerundet, mindestens 2 min. Rückgabe (Instance, Nachfrage, Koordinaten)."""
    coords, demand, hubs = generate_network(n_stops, seed, hub_pct)
    raw = [l for l in demand_greedy(coords, demand, n_lines, MAX_LINE_LENGTH) if len(l) >= 2]
    lines = []
    for l in raw:
        run = [max(2, (isqrt(sq_dist(coords, a, b)) + 2) // 5) for a, b in zip(l, l[1:])]
        lines.append(Line([int(x) for x in l], run))
    return Instance(T, lines, derive_connections(lines, demand, tie_rule)), demand, coords


def build_valid_instance(n_stops: int, n_lines: int, seed: int, attempts: int = 50):
    """Der erste gültige Seed ab `seed` (mindestens zwei Linien und ein Umstieg); Rückgabe (Instance, Nachfrage, Koordinaten, verwendeter Seed)."""
    for k in range(attempts):
        inst, demand, coords = build_instance(n_stops, n_lines, seed + k)
        if len(inst.lines) >= 2 and inst.transfers:
            return inst, demand, coords, seed + k
    raise ValueError(f"kein gültiger Seed ab {seed} in {attempts} Versuchen")


# ---------------------------------------------------------------- Ereignisnetz
class EventNet:
    """Ereignisnetz: Ereignisse 0..N-1 in Planreihenfolge. Alle Felder werden von `assemble` gesetzt."""


def assemble(N, preds, conns, groups, dirs, onb=None, nxt=None) -> EventNet:
    """Ereignisnetz aus Rohdaten (auch für die von Hand gerechnete Mini-Instanz der Tests).

    preds[e] = [(s, Puffer)]; conns = [(A, B, Puffer)] (Zubringer-Ankunft A, Folgezug-Abfahrt B); groups[c] = [(Zielereignis, Gewicht)];
    dirs = [(Zielereignis, Gewicht)] der Fahrgäste ohne Umstieg; onb[e] = Fahrgäste an Bord des Zuges, der bei Ereignis e abfährt;
    nxt[(Zielereignis)] = dasselbe Ereignis der nächsten Fahrt derselben Linie (Erweiterung, fehlt: keine)."""
    n = EventNet()
    n.N = N
    n.preds = preds
    n.nconn = len(conns)
    n.conn_A = [a for a, b, sl in conns]
    n.conn_B = [b for a, b, sl in conns]
    n.conn_sl = [sl for a, b, sl in conns]
    n.conn_groups = [list(g) for g in groups]
    n.conn_in = [[] for _ in range(N)]
    for c, (a, b, sl) in enumerate(conns):
        n.conn_in[b].append((c, a, sl))
    n.conn_w = [sum(w for _, w in g) for g in groups]
    n.onb = list(onb) if onb is not None else [0] * N
    dd = {}
    for e, w in dirs:
        dd[e] = dd.get(e, 0) + w
    n.dir_e = np.array(list(dd.keys()), dtype=np.int64)
    n.dir_w = np.array(list(dd.values()), dtype=np.int64)
    ge, gw, gc = [], [], []
    for c, g in enumerate(groups):
        for e, w in g:
            ge.append(e); gw.append(w); gc.append(c)
    n.g_e, n.g_w, n.g_c = np.array(ge, dtype=np.int64), np.array(gw, dtype=np.int64), np.array(gc, dtype=np.int64)
    n.cA, n.cB, n.cS = np.array(n.conn_A, dtype=np.int64), np.array(n.conn_B, dtype=np.int64), np.array(n.conn_sl, dtype=np.int64)
    qs = np.percentile(n.conn_w, [50, 75]) if n.nconn else [0, 0]
    n.theta = {50: float(qs[0]), 75: float(qs[1])}
    n.nxt_g = np.array([(nxt or {}).get(int(e), -1) for e in n.g_e], dtype=np.int64)
    n.tp, n.ev_key, n.idx, n.prim_cand, n.T, n.H, n.variant, n.lines = [0] * N, None, None, list(range(N)), T_DEFAULT, HORIZON, "mini", None
    return n


def _supp(run: int, pct: int) -> int:
    return (run * pct + 50) // 100


def build_event_net(inst: Instance, demand, offsets: list, splits: list | None = None, variant: str = "normal", H: int = HORIZON) -> EventNet:
    """Ereignisnetz des Takts: Fahren (Mindestfahrzeit = Plan - Zuschlag), Halten, Wende/Fahrzeugumlauf, Anschlüsse (Mindestumsteigezeit 3 min).

    `offsets`/`splits` sind die Ausgabe von `anh_takt.build_takt`; Fahrgastgruppen und Anschlüsse stammen aus `route_pairs` (dieselbe Ableitung wie die
    Umsteigeaktivitäten des Takts)."""
    prm = VARIANTEN[variant]
    T = inst.T
    lines = inst.lines
    nl = len(lines)
    evs, cyc = [], []
    for l, line in enumerate(lines):
        s, e = (None, 0) if splits is None else splits[l]
        ev, cycle = TT.fixed_line_times(line, T, inst.dwell, inst.tmin, offsets[l], s, e)
        assert cycle % T == 0
        evs.append(ev)
        cyc.append(cycle // T)
    raw = []
    for l in range(nl):
        for p in range(-cyc[l] - 2, H // T + 1):
            for key, t0 in evs[l].items():
                t = t0 + p * T
                if 0 <= t < H:
                    raw.append((t, l, p, key))
    raw.sort()
    idx = {(l, p, key): i for i, (t, l, p, key) in enumerate(raw)}
    N = len(raw)
    tp = [r[0] for r in raw]
    preds = [[] for _ in range(N)]

    def add(l, p1, k1, p2, k2, mindur, cap=None):
        a, b = idx.get((l, p1, k1)), idx.get((l, p2, k2))
        if a is None or b is None:
            return
        slack = tp[b] - tp[a] - mindur
        assert slack >= 0, (l, p1, k1, k2, slack)
        if cap is not None:
            slack = min(slack, cap)
        preds[b].append((a, slack))

    for l, line in enumerate(lines):
        m = len(line.stops) - 1
        c = cyc[l]
        mind_dw = inst.dwell - prm["dwell_slack"]
        for p in range(-c - 2, H // T + 1):
            for k in range(m):
                r = line.run[k]
                add(l, p, ("dep", "f", k), p, ("arr", "f", k + 1), r - _supp(r, prm["run_pct"]))
            for k in range(1, m):
                add(l, p, ("arr", "f", k), p, ("dep", "f", k), mind_dw)
            add(l, p, ("arr", "f", m), p, ("dep", "b", m), inst.tmin, prm["turn_cap"])
            for k in range(m, 0, -1):
                r = line.run[k - 1]
                add(l, p, ("dep", "b", k), p, ("arr", "b", k - 1), r - _supp(r, prm["run_pct"]))
            for k in range(m - 1, 0, -1):
                add(l, p, ("arr", "b", k), p, ("dep", "b", k), mind_dw)
            add(l, p, ("arr", "b", 0), p + c, ("dep", "f", 0), inst.tmin, prm["turn_cap"])

    # ---- Fahrgastgruppen und Anschlüsse aus den Routen
    pos = [{s: k for k, s in enumerate(l.stops)} for l in lines]
    conn_id = {}
    conn_A, conn_B, conn_sl, conn_groups = [], [], [], []
    direct = []
    onb = [0] * N

    def ride_events(d, a, b):
        if d == "f":
            return [("dep", "f", k) for k in range(a, b)]
        return [("dep", "b", k) for k in range(a, b, -1)]

    def trips_of(l):
        return range(-cyc[l] - 2, H // T + 1)

    def add_direct(l, d, pa, pb, w):
        for p in trips_of(l):
            de = idx.get((l, p, ("arr", d, pb)))
            oe = idx.get((l, p, ("dep", d, pa)))
            if de is None or oe is None:
                continue
            direct.append((de, w))
            for k in ride_events(d, pa, pb):
                e = idx.get((l, p, k))
                if e is not None:
                    onb[e] += w

    def add_transfer(la, dA, a0, as_, lb, dB, bs, bj, w):
        t0B = evs[lb][("dep", dB, bs)]
        for p in trips_of(la):
            ea = idx.get((la, p, ("arr", dA, as_)))
            eo = idx.get((la, p, ("dep", dA, a0)))
            if ea is None or eo is None:
                continue
            need = tp[ea] + inst.transfer_min
            p2 = -((t0B - need) // T)        # kleinstes p2 mit t0B + p2*T >= need
            eb = idx.get((lb, p2, ("dep", dB, bs)))
            ed = idx.get((lb, p2, ("arr", dB, bj)))
            if eb is None or ed is None:
                continue
            assert tp[eb] >= tp[ea] + inst.transfer_min
            key = (ea, eb)
            if key not in conn_id:
                conn_id[key] = len(conn_A)
                conn_A.append(ea); conn_B.append(eb); conn_sl.append(tp[eb] - tp[ea] - inst.transfer_min); conn_groups.append([])
            conn_groups[conn_id[key]].append((ed, w))
            for k in ride_events(dB, bs, bj):
                e = idx.get((lb, p2, k))
                if e is not None:
                    onb[e] += w

    for r in route_pairs(lines, demand):
        if r.direct:
            pi, pj = pos[r.la][r.i], pos[r.la][r.j]
            d1 = TT.direction(pi, pj)
            add_direct(r.la, d1, pi, pj, r.d)
            add_direct(r.la, TT.opposite(d1), pj, pi, r.d)
        else:
            ai, as_, bs, bj = pos[r.la][r.i], pos[r.la][r.s], pos[r.lb][r.s], pos[r.lb][r.j]
            dA, dB = TT.direction(ai, as_), TT.direction(bs, bj)
            add_transfer(r.la, dA, ai, as_, r.lb, dB, bs, bj, r.d)
            add_transfer(r.lb, TT.opposite(dB), bj, bs, r.la, TT.opposite(dA), as_, ai, r.d)
    conns = list(zip(conn_A, conn_B, conn_sl))
    # Erweiterung: dasselbe Zielereignis eine Periode später (nächste Fahrt derselben Linie), -1 außerhalb des Horizonts
    nxt = {}
    for c, g in enumerate(conn_groups):
        for e, _ in g:
            t, l, p, key = raw[e]
            nxt[e] = idx.get((l, p + 1, key), -1)
    net = assemble(N, preds, conns, conn_groups, direct, onb, nxt)
    net.T, net.H, net.tp, net.idx, net.ev_key, net.variant, net.lines = T, H, tp, idx, raw, variant, lines
    net.prim_cand = [i for i in range(N) if raw[i][3][0] == "dep" and tp[i] < 2 * T]
    return net


def station_of(net: EventNet, e: int) -> int:
    """Haltestelle (Index im Netz) des Ereignisses e."""
    t, l, p, key = net.ev_key[e]
    return net.lines[l].stops[key[2]]


def line_of(net: EventNet, e: int) -> int:
    return net.ev_key[e][1]
