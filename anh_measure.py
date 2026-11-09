"""Messreihe je Netz (wird von tools/build_results.py vorgerechnet; die App rechnet sie nie live).

Netze: Zufalls-Seed 9000 + i (i = 0..27), Linienzahl 4 + i % 7 (je 4 Netze für jede Linienzahl 4 bis 10), 16/20/24/20 Haltestellen je Block von sieben Netzen.
Je Netz 100 Störtage (Zufalls-Seed des Netzes * 1000 + s), 1 bis 8 Primärverspätungen von 3 bis 30 min. Ein Störtag ist die Beobachtungseinheit; ausgewiesen wird
das Netz-Mittel (Mittel über die 28 Netze, je Netz die Summe über die 100 Störtage). Das Optimum wird mit 60 s Zeitlimit gelöst; nicht bewiesene Störtage werden gezählt.
"""
from __future__ import annotations

import anh_exact as AE
import anh_network as AN
import anh_propagate as AP
import anh_rules as AR
import anh_scenario as AS
import anh_takt as AT

N_NETS = 28
N_SCEN = 100
NET_SEED0 = 9000
MS = (10, 15, 20, 30, 45, 60, 90, 120)
WS = tuple(range(1, 15))
M_MAIN = 60
RULES_MAIN = ([("never",), ("always",)] + [("p", w) for w in WS] + [("c", w) for w in (2, 3, 5, 10)]
              + [("d", 5, 50), ("d", 5, 75), ("bal",), ("bal2",)])
RULES_MKURVE = [("never",), ("always",), ("bal2",)] + [("p", w) for w in WS]
RULES_TAKT = [("never",), ("always",)] + [("p", w) for w in range(1, 11)] + [("c", 5), ("bal2",)]
TAKT_STUFEN = AT.STUFEN


def net_params(i: int) -> tuple:
    """(Linienzahl, Haltestellen, Zufalls-Seed) des i-ten Messnetzes."""
    return 4 + i % 7, (16, 20, 24, 20)[i // 7], NET_SEED0 + i


def build_measure_net(i: int, stufe: str, variant: str):
    """(Instanz, Ereignisnetz) des i-ten Messnetzes oder None, wenn es keinen Umstieg gibt."""
    nl, ns, seed = net_params(i)
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    if not inst.transfers or len(inst.lines) < 2:
        return None
    off, sp = AT.build_takt(inst, stufe, seed)
    return inst, AN.build_event_net(inst, demand, off, sp, variant)


def _scenario_costs(net, prim, M, rules, follow=False):
    return {AR.rule_name(r): AP.total_cost(net, AR.run_rule(net, prim, M, r)[0], M, follow) for r in rules}


def run_main(i: int, variant: str, n_scen: int = N_SCEN, time_limit: float = AE.MEASURE_TIME_LIMIT) -> dict | None:
    """Experiment „main“ (normale Puffer) bzw. „knapp“: M = 60, Phasen-Optimum, alle Regeln, Optimum, dazu die Erweiterung „Folgezug ebenfalls verspätet“."""
    built = build_measure_net(i, "phase", variant)
    if built is None:
        return None
    inst, net = built
    nl, ns, seed = net_params(i)
    out = {"n_lines": len(inst.lines), "n_stops": ns, "seed": seed, "N": net.N, "nconn": net.nconn,
           "ncrit": [], "status": [], "secs": [], "opt": [], "costs": {AR.rule_name(r): [] for r in RULES_MAIN},
           "ext": {"opt": [], "opt_base_decision": [], "status": [], "costs": {AR.rule_name(r): [] for r in RULES_MAIN}},
           "miss_share": float(net.g_w[net.nxt_g < 0].sum() / max(1, net.g_w.sum())) if len(net.g_w) else 0.0,
           "dprime_mean": [], "dprime_pos": []}
    for s in range(n_scen):
        prim = AS.make_scenario(net, seed * 1000 + s)
        Dup = AE.upper_delays(net, prim)
        crit = AE.critical_connections(net, Dup)
        opt = AE.solve_optimum(net, prim, M_MAIN, time_limit)
        opt_e = AE.solve_optimum(net, prim, M_MAIN, time_limit, follow=True) if crit else opt
        out["ncrit"].append(len(crit))
        out["status"].append(opt.status)
        out["secs"].append(round(opt.seconds, 4))
        out["opt"].append(opt.cost)
        for name, c in _scenario_costs(net, prim, M_MAIN, RULES_MAIN).items():
            out["costs"][name].append(c)
        out["ext"]["opt"].append(opt_e.cost)
        out["ext"]["status"].append(opt_e.status)
        out["ext"]["opt_base_decision"].append(AP.total_cost(net, AP.propagate(net, prim, opt.held), M_MAIN, True))
        for name, c in _scenario_costs(net, prim, M_MAIN, RULES_MAIN, follow=True).items():
            out["ext"]["costs"][name].append(c)
        Dn = AP.propagate(net, prim, ())
        dn = [int(Dn[n]) if n >= 0 else 0 for n in net.nxt_g]
        wsum = max(1, int(net.g_w.sum()))
        out["dprime_mean"].append(sum(int(w) * d for w, d in zip(net.g_w, dn)) / wsum)
        out["dprime_pos"].append(sum(int(w) for w, d in zip(net.g_w, dn) if d > 0) / wsum)
    return out


def run_mkurve(i: int, n_scen: int = N_SCEN, time_limit: float = AE.MEASURE_TIME_LIMIT) -> dict | None:
    """Wohin wandert das beste W? Summen über die Störtage je M: Optimum und Kosten der Regeln (normale Puffer, Phasen-Optimum)."""
    built = build_measure_net(i, "phase", "normal")
    if built is None:
        return None
    inst, net = built
    nl, ns, seed = net_params(i)
    out = {"n_lines": len(inst.lines), "M": {str(M): {"opt": 0, "costs": {AR.rule_name(r): 0 for r in RULES_MKURVE}, "n_unproven": 0, "n_crit": 0}
                                           for M in MS}}
    for s in range(n_scen):
        prim = AS.make_scenario(net, seed * 1000 + s)
        for M in MS:
            opt = AE.solve_optimum(net, prim, M, time_limit)
            cell = out["M"][str(M)]
            cell["opt"] += opt.cost
            cell["n_unproven"] += 0 if opt.proven else 1
            cell["n_crit"] += opt.status != "NOCRIT"
            for name, c in _scenario_costs(net, prim, M, RULES_MKURVE).items():
                cell["costs"][name] += c
    return out


def run_takt(i: int, n_scen: int = N_SCEN, time_limit: float = AE.MEASURE_TIME_LIMIT) -> dict | None:
    """Der Takt bestimmt die Puffer: je Takt-Stufe Plan-Umsteigezeit, Anteil knapper Anschlüsse, kritische Anschlüsse je Störtag, Regeln und Optimum (M = 60, normale Puffer)."""
    out = {}
    for stufe in TAKT_STUFEN:
        built = build_measure_net(i, stufe, "normal")
        if built is None:
            return None
        inst, net = built
        nl, ns, seed = net_params(i)
        w = [float(x) for x in net.conn_w]
        sl = list(net.conn_sl)
        wsum = sum(w)
        cell = {"n_lines": len(inst.lines), "nconn": net.nconn,
                "P": sum(wi * (s + inst.transfer_min) for wi, s in zip(w, sl)),
                "plan_wait": sum(wi * (s + inst.transfer_min) for wi, s in zip(w, sl)) / wsum,
                "share_le5": sum(wi for wi, s in zip(w, sl) if s <= 5) / wsum,
                "ncrit_sum": 0, "opt_sum": 0, "n_unproven": 0, "costs": {AR.rule_name(r): 0 for r in RULES_TAKT}}
        for s in range(n_scen):
            prim = AS.make_scenario(net, seed * 1000 + s)
            crit = AE.critical_connections(net, AE.upper_delays(net, prim))
            opt = AE.solve_optimum(net, prim, M_MAIN, time_limit)
            cell["ncrit_sum"] += len(crit)
            cell["opt_sum"] += opt.cost
            cell["n_unproven"] += 0 if opt.proven else 1
            for name, c in _scenario_costs(net, prim, M_MAIN, RULES_TAKT).items():
                cell["costs"][name] += c
        out[stufe] = cell
    return out
