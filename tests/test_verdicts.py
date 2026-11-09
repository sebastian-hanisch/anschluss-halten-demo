"""Verdikte an von Hand gesetzten Werten (DEMO-PLAYBOOK §12): jede Zahl im Text und jede Schwelle der Art steht hier.

Ein Verdikt ist eine reine Funktion (Art, Text) und bekommt Zeilen, nicht Seeds."""

import numpy as np

import anh_evaluation as ev
import anh_exact as AE


def _analysis(cost_rule, cost_opt, crit=(0, 1, 2, 3), proven=True, same=0.5, never=1100, always=1500):
    opt = AE.Optimum(cost_opt, frozenset(), "OPTIMAL" if proven else "FEASIBLE", None, 0.1)
    return ev.Analysis(None, {}, 60, False, list(crit), ("p", 5), frozenset(), opt, frozenset(), never, always, cost_rule, cost_opt, None, None, None, same if crit else None)


def test_zahlenformat_deutsch():
    assert ev.de(2.81) == "2,8" and ev.de(2.81, 2) == "2,81" and ev.de_int(1234567) == "1.234.567" and ev.de_int(999) == "999"


def test_gap_percent_hat_die_basis_optimum_und_keine_division_durch_null():
    assert ev.gap_percent(1050, 1000) == 5.0
    assert ev.gap_percent(1000, 1000) == 0.0
    assert ev.gap_percent(50, 0) is None and ev.gap_percent(50, None) is None


def test_verdict_regel_trifft_das_optimum():
    kind, text = ev.verdict_rule(_analysis(1000, 1000), "p_5")
    assert kind == "success" and "p_5 trifft hier das Optimum: 1.000 Fahrgastminuten" in text
    assert "„Nie halten“ liegt 10,0 % über dem Optimum" in text and "Bei 50 % der 4 kritischen Anschlüsse" in text


def test_verdict_regel_liegt_ueber_dem_optimum_und_nennt_die_basis():
    kind, text = ev.verdict_rule(_analysis(1234, 1000), "p_5")
    assert kind == "info" and "kostet **23,4 %** mehr als das Optimum" in text and "Basis: Optimum 1.000 Fahrgastminuten; Regel 1.234" in text


def test_verdict_ohne_kritischen_anschluss_meldet_keinen_effekt():
    kind, text = ev.verdict_rule(_analysis(500, 500, crit=()), "p_5")
    assert kind == "info" and "ist kein Anschluss kritisch" in text and "Lücke" not in text


def test_verdict_nicht_bewiesenes_optimum_wird_benannt():
    kind, text = ev.verdict_rule(_analysis(1100, 1000, proven=False), "p_5")
    assert "**nicht bewiesen**" in text and "10 s" in text
    assert "nicht bewiesen" not in ev.verdict_rule(_analysis(1100, 1000), "p_5")[1]


def test_verdict_ohne_loesung_ist_eine_warnung():
    a = _analysis(1100, 1000)
    a = ev.Analysis(**{**a.__dict__, "cost_opt": None})
    assert ev.verdict_rule(a, "p_5")[0] == "warning"


def test_verdict_optimum_null_kosten():
    kind, text = ev.verdict_rule(_analysis(0, 0), "p_5")
    assert kind == "info" and "pünktlich" in text


def test_verdict_mkurve_nennt_erstes_und_letztes_w_und_die_groesste_luecke_der_festen_schwelle():
    rows = [{"M": 10, "w_best": 1, "gap_best": (0.4, 0.1), "gap_w5": (4.2, 0.5)}, {"M": 60, "w_best": 5, "gap_best": (2.8, 0.3), "gap_w5": (2.8, 0.3)},
            {"M": 120, "w_best": 9, "gap_best": (6.5, 0.9), "gap_w5": (10.7, 1.0)}]
    kind, text = ev.verdict_mkurve(rows)
    assert kind == "info" and "von 1 min bei M = 10 auf 9 min bei M = 120" in text
    assert "bei M = 120 um 4,2 Prozentpunkte" in text           # 10,7 - 6,5 = 4,2 ist die größte Differenz (M = 10: 3,8)


def test_verdict_takt_und_bilanz():
    brutto = {"zufall": {"plan_wait": 31.2, "ncrit": 9.0}, "split": {"plan_wait": 17.9, "ncrit": 36.9}}
    netto = {"dP_pct": 42.6, "dV_pct": 47.0, "breakeven": 2.9}
    kind, text = ev.verdict_takt(brutto, netto)
    assert "von 31,2 auf 17,9 min" in text and "von 9,0 auf 36,9" in text and "−42,6 %" in text and "+47,0 %" in text and "bei 2,9 Störtagen" in text
    assert ev.breakeven_verdict(netto, 2.9)[0] == "success"          # genau der Gleichstand zählt als „zahlt sich aus“
    k2, t2 = ev.breakeven_verdict(netto, 3.0)
    assert k2 == "warning" and "Bei 3,0 Störtagen" in t2


def test_verdict_kern_nennt_basis_und_zahlen():
    s = {"best_name": "p_5", "best_gap": 2.81, "best_se": 0.34, "below_never": 10.3, "n_nets": 28, "n_scen": 100, "never_gap": 11.1, "always_gap": 72.2}
    kind, text = ev.verdict_kern(s)
    assert "28 Netze mit je 100 Störtagen" in text and "p_5" in text and "**2,8 ± 0,3 %**" in text and "10,3 %" in text and "11,1 %" in text and "72,2 %" in text
    assert "Basis: Optimum" in text and np.isfinite(s["best_gap"])


def test_mini_beispiel_der_erklaerung_hat_die_handwerte():
    assert ev.mini_costs() == {"never": 600, "c0": 405, "c0c2": 420, "opt": 405}
