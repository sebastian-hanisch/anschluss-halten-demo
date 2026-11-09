"""Orakel-Test Delay Management: Fortpflanzung, Kosten, Regeln und Optimum gegen einen zweiten Rechenweg in reinem Python.

Der zweite Weg kennt nur die Modellbeschreibung (keine numpy-Vektoren, kein CP-SAT, keine Funktion aus anh_propagate/anh_exact):

  D[e] = max(Primärverspätung[e], max über Vorgänger s von D[s] - Puffer, max über GEHALTENE Anschlüsse c nach e von D[A_c] - Puffer_c), D >= 0
  Anschluss c erreicht  <=>  D[B_c] >= D[A_c] - Puffer_c
  Kosten = Summe direkter Gruppen w * D[Ziel] + Summe Umsteigergruppen w * (erreicht ? min(D[Ziel], V) : V),  V = M  bzw.  M + D[nächste Fahrt]

Die Aufzählung läuft über ALLE 2^k Teilmengen ALLER Anschlüsse (nicht nur der kritischen). Dazu: Ableitung der Routen gegen eine Neuherleitung mit anderer
Tie-Break-Schreibweise, und das Optimum gegen die Aufzählung auf kleinen echten Netzen. Umfang bewusst klein (Sekunden); der große Lauf (300 Netze,
15 585 Vergleiche, 0 Abweichungen) lief als Vormessung `e6_gegenprobe.py`."""

import itertools
import random

import pytest

import anh_exact as AE
import anh_network as AN
import anh_propagate as AP
import anh_rules as AR
import anh_scenario as AS
import anh_takt as AT


# ------------------------------------------------------------------ zweiter Rechenweg
def ref_delays(N, preds, conns, prim, held):
    D = [0] * N
    for e in range(N):
        v = prim.get(e, 0)
        for s, sl in preds[e]:
            v = max(v, D[s] - sl)
        for c in held:
            a, b, sl = conns[c]
            if b == e:
                v = max(v, D[a] - sl)
        D[e] = v
    return D


def ref_cost(D, conns, groups, dirs, M, nxt=None):
    tot = 0
    for e, w in dirs:
        tot += w * D[e]
    for c, (a, b, sl) in enumerate(conns):
        reached = D[b] >= D[a] - sl
        for e, w in groups[c]:
            loss = M + (D[nxt[e]] if nxt and nxt.get(e, -1) >= 0 else 0)
            tot += w * (min(D[e], loss) if reached else loss)
    return tot


def ref_rule(N, preds, conns, onb, prim, M, rule):
    """Regeln unabhängig geschrieben: Entscheidungen in Planreihenfolge, mehrere Anschlüsse eines Zuges aufsteigend nach need."""
    D = [0] * N
    for e in range(N):
        b = prim.get(e, 0)
        for s, sl in preds[e]:
            b = max(b, D[s] - sl)
        needs = sorted((D[a] - sl, c) for c, (a, bb, sl) in enumerate(conns) if bb == e)
        for need, c in needs:
            if need <= b:
                continue
            extra = need - b
            wgt = rule["w"][c]
            if rule["kind"] == "never":
                hold = False
            elif rule["kind"] == "always":
                hold = True
            elif rule["kind"] == "p":
                hold = need <= rule["W"]
            elif rule["kind"] == "c":
                hold = extra <= rule["W"]
            elif rule["kind"] == "bal":
                hold = wgt * M >= extra * (onb[e] - wgt)
            elif rule["kind"] == "bal2":
                hold = wgt * max(0, M - need) >= extra * (onb[e] - wgt)
            if hold:
                b = need
        D[e] = b
    return D


def random_mini(rng):
    N = rng.randint(7, 12)
    preds = [[] for _ in range(N)]
    for e in range(1, N):
        for s in rng.sample(range(e), min(e, rng.randint(0, 2))):
            preds[e].append((s, rng.randint(0, 4)))
    conns, seen = [], set()
    for _ in range(rng.randint(2, 6)):
        a = rng.randint(0, N - 3)
        b = rng.randint(a + 1, N - 2)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        conns.append((a, b, rng.randint(0, 4)))
    groups = [[(rng.randint(b + 1, N - 1), rng.randint(1, 30)) for _ in range(rng.randint(1, 2))] for a, b, sl in conns]
    dirs = [(rng.randint(1, N - 1), rng.randint(1, 40)) for _ in range(rng.randint(1, 4))]
    onb = [rng.randint(5, 80) for _ in range(N)]
    return N, preds, conns, groups, dirs, onb


def all_subsets_min(N, preds, conns, groups, dirs, prim, M, nxt=None):
    k = len(conns)
    best = None
    for r in range(k + 1):
        for held in itertools.combinations(range(k), r):
            c = ref_cost(ref_delays(N, preds, conns, prim, set(held)), conns, groups, dirs, M, nxt)
            best = c if best is None or c < best else best
    return best


# ------------------------------------------------------------------ Tests
def test_fortpflanzung_kosten_optimum_regeln_auf_zufalls_mini_netzen():
    rng = random.Random(20261109)
    n_nontriv = n_opt_lt_never = n_opt_lt_always = 0
    for _ in range(60):
        N, preds, conns, groups, dirs, onb = random_mini(rng)
        net = AN.assemble(N, preds, conns, groups, dirs, onb)
        cand = list(range(0, N - 2))
        for _ in range(3):
            prim = {e: rng.randint(2, 15) for e in rng.sample(cand, rng.randint(1, min(3, len(cand))))}
            for M in (5, 15, 60):
                best_ref = all_subsets_min(N, preds, conns, groups, dirs, prim, M)
                crit = AE.critical_connections(net, AE.upper_delays(net, prim))
                if crit:
                    n_nontriv += 1
                    opt = AE.solve_optimum(net, prim, M, time_limit=20)
                    assert opt.status == "OPTIMAL"
                    assert opt.cost == best_ref == AE.brute_force(net, prim, M, crit)[0]
                    assert opt.cost == ref_cost(ref_delays(N, preds, conns, prim, set(opt.held)), conns, groups, dirs, M)
                else:
                    assert best_ref == ref_cost(ref_delays(N, preds, conns, prim, set()), conns, groups, dirs, M)    # ohne kritischen Anschluss ist Halten egal
                w = [sum(x for _, x in g) for g in groups]
                for rule in [("never",), ("always",), ("p", 2), ("p", 5), ("c", 3), ("bal",), ("bal2",)]:
                    D, _ = AR.run_rule(net, prim, M, rule)
                    spec = {"kind": rule[0], "W": rule[1] if len(rule) > 1 else None, "w": w}
                    Dr = ref_rule(N, preds, conns, onb, prim, M, spec)
                    assert list(D) == Dr, (rule, prim, M)
                    assert AP.total_cost(net, D, M) == ref_cost(Dr, conns, groups, dirs, M)
                    assert AP.total_cost(net, D, M) >= best_ref                  # keine Regel schlägt das Optimum
                n_opt_lt_never += best_ref < ref_cost(ref_delays(N, preds, conns, prim, set()), conns, groups, dirs, M)
                n_opt_lt_always += best_ref < ref_cost(ref_delays(N, preds, conns, prim, set(range(len(conns)))), conns, groups, dirs, M)
    # Zweigprüfung: das Optimum ist nicht nur gleich „nie“ oder gleich „immer“
    assert n_nontriv > 100 and n_opt_lt_never > 50 and n_opt_lt_always > 20


def test_erweiterung_folgezug_verspaetet_gegen_aufzaehlung():
    rng = random.Random(7)
    n_diff_models = n_cmp = 0
    for _ in range(60):
        N, preds, conns, groups, dirs, onb = random_mini(rng)
        nxt = {}
        for g in groups:
            for e, _ in g:
                nxt[e] = rng.choice([-1, rng.randint(0, N - 1)])
        net = AN.assemble(N, preds, conns, groups, dirs, onb, nxt)
        for _ in range(2):
            prim = {e: rng.randint(2, 15) for e in rng.sample(range(N - 2), rng.randint(1, 3))}
            prim.update({e: rng.randint(0, 25) for e in rng.sample(range(N), 2)})        # auch Folgefahrten dürfen verspätet sein
            M = 15
            best = all_subsets_min(N, preds, conns, groups, dirs, prim, M, nxt)
            opt = AE.solve_optimum(net, prim, M, time_limit=20, follow=True)
            n_cmp += 1
            assert opt.proven and opt.cost == best
            assert opt.cost == ref_cost(ref_delays(N, preds, conns, prim, set(opt.held)), conns, groups, dirs, M, nxt)
            base = AE.solve_optimum(net, prim, M, time_limit=20, follow=False)
            n_diff_models += base.cost != opt.cost
    assert n_cmp == 120 and n_diff_models > 0        # die Erweiterung wirkt (kein toter Zweig)


# ------------------------------------------------------------------ echte Netze
def _real(nl, ns, seed, variant="normal", stufe="phase"):
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    return inst, demand, AN.build_event_net(inst, demand, *AT.build_takt(inst, stufe, seed), variant)


@pytest.mark.parametrize("nl,ns,seed,variant", [(3, 14, 7101, "normal"), (4, 16, 9000, "normal"), (5, 18, 9001, "knapp")])
def test_optimum_gegen_aufzaehlung_auf_kleinen_echten_netzen(nl, ns, seed, variant):
    _, _, net = _real(nl, ns, seed, variant)
    N, preds = net.N, net.preds
    conns = list(zip(net.conn_A, net.conn_B, net.conn_sl))
    dirs = [(int(e), int(w)) for e, w in zip(net.dir_e, net.dir_w)]
    n_cmp = 0
    for s in range(30):
        prim = AS.make_scenario(net, seed * 1000 + s)
        for M in (15, 60):
            crit = AE.critical_connections(net, AE.upper_delays(net, prim))
            if not crit or len(crit) > 10:
                continue
            best = min(ref_cost(ref_delays(N, preds, conns, prim, set(W)), conns, net.conn_groups, dirs, M)
                       for r in range(len(crit) + 1) for W in itertools.combinations(crit, r))
            opt = AE.solve_optimum(net, prim, M, time_limit=30)
            n_cmp += 1
            assert opt.status == "OPTIMAL" and opt.cost == best, (seed, s, M)
    assert n_cmp >= 8


def test_fortpflanzung_und_regel_p_auf_echtem_netz_gegen_zweiten_weg():
    _, _, net = _real(6, 20, 9002)
    conns = list(zip(net.conn_A, net.conn_B, net.conn_sl))
    dirs = [(int(e), int(w)) for e, w in zip(net.dir_e, net.dir_w)]
    rng = random.Random(3)
    for s in range(10):
        prim = AS.make_scenario(net, 9002 * 1000 + s)
        held = {c for c in range(net.nconn) if rng.random() < 0.3}
        D = AP.propagate(net, prim, held)
        Dr = ref_delays(net.N, net.preds, conns, prim, held)
        assert list(D) == Dr
        assert AP.total_cost(net, D, 60) == ref_cost(Dr, conns, net.conn_groups, dirs, 60)
        Dp, _ = AR.run_rule(net, prim, 60, ("p", 5))
        assert list(Dp) == ref_rule(net.N, net.preds, conns, net.onb, prim, 60, {"kind": "p", "W": 5, "w": net.conn_w})


# ------------------------------------------------------------------ Routen und Umsteigeaktivitäten
def ref_connections(lines, demand):
    """Neuherleitung: Kandidaten (Fahrzeit, la, lb, s) sammeln und lexikographisch den kleinsten nehmen (gleich dem ersten Treffer bei aufsteigender Schleife)."""
    out = {}
    n = demand.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            if demand[i][j] <= 0:
                continue
            on_i = [x for x, l in enumerate(lines) if i in l.stops]
            on_j = [x for x, l in enumerate(lines) if j in l.stops]
            if set(on_i) & set(on_j):
                continue
            cands = []
            for la in on_i:
                for lb in on_j:
                    for s in set(lines[la].stops) & set(lines[lb].stops):
                        pa, pb = lines[la].stops.index(i), lines[la].stops.index(s)
                        qa, qb = lines[lb].stops.index(s), lines[lb].stops.index(j)
                        cost = sum(lines[la].run[min(pa, pb):max(pa, pb)]) + sum(lines[lb].run[min(qa, qb):max(qa, qb)])
                        cands.append((cost, la, lb, s, pa, pb, qa, qb))
            if not cands:
                continue
            _, la, lb, s, pa, pb, qa, qb = min(cands)
            dA, dB = ("f" if pb > pa else "b"), ("f" if qb > qa else "b")
            flip = lambda d: "b" if d == "f" else "f"
            for key in ((la, dA, pb, lb, dB, qa), (lb, flip(dB), qa, la, flip(dA), pb)):
                out[key] = out.get(key, 0) + float(demand[i][j]) / 2
    return out


@pytest.mark.parametrize("nl,ns,seed", [(4, 16, 9000), (6, 20, 9002), (8, 24, 9017), (10, 20, 9027), (7, 20, 9005), (5, 20, 9012)])
def test_umsteigeaktivitaeten_gegen_neuherleitung(nl, ns, seed):
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    soll = ref_connections(inst.lines, demand)
    assert set(inst.transfers) == set(soll)
    for k, w in soll.items():
        assert inst.transfers[k] == pytest.approx(w)
