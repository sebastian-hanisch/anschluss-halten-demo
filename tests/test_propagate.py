"""Fortpflanzung und Kosten an der von Hand gerechneten Mini-Instanz (siehe conftest.py für die Handrechnung)."""

import numpy as np
import pytest

import anh_propagate as AP
from conftest import M_MINI, PRIM_MINI

HAND = {
    (): 600, (2,): 600,
    (0,): 405, (1,): 405, (0, 1): 405,
    (0, 2): 420, (1, 2): 420, (0, 1, 2): 420,
}


@pytest.mark.parametrize("held,soll", list(HAND.items()))
def test_kosten_aller_acht_halte_mengen_stimmen_mit_der_handrechnung(mini, held, soll):
    D = AP.propagate(mini, PRIM_MINI, held)
    assert AP.total_cost(mini, D, M_MINI) == soll


def test_verspaetungen_im_detail(mini):
    # nie: B fährt pünktlich ab; c0 und c1 verpasst, c2 erreicht
    assert list(AP.propagate(mini, PRIM_MINI, ())) == [6, 4, 0, 0, 0, 0]
    # c0 gehalten: B fährt mit 4 min ab (Zubringer 0: 6 - 2), kommt mit 3 min an (Puffer 1); c2 verpasst, C fährt pünktlich
    assert list(AP.propagate(mini, PRIM_MINI, (0,))) == [6, 4, 4, 3, 0, 0]
    # zusätzlich c2: C wartet auf die 3 min Verspätung abzüglich Puffer 2, also 1 min
    assert list(AP.propagate(mini, PRIM_MINI, (0, 2))) == [6, 4, 4, 3, 1, 1]


def test_kosten_im_detail(mini):
    D = AP.propagate(mini, PRIM_MINI, (0,))
    cd, cg = AP.group_costs(mini, D, M_MINI)
    assert cd.sum() == 5 * 3 + 300 * 0                                   # direkte Gruppen
    assert list(cg) == [10 * 3, 20 * 3, 15 * M_MINI]                     # c0, c1 erreicht (min(3, 20)); c2 verpasst: 15 * 20
    assert list(AP.caught_flags(mini, D)) == [True, True, False]


def test_deckelung_min_d_m_greift(mini):
    # M = 2: wer den Anschluss erreicht, zahlt höchstens M; hier D[3] = 3 > 2
    D = AP.propagate(mini, PRIM_MINI, (0,))
    _, cg = AP.group_costs(mini, D, 2)
    assert list(cg[:2]) == [10 * 2, 20 * 2]


def test_ohne_anschluesse_keine_gruppenkosten():
    import anh_network as AN
    net = AN.assemble(3, [[], [(0, 1)], [(1, 0)]], [], [], [(2, 7)])
    D = AP.propagate(net, {0: 5}, ())
    assert list(D) == [5, 4, 4]
    assert AP.total_cost(net, D, 60) == 7 * 4


def test_erweiterung_verlust_m_plus_folgezug(mini_follow):
    net, prim = mini_follow
    assert AP.total_cost(net, AP.propagate(net, prim, ()), M_MINI, follow=True) == 900   # c0, c1 verpasst: 30 * 30 statt 30 * 20
    assert AP.total_cost(net, AP.propagate(net, prim, ()), M_MINI, follow=False) == 600
    assert AP.total_cost(net, AP.propagate(net, prim, (0,)), M_MINI, follow=True) == 1905
    assert AP.total_cost(net, AP.propagate(net, prim, (0, 2)), M_MINI, follow=True) == 420


def test_nicht_halten_ist_nie_besser_als_die_obere_schranke(mini):
    Dup = AP.propagate(mini, PRIM_MINI, range(3))
    for held in HAND:
        assert (AP.propagate(mini, PRIM_MINI, held) <= Dup).all()
    assert isinstance(Dup, np.ndarray)
