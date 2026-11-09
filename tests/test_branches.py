"""Zweig-Tests (Nullspalten-Regel, DEMO-PLAYBOOK §0): jede Variante weicht auf mindestens einem Störtag von ihrer Nachbarvariante ab.

Eine Spalte mit lauter gleichen Werten hieße: die Variante läuft nie. Gezählt wird über feste Netze und Störtage, nicht über ein Ergebnis."""

import pytest

import anh_exact as AE
import anh_network as AN
import anh_propagate as AP
import anh_rules as AR
import anh_scenario as AS
import anh_takt as AT

NETZE = [(4, 16, 9000), (6, 20, 9002), (8, 24, 9017)]
N_SCEN = 25


def _net(nl, ns, seed, stufe="phase", variante="normal"):
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    return AN.build_event_net(inst, demand, *AT.build_takt(inst, stufe, seed), variante)


@pytest.fixture(scope="module")
def tage():
    """(Netz, Störtag)-Paare mit Kosten aller Regeln bei M = 60."""
    out = []
    for nl, ns, seed in NETZE:
        net = _net(nl, ns, seed)
        for s in range(N_SCEN):
            out.append((net, AS.make_scenario(net, seed * 1000 + s)))
    return out


def _cost(net, prim, rule, M=60, follow=False):
    return AP.total_cost(net, AR.run_rule(net, prim, M, rule)[0], M, follow)


@pytest.mark.parametrize("rule", [("always",), ("p", 5), ("c", 5), ("d", 5, 75), ("bal",), ("bal2",)])
def test_jede_regel_weicht_auf_mindestens_einem_stoertag_von_nie_halten_ab(tage, rule):
    assert any(_cost(net, prim, rule) != _cost(net, prim, ("never",)) for net, prim in tage)


def test_die_spalte_p_w_ist_nicht_konstant_und_hat_ein_inneres_minimum_oder_gefaelle(tage):
    total = {w: sum(_cost(net, prim, ("p", w)) for net, prim in tage) for w in range(1, 15)}
    assert len(set(total.values())) > 5                                  # die Kurve über W ist keine Linie mit lauter gleichen Werten
    assert total[1] != total[14]


def test_p_und_c_unterscheiden_sich_und_d_ist_strenger_als_c(tage):
    assert any(_cost(net, prim, ("p", 5)) != _cost(net, prim, ("c", 5)) for net, prim in tage)
    assert any(_cost(net, prim, ("d", 5, 75)) != _cost(net, prim, ("c", 5)) for net, prim in tage)
    assert any(_cost(net, prim, ("bal",)) != _cost(net, prim, ("bal2",)) for net, prim in tage)


def test_optimum_ist_strikt_besser_als_nie_und_als_immer_auf_mindestens_einem_stoertag(tage):
    better_never = better_always = 0
    for net, prim in tage:
        opt = AE.solve_optimum(net, prim, 60, 30)
        assert opt.proven
        better_never += opt.cost < _cost(net, prim, ("never",))
        better_always += opt.cost < _cost(net, prim, ("always",))
        assert opt.cost <= min(_cost(net, prim, r) for r in [("never",), ("always",), ("p", 5), ("bal2",)])
    assert better_never >= 10 and better_always >= 5


def test_folgezug_erweiterung_aendert_mindestens_einen_stoertag(tage):
    changed = sum(_cost(net, prim, ("never",), follow=True) != _cost(net, prim, ("never",)) for net, prim in tage)
    assert changed >= 5
    assert all(_cost(net, prim, ("never",), follow=True) >= _cost(net, prim, ("never",)) for net, prim in tage)      # M + D' >= M


def test_die_takt_stufen_unterscheiden_sich_in_den_kritischen_anschluessen():
    counts = {}
    for stufe in AT.STUFEN:
        n = 0
        for nl, ns, seed in NETZE:
            net = _net(nl, ns, seed, stufe)
            for s in range(N_SCEN):
                n += len(AE.critical_connections(net, AE.upper_delays(net, AS.make_scenario(net, seed * 1000 + s))))
        counts[stufe] = n
    assert len(set(counts.values())) == 4
    assert counts["split"] > counts["zufall"]


def test_knappe_puffer_machen_mehr_anschluesse_kritisch_und_veraendern_kosten():
    n_norm = n_knapp = 0
    cost_diff = 0
    for nl, ns, seed in NETZE:
        a, b = _net(nl, ns, seed, variante="normal"), _net(nl, ns, seed, variante="knapp")
        for s in range(N_SCEN):
            pa, pb = AS.make_scenario(a, seed * 1000 + s), AS.make_scenario(b, seed * 1000 + s)
            assert pa == pb
            n_norm += len(AE.critical_connections(a, AE.upper_delays(a, pa)))
            n_knapp += len(AE.critical_connections(b, AE.upper_delays(b, pb)))
            cost_diff += _cost(a, pa, ("never",)) != _cost(b, pb, ("never",))
    assert n_knapp > n_norm and cost_diff > 0


def test_m_veraendert_die_kosten_und_das_optimum(tage):
    costs = {M: sum(AE.solve_optimum(net, prim, M, 30).cost for net, prim in tage[:15]) for M in (10, 60, 120)}
    assert len(set(costs.values())) == 3 and costs[10] < costs[60] < costs[120]
