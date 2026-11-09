"""Regeln: reine Entscheidungsfunktion und Durchlauf an der Mini-Instanz (Handrechnung in conftest.py)."""

import pytest

import anh_propagate as AP
import anh_rules as AR
from conftest import M_MINI, PRIM_MINI

THETA = {50: 5.0, 75: 20.0}


def d(rule, need, extra, w=10, onb=35, M=20):
    return AR.decide(rule, need, extra, w, onb, M, THETA)


def test_nie_und_immer():
    assert d(("never",), 1, 1) is False
    assert d(("always",), 99, 99) is True


def test_c_und_p_pruefen_verschiedene_groessen():
    assert d(("c", 5), need=9, extra=5) is True and d(("c", 5), need=9, extra=6) is False        # c prüft extra, Grenze inklusive
    assert d(("p", 5), need=5, extra=5) is True and d(("p", 5), need=6, extra=1) is False         # p prüft need, nicht extra


def test_d_verlangt_das_gewicht_des_quantils():
    assert d(("d", 5, 75), 3, 3, w=20) is True and d(("d", 5, 75), 3, 3, w=19) is False          # Schwelle inklusive
    assert d(("d", 5, 50), 3, 3, w=5) is True
    assert d(("d", 5, 75), 6, 6, w=20) is False                                                    # zu lange Wartezeit


def test_bal_gegenrechnung_im_eigenen_zug():
    # Gewicht 10, an Bord 35: 10 * M = 200 gegen extra * 25
    assert d(("bal",), 8, 8) is True                                                              # 200 >= 200
    assert d(("bal",), 9, 9) is False                                                             # 200 < 225


def test_bal2_zieht_die_schon_angenommene_verspaetung_vom_verlust_ab():
    assert d(("bal2",), need=4, extra=4) is True                                                  # 10 * 16 = 160 >= 4 * 25 = 100
    assert d(("bal2",), need=19, extra=1) is False                                                # 10 * 1 = 10 < 1 * 25
    assert d(("bal2",), need=25, extra=1) is False                                                # Verlust ist nie negativ: max(0, M - need)


def test_rule_name_und_parse_rule_sind_umkehrungen():
    for rule in [("never",), ("always",), ("bal",), ("bal2",), ("p", 5), ("c", 12), ("d", 5, 75)]:
        assert AR.parse_rule(AR.rule_name(rule)) == rule
    assert AR.rule_name(("d", 5, 75)) == "d5_75"


def test_unbekannte_regel_wird_abgelehnt():
    with pytest.raises(ValueError):
        d(("zufall",), 1, 1)


HAND = {("never",): 600, ("always",): 420, ("p", 5): 420, ("p", 0): 600, ("bal2",): 405, ("c", 5): 420}


@pytest.mark.parametrize("rule,soll", list(HAND.items()), ids=[AR.rule_name(r) for r in HAND])
def test_regeln_auf_der_mini_instanz(mini, rule, soll):
    D, _ = AR.run_rule(mini, PRIM_MINI, M_MINI, rule)
    assert AP.total_cost(mini, D, M_MINI) == soll


def test_gehaltene_mengen_der_regeln(mini):
    # p5: c0 (need 4) und c2 (need 1) werden gehalten; c1 (need 4) ist dann schon abgedeckt, weil B mit 4 min abfährt
    assert AR.run_rule(mini, PRIM_MINI, M_MINI, ("p", 5))[1] == {0, 2}
    # bal2: c0: 10 * (20 - 4) = 160 >= 4 * (35 - 10) = 100 halten; c2: 15 * (20 - 1) = 285 < 1 * (315 - 15) = 300 nicht halten
    assert AR.run_rule(mini, PRIM_MINI, M_MINI, ("bal2",))[1] == {0}
    assert AR.run_rule(mini, PRIM_MINI, M_MINI, ("never",))[1] == set()


def test_durchlauf_mit_regel_ist_gleich_der_fortpflanzung_mit_ihrer_menge(mini):
    for rule in HAND:
        D, held = AR.run_rule(mini, PRIM_MINI, M_MINI, rule)
        assert list(D) == list(AP.propagate(mini, PRIM_MINI, held))
