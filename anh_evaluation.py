"""Live-Rechnung eines Störtags, Kennzahlen und Verdikte (reine Funktionen: Art, Text).

Ein Störtag auf dem gewählten Netz: Takt-Stufe aufbauen, Ereignisnetz bauen, Primärverspätungen setzen, die gewählte Regel und das Optimum (CP-SAT mit
Zeitlimit) rechnen. Alle Prozentzahlen nennen ihre Basis. Die vorgerechneten Experimente stehen in `anh_results.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import anh_constants as C
import anh_exact as AE
import anh_network as AN
import anh_propagate as AP
import anh_rules as AR
import anh_scenario as AS
import anh_takt as AT


@dataclass(frozen=True, kw_only=True)
class Settings:
    lines: int = C.DEFAULT_LINES
    stufe: str = C.DEFAULT_STUFE
    puffer: str = C.DEFAULT_PUFFER
    M: int = C.DEFAULT_M
    k: int = C.DEFAULT_K
    hmax: int = C.DEFAULT_HMAX
    rule: str = C.DEFAULT_RULE
    W: int = C.DEFAULT_W
    folgezug: bool = False
    net_seed: int = C.DEFAULT_NET_SEED
    scen_seed: int = C.DEFAULT_SCEN_SEED

    @property
    def net_key(self) -> tuple:
        return (self.lines, self.stufe, self.puffer, self.net_seed)


def rule_tuple(rule: str, W: int) -> tuple:
    """Regel-Tupel aus Auswahl und Schwelle: d_W nutzt das 75-Prozent-Quantil des Umsteigergewichts."""
    if rule in ("never", "always", "bal", "bal2"):
        return (rule,)
    if rule == "d":
        return ("d", W, 75)
    return (rule, W)


def rule_label(rule: str, W: int) -> str:
    return {"never": "nie halten", "always": "immer halten", "c": f"c_{W}", "p": f"p_{W}", "d": f"d_{W}", "bal": "Gegenrechnung", "bal2": "Gegenrechnung (verfeinert)"}[rule]


@dataclass(frozen=True)
class Network:
    inst: object
    net: object
    seed_used: int            # tatsächlich verwendeter Seed (der erste gültige ab dem gewählten)
    n_lines: int              # Linien, die der Generator wirklich gebaut hat


def build_network(lines: int, stufe: str, puffer: str, net_seed: int) -> Network:
    inst, demand, _, used = AN.build_valid_instance(C.N_STOPS, lines, net_seed)
    off, sp = AT.build_takt(inst, stufe, used)
    return Network(inst, AN.build_event_net(inst, demand, off, sp, puffer), used, len(inst.lines))


@dataclass(frozen=True)
class Analysis:
    network: Network
    prim: dict
    M: int
    follow: bool
    crit: list                # kritische Anschlüsse
    rule: tuple
    rule_held: frozenset      # tatsächlich gehaltene Anschlüsse der Regel (nur solche, bei denen das Halten den Folgezug wirklich verspätet)
    opt: AE.Optimum
    opt_held: frozenset       # tatsächlich gehaltene Anschlüsse des Optimums (Anschlüsse, deren Halten nichts ändert, zählen nicht)
    cost_never: int
    cost_always: int
    cost_rule: int
    cost_opt: int | None
    D_rule: object
    D_opt: object
    D_never: object
    same_share: float | None  # Anteil der kritischen Anschlüsse mit gleicher Entscheidung von Regel und Optimum (einfach gezählt; „gehalten“ heißt: der Folgezug wartet tatsächlich)

    @property
    def gap_pct(self) -> float | None:
        """Regel gegenüber dem Optimum in Prozent der Optimumskosten."""
        return gap_percent(self.cost_rule, self.cost_opt)


def gap_percent(cost: float, reference: float | None) -> float | None:
    """Abstand in Prozent der Referenz (Optimum); ohne Referenz oder bei Referenz 0 gibt es keinen Abstand."""
    if reference is None or reference <= 0:
        return None
    return 100.0 * (cost - reference) / reference


def effective_holds(net, prim: dict, held) -> set:
    """Von den Anschlüssen in `held` diejenigen, bei denen der Folgezug tatsächlich wartet (need > b zum Zeitpunkt der Entscheidung, aufsteigend nach need wie in `run_rule`).

    Ein Optimum kann Anschlüsse „halten“, deren Halten nichts verspätet (beliebige Wahl bei Gleichstand); für Vergleich und Anzeige zählen nur wirksame Halte."""
    held = set(held)
    D = [0] * net.N
    eff = set()
    for e in range(net.N):
        b = prim.get(e, 0)
        for s, sl in net.preds[e]:
            b = max(b, D[s] - sl)
        for need, cid in sorted((D[a] - sl, c) for c, a, sl in net.conn_in[e]):
            if cid in held and need > b:
                eff.add(cid)
                b = need
        D[e] = b
    return eff


def analyse(settings: Settings, network: Network, time_limit: float = C.LIVE_TIME_LIMIT) -> Analysis:
    net = network.net
    prim = AS.make_scenario(net, settings.scen_seed, kmin=settings.k, kspan=1, hmin=min(3, settings.hmax), hmax=settings.hmax)
    follow = settings.folgezug
    Dup = AE.upper_delays(net, prim)
    crit = AE.critical_connections(net, Dup)
    rule = rule_tuple(settings.rule, settings.W)
    D_rule, held = AR.run_rule(net, prim, settings.M, rule)
    D_never = AP.propagate(net, prim, ())
    opt = AE.solve_optimum(net, prim, settings.M, time_limit, follow=follow)
    D_opt = AP.propagate(net, prim, opt.held)
    opt_held = effective_holds(net, prim, opt.held)
    cost_opt = opt.cost
    same = None
    if crit:
        same = sum(1 for c in crit if (c in held) == (c in opt_held)) / len(crit)
    return Analysis(network, prim, settings.M, follow, crit, rule, frozenset(held), opt, frozenset(opt_held),
                    AP.total_cost(net, D_never, settings.M, follow), AP.total_cost(net, AP.propagate(net, prim, range(net.nconn)), settings.M, follow),
                    AP.total_cost(net, D_rule, settings.M, follow), cost_opt, D_rule, D_opt, D_never, same)


# ---------------------------------------------------------------- Zeilen für Tabelle und Zeitdiagramm
def connection_rows(a: Analysis, limit: int = 30) -> list:
    """Kritische Anschlüsse mit Plan- und Ist-Zeiten unter Regel und Optimum, absteigend nach Umsteigegewicht (höchstens `limit`)."""
    net = a.network.net
    rows = []
    for c in a.crit:
        A, B = net.conn_A[c], net.conn_B[c]
        rows.append({
            "c": c, "station": AN.station_of(net, A), "line_a": AN.line_of(net, A) + 1, "line_b": AN.line_of(net, B) + 1, "weight": net.conn_w[c],
            "buffer": net.conn_sl[c], "plan_arr": net.tp[A], "plan_dep": net.tp[B],
            "arr_delay": int(a.D_rule[A]), "dep_delay_rule": int(a.D_rule[B]), "dep_delay_opt": int(a.D_opt[B]),
            "hold_rule": c in a.rule_held, "hold_opt": c in a.opt_held,
            "caught_rule": bool(a.D_rule[B] >= a.D_rule[A] - net.conn_sl[c]), "caught_opt": bool(a.D_opt[B] >= a.D_opt[A] - net.conn_sl[c]),
        })
    rows.sort(key=lambda r: (-r["weight"], r["plan_arr"], r["c"]))
    return rows[:limit]


# ---------------------------------------------------------------- Zahlenformat (deutsches Dezimalkomma, Tausenderpunkt)
def de(x: float, digits: int = 1) -> str:
    """Zahl mit Dezimalkomma."""
    return f"{x:.{digits}f}".replace(".", ",")


def de_int(n: int) -> str:
    """Ganzzahl mit Tausenderpunkt."""
    return f"{int(n):,}".replace(",", ".")


# ---------------------------------------------------------------- Verdikte
def verdict_rule(a: Analysis, label: str) -> tuple[str, str]:
    """Verdikt der Kernfrage: wie gut trifft die gewählte Regel das Optimum auf diesem Störtag? Basis jeder Prozentzahl: Kosten des Optimums."""
    if not a.crit:
        return "info", ("Auf diesem Störtag ist kein Anschluss kritisch (kein Zubringer ist über den Puffer hinaus verspätet): Es gibt nichts zu entscheiden, "
                        "alle Regeln und das Optimum kosten gleich viel.")
    if a.cost_opt is None:
        return "warning", f"In {C.LIVE_TIME_LIMIT:.0f} s wurde keine Lösung gefunden; ein Vergleich mit dem Optimum ist nicht möglich."
    proof = "" if a.opt.proven else (f" Das Optimum ist **nicht bewiesen** (Zeitlimit {C.LIVE_TIME_LIMIT:.0f} s): Es ist die beste gefundene Entscheidung, "
                                     "die Lücke zum Beweis bleibt offen.")
    if a.cost_opt <= 0:
        return "info", f"Alle Fahrgäste kommen pünktlich an (Kosten 0); kein Vergleich nötig.{proof}"
    gap = gap_percent(a.cost_rule, a.cost_opt)
    never = gap_percent(a.cost_never, a.cost_opt)
    if gap <= 1e-9:
        kind, head = "success", f"Die Regel {label} trifft hier das Optimum: {de_int(a.cost_rule)} Fahrgastminuten."
    else:
        kind, head = "info", (f"Die Regel {label} kostet **{de(gap)} %** mehr als das Optimum "
                              f"(Basis: Optimum {de_int(a.cost_opt)} Fahrgastminuten; Regel {de_int(a.cost_rule)}).")
    tail = f" „Nie halten“ liegt {de(never)} % über dem Optimum."
    same = f" Bei {de(a.same_share * 100, 0)} % der {len(a.crit)} kritischen Anschlüsse entscheidet die Regel wie das Optimum."
    return kind, head + tail + same + proof


def verdict_mkurve(rows: list) -> tuple[str, str]:
    """Verdikt E1: Wanderung des besten W mit M (Zeilen aus `anh_results.mkurve_rows`)."""
    first, last = rows[0], rows[-1]
    worst = max(rows, key=lambda r: r["gap_w5"][0] - r["gap_best"][0])
    cost = worst["gap_w5"][0] - worst["gap_best"][0]
    return "info", (f"Das beste W steigt von {first['w_best']} min bei M = {first['M']} auf {last['w_best']} min bei M = {last['M']}. "
                    f"Eine feste Schwelle W = 5 liegt bei M = {worst['M']} um {de(cost)} Prozentpunkte über dem besten W (Abstand zum Optimum, Netz-Mittel).")


def verdict_takt(brutto: dict, netto: dict) -> tuple[str, str]:
    """Verdikt E2: der bessere Takt (Aufteilung) lässt mehr Anschlüsse kritisch werden; `brutto` = Zeilen je Stufe, `netto` = Rechnung zufällige Phasen -> Phasen + Aufteilung."""
    z, s = brutto["zufall"], brutto["split"]
    return "info", (f"Von zufälligen Phasen zu Phasen + Aufteilung sinkt die Plan-Umsteigezeit von {de(z['plan_wait'])} auf {de(s['plan_wait'])} min je Umsteiger, "
                    f"die kritischen Anschlüsse je Störtag steigen von {de(z['ncrit'])} auf {de(s['ncrit'])}. Gesamtbilanz je Horizont (Einheit Gewicht mal Minuten, "
                    f"Basis: zufällige Phasen): Plan-Umsteigezeit −{de(netto['dP_pct'])} %, Verspätungskosten je Störtag +{de(netto['dV_pct'])} %; "
                    f"Gleichstand bei {de(netto['breakeven'])} Störtagen je Horizont.")


def breakeven_verdict(netto: dict, f: float) -> tuple[str, str]:
    """Bei f Störtagen je Horizont: lohnt sich der bessere Takt? Gesamtkosten = P + f · V (Einheit Gewicht · Minuten)."""
    if f > netto["breakeven"]:
        return "warning", f"Bei {de(f)} Störtagen je Horizont ist der bessere Takt insgesamt teurer: Die Mehrkosten durch Verspätung überwiegen den Gewinn an Plan-Umsteigezeit."
    return "success", f"Bei {de(f)} Störtagen je Horizont zahlt sich der bessere Takt aus: Der Gewinn an Plan-Umsteigezeit überwiegt die Mehrkosten durch Verspätung."


# ---------------------------------------------------------------- Mini-Instanz der Erklärung (dieselbe wie in tests/conftest.py, dort von Hand gerechnet)
MINI_M = 20
MINI_PRIM = {0: 6, 1: 4}


def mini_example():
    """Das von Hand gerechnete Mini-Ereignisnetz aus der Erklärung (6 Ereignisse, 3 Anschlüsse)."""
    return AN.assemble(6, [[], [], [], [(2, 1)], [], [(4, 0)]], [(0, 2, 2), (1, 2, 0), (3, 4, 2)], [[(3, 10)], [(3, 20)], [(5, 15)]], [(3, 5), (5, 300)],
                       [0, 0, 35, 0, 315, 0])


def mini_costs() -> dict:
    """Kosten der Mini-Instanz für die Erklärung: nie, c0 gehalten, c0 und c2 gehalten, Optimum (Fahrgastminuten, M = 20)."""
    net = mini_example()
    cost = lambda held: AP.total_cost(net, AP.propagate(net, MINI_PRIM, held), MINI_M)
    return {"never": cost(()), "c0": cost((0,)), "c0c2": cost((0, 2)), "opt": AE.solve_optimum(net, MINI_PRIM, MINI_M).cost}


def verdict_kern(res_stats: dict) -> tuple[str, str]:
    """Verdikt der Kernfrage über die Messreihe: `res_stats` mit den Schlüsseln best_name, best_gap, best_se, below_never, n_nets, n_scen, never_gap, always_gap, bal2_gap."""
    s = res_stats
    return "info", (f"Über {s['n_nets']} Netze mit je {s['n_scen']} Störtagen (normale Puffer, M = 60) liegt die beste feste Regel im Rückblick ({s['best_name']}) im Netz-Mittel "
                    f"**{de(s['best_gap'])} ± {de(s['best_se'])} %** über dem bewiesenen Optimum (Basis: Optimum; Mittel ± Standardfehler über die Netze). Das Optimum liegt "
                    f"{de(s['below_never'])} % unter „nie halten“ (Basis: „nie halten“), „nie halten“ selbst {de(s['never_gap'])} % über dem Optimum, „immer halten“ {de(s['always_gap'])} %. "
                    "Die Schwelle der Regel ist dabei im Rückblick gewählt; wie sie von M abhängt, zeigt E1.")
