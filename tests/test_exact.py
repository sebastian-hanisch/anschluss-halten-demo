"""Das Optimum an der Mini-Instanz (Handrechnung in conftest.py) und Randfälle."""

import anh_exact as AE
import anh_propagate as AP
from conftest import M_MINI, PRIM_MINI


def test_kritische_anschluesse_der_mini_instanz(mini):
    Dup = AE.upper_delays(mini, PRIM_MINI)
    assert list(Dup) == [6, 4, 4, 3, 1, 1]
    assert AE.critical_connections(mini, Dup) == [0, 1, 2]       # 6 > 2, 4 > 0, 3 > 2


def test_optimum_405_und_aufzaehlung_stimmen_mit_der_handrechnung(mini):
    opt = AE.solve_optimum(mini, PRIM_MINI, M_MINI, time_limit=10)
    assert opt.status == "OPTIMAL" and opt.proven and opt.cost == 405
    assert opt.held in (frozenset({0}), frozenset({1}), frozenset({0, 1}))   # c2 halten kostet 15 mehr
    best, held = AE.brute_force(mini, PRIM_MINI, M_MINI, [0, 1, 2])
    assert best == 405 and held == frozenset({0})


def test_aufzaehlung_waehlt_bei_gleichstand_die_kleinste_maske(mini):
    # Masken werden aufsteigend durchlaufen, ein Gleichstand ersetzt nicht: erste Menge mit 405 ist {c0} (Maske 1)
    assert AE.brute_force(mini, PRIM_MINI, M_MINI, [0, 1, 2]) == (405, frozenset({0}))


def test_ohne_kritischen_anschluss_ist_nichts_zu_entscheiden(mini):
    opt = AE.solve_optimum(mini, {}, M_MINI)
    assert opt.status == "NOCRIT" and opt.proven and opt.held == frozenset() and opt.cost == 0 and opt.bound is None


def test_erweiterung_aendert_die_entscheidung_von_hand(mini_follow):
    net, prim = mini_follow
    base = AE.solve_optimum(net, prim, M_MINI, follow=False)
    ext = AE.solve_optimum(net, prim, M_MINI, follow=True)
    assert base.cost == 405 and 2 not in base.held                # Grundmodell: c2 nicht halten
    assert ext.cost == 420 and 2 in ext.held                      # Erweiterung: das Verpassen von c2 kostet 15 * 120, also halten
    assert ext.status == base.status == "OPTIMAL"
    assert AE.brute_force(net, prim, M_MINI, [0, 1, 2], follow=True)[0] == 420
    # die Entscheidung des Grundmodells ist im erweiterten Modell schlechter (1905 gegen 420)
    assert AP.total_cost(net, AP.propagate(net, prim, base.held), M_MINI, follow=True) > 420


def test_zeitlimit_null_liefert_keine_falsche_beweisaussage(mini):
    opt = AE.solve_optimum(mini, PRIM_MINI, M_MINI, time_limit=1e-9)
    # entweder noch nichts gefunden oder eine zulässige Lösung ohne Beweis oder (bei winziger Instanz) schon bewiesen; nie ein Kostenwert unter dem Optimum
    assert opt.cost is None or opt.cost >= 405
    assert opt.status in ("UNKNOWN", "FEASIBLE", "OPTIMAL")
