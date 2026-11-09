"""Jede Zahl der README und der Pflichttexte der App wird hier aus der vorgerechneten Messreihe nachgerechnet (DEMO-PLAYBOOK §4 und §11a).

Die Zeichenketten werden mit denselben Auswertungsfunktionen wie in der App aus `data/anh_results.json` gebildet und müssen wörtlich in der README stehen (Dezimalkomma,
eine Nachkommastelle, Prozentzahlen mit genannter Basis). Urteilswörter („ja“, „nicht trennbar“, „nicht streng monoton“) sind als Zählung oder Vergleich geprüft."""

from pathlib import Path

import numpy as np
import pytest

import anh_constants as C
import anh_evaluation as ev
import anh_results as R
from anh_evaluation import de

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def res():
    return R.load_results()


def pm(pair, d=1):
    return f"{de(pair[0], d)} ± {de(pair[1], d)}"


def sp(n):
    """Tausendertrennung mit Leerzeichen, so wie die README sie schreibt."""
    return f"{n:,}".replace(",", " ")


def has(snippet):
    assert snippet in README, snippet


def _avg_ranks(v):
    """Ränge mit Mittelung bei Gleichstand (die Linienzahl hat je 4 gleiche Werte)."""
    v = np.asarray(v, float)
    order = np.argsort(v, kind="stable")
    ranks = np.empty(len(v))
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2
        i = j + 1
    return ranks


def rank_corr(x, y):
    """Spearman-Rangkorrelation mit mittleren Rängen."""
    return float(np.corrcoef(_avg_ranks(x), _avg_ranks(y))[0, 1])


# ------------------------------------------------------------------ H1
def test_h1_beste_feste_regel_zwei_bis_vier_prozent_ueber_dem_optimum(res):
    name_n, gap_n, se_n = R.best_rule_overall(res, "main")
    name_k, gap_k, se_k = R.best_rule_overall(res, "knapp")
    assert (name_n, name_k) == ("p5", "p3")
    assert 2 <= gap_n <= 4 and 2 <= gap_k <= 4
    has(f"`p_5` liegt {pm((gap_n, se_n))} % über dem Optimum")
    # E3-Text der App nennt dieselbe gemessene Zahl statt „wenige Prozent“
    assert f"(`p_5`, normale Puffer) {pm((gap_n, se_n))} % über dem Optimum (28 Netze" in (ROOT / "app.py").read_text(encoding="utf-8")
    has(f"bei knappen Puffern `p_3` {pm((gap_k, se_k))} %")
    nd, nok, nopen = R.proven_counts(res, "main")
    kd, kok, kopen = R.proven_counts(res, "knapp")
    has(f"({sp(nok)} von {sp(nd)} Störtagen mit Entscheidung bewiesen)")
    has(f"({sp(kok)} von {sp(kd)} bewiesen)")
    has(f"Das Optimum liegt {de(R.opt_below_never(res, 'main'))} % unter „nie halten“ (Basis: „nie halten“), bei knappen Puffern {de(R.opt_below_never(res, 'knapp'))} %")
    assert (nopen, kopen) == (0, 1)
    by_lines = [np.mean(R.gap_per_net(res, "main", "p5", n_lines=l)) for l in R.lines_of(res, "main")]
    has(f"je Linienzahl {de(min(by_lines))} bis {de(max(by_lines))} %")
    assert C.K_MAX == 16 and "Reglermaximum von 16 Primärverspätungen" in README
    has(f"bei normalen Puffern kein Störtag nach 60 s unbewiesen, bei knappen Puffern einer von {sp(kd)}")


def test_basis_der_prozentzahl_dieses_laufs(res):
    has(f"dieser Lauf {de(R.opt_below_never(res, 'main'))} %")
    has("2 800 Störtage je Experiment")
    assert len([r for r in res["main"] if r]) * res["meta"]["N_SCEN"] == 2800
    assert res["meta"]["net_seeds"][0] == 9000 and res["meta"]["net_seeds"][-1] == 9027
    has("Zufalls-Seed 9000 bis 9027")


# ------------------------------------------------------------------ H2
def test_h2_bestes_w_wandert_mit_m(res):
    rows = R.mkurve_rows(res)
    ws = [r["w_best"] for r in rows]
    assert [r["M"] for r in rows] == [10, 15, 20, 30, 45, 60, 90, 120]
    assert ws == sorted(ws) and ws[0] < ws[-1]
    has("für M = 10, 15, 20, 30, 45, 60, 90, 120: " + ", ".join(str(w) for w in ws) + " min")
    r60 = next(r for r in rows if r["M"] == 60)
    has(f"(M = 60: {r60['w_net_min']} bis {r60['w_net_max']}, Median {de(r60['w_net_median'], 0)})")
    diffs = {r["M"]: r["gap_w5"][0] - r["gap_best"][0] for r in rows}
    top = max(diffs.values())
    assert sorted(m for m, d in diffs.items() if de(d) == de(top)) == [10, 120]
    has(f"bis zu {de(top)} Prozentpunkte (bei M = 10 und bei M = 120)")
    assert all(r["n_unproven"] == 0 for r in rows)
    flat = sum(1 for r in rows if min(r["gap_p"][w] - r["gap_p"][r["w_best"]] for w in (r["w_best"] - 1, r["w_best"] + 1) if w in r["gap_p"]) < 0.1)
    has(f"bei {flat} der {len(rows)} Werte von M liegt ein benachbartes W um weniger als 0,1 Prozentpunkte über dem besten W")


# ------------------------------------------------------------------ H3
def test_h3_immer_halten_ist_schlimmer_als_nie_halten(res):
    for exp in ("main", "knapp"):
        assert all(a > b for a, b in zip(R.gap_per_net(res, exp, "always"), R.gap_per_net(res, exp, "never")))
    assert all(r["gap_always"][0] > r["gap_never"][0] for r in R.mkurve_rows(res)) and len(R.mkurve_rows(res)) == 8
    n120 = sum(1 for r in res["mkurve"] if r and r["M"]["120"]["costs"]["always"] < r["M"]["120"]["costs"]["never"])
    has(f"(bei M = 120, normale Puffer, Phasen-Optimum, ist „immer halten“ gezählt über die Netzkosten der 100 Störtage in {n120} von 28 Netzen billiger als „nie halten“;")
    has(f"{pm(R.gap_summary(res, 'main', 'always'))} % über dem Optimum gegen {pm(R.gap_summary(res, 'main', 'never'))} % für „nie halten“")
    by_lines = [np.mean(R.gap_per_net(res, "main", "always", n_lines=l)) for l in range(4, 11)]
    has(f"von {de(by_lines[0])} % (4 Linien) auf {de(by_lines[-1])} % (10 Linien)")
    assert any(b < a for a, b in zip(by_lines, by_lines[1:]))                       # „nicht streng monoton“
    has(f"{de(by_lines[0])} bis {de(by_lines[-1])} % je Linienzahl")
    assert min(by_lines) == by_lines[0] and max(by_lines) == by_lines[-1]


# ------------------------------------------------------------------ H4
def test_h4_gegenrechnung_knapp_und_normal(res):
    kb, kp = R.gap_summary(res, "knapp", "bal2"), R.gap_summary(res, "knapp", "p3")
    nb, npp = R.gap_summary(res, "main", "bal2"), R.gap_summary(res, "main", "p5")
    has(f"Knapp: `bal2` {pm(kb)} % gegen {pm(kp)} % für das im Rückblick beste W, auch schlechter als „nie halten“ mit {de(R.gap_summary(res, 'knapp', 'never')[0])} %")
    assert kb[0] > R.gap_summary(res, "knapp", "never")[0]
    has(f"Normal: `bal2` {pm(nb)} % gegen {pm(npp)} %")
    for exp, bw, label in (("knapp", "p3", "5,6 ± 1,4"), ("main", "p5", "0,7 ± 0,8")):
        d = np.array(R.gap_per_net(res, exp, "bal2")) - np.array(R.gap_per_net(res, exp, bw))
        se = d.std(ddof=1) / np.sqrt(len(d))
        assert pm((d.mean(), se)) == label
        better = int((d < 0).sum())
        has(f"{label} Prozentpunkte" if exp == "knapp" else f"Differenz {label} Prozentpunkte")
        has(f"in {better} von 28 Netzen ist `bal2` besser" if exp == "knapp" else f"({better} von 28 Netzen `bal2` besser)")
        if exp == "main":
            assert abs(d.mean()) < 2 * se                                           # „nicht von null trennbar“
        else:
            assert d.mean() > 3 * se
    byl = lambda exp, l: np.mean(R.gap_per_net(res, exp, "bal2", n_lines=l))
    has(f"von {de(byl('main', 4))} % (4 Linien) auf {de(byl('main', 10))} % (10 Linien) bei normalen und von {de(byl('knapp', 4))} % auf {de(byl('knapp', 10))} % bei knappen Puffern (nicht streng monoton)")
    knapp_by_lines = [byl("knapp", l) for l in range(4, 11)]
    assert any(b < a for a, b in zip(knapp_by_lines, knapp_by_lines[1:]))                  # „nicht streng monoton“


def test_h5_gegenrechnung_gleichauf_bei_kleinem_m(res):
    rows = {r["M"]: r for r in R.mkurve_rows(res)}
    assert [m for m, r in rows.items() if r["gap_bal2"][0] <= r["gap_best"][0]] == [10, 15, 20]
    has("bei M = 10, 15 und 20 liegt sie gleichauf oder unter dem besten W")


# ------------------------------------------------------------------ H6, H7
def test_h6_kritische_anschluesse_und_plan_umsteigezeit(res):
    rows = {r["stufe"]: r for r in R.takt_rows(res)}
    order = ["zufall", "greedy", "phase", "split"]
    has("Kritische Anschlüsse je Störtag bei zufälligen Phasen " + de(rows["zufall"]["ncrit"]) + ", Greedy " + de(rows["greedy"]["ncrit"]) + ", Phasen-Optimum "
        + de(rows["phase"]["ncrit"]) + ", Phasen + Aufteilung " + de(rows["split"]["ncrit"]))
    has("Plan-Umsteigezeit " + ", ".join(de(rows[s]["plan_wait"]) for s in order) + " min je Umsteiger")
    assert rows["zufall"]["ncrit"] < rows["greedy"]["ncrit"] < rows["phase"]["ncrit"] < rows["split"]["ncrit"]
    assert rows["zufall"]["plan_wait"] > rows["greedy"]["plan_wait"] > rows["phase"]["plan_wait"] > rows["split"]["plan_wait"]
    has("beim Phasen-Optimum bei " + f"{rows['phase']['share_le5']:.3f}".replace(".", ",") + " und mit Aufteilung bei " + f"{rows['split']['share_le5']:.3f}".replace(".", ","))
    has("bei zufälligen Phasen bei " + f"{rows['zufall']['share_le5']:.3f}".replace(".", ","))
    assert all(r["n_unproven"] == 0 for r in rows.values())
    nets = [r for r in res["takt"] if r]
    more = sum(1 for r in nets if r["phase"]["ncrit_sum"] > r["greedy"]["ncrit_sum"])
    has(f"(Phasen-Optimum gegen Greedy in {more} von {len(nets)} Netzen höher)")
    assert rows["phase"]["ncrit"] - rows["greedy"]["ncrit"] < 0.5                                  # „Unterschied gering“


def test_h7_bilanz_des_besseren_takts(res):
    a, b, c = R.takt_netto(res, "zufall", "phase"), R.takt_netto(res, "phase", "split"), R.takt_netto(res, "greedy", "phase")
    has(f"Plan-Umsteigezeit −{de(a['dP_pct'])} %, Verspätungskosten je Störtag +{de(a['dV_pct'])} %")
    has(f"Gleichstand bei {de(a['breakeven'])} Störtagen je Horizont")
    has(f"−{de(b['dP_pct'])} % und +{de(b['dV_pct'])} %, Gleichstand bei {de(b['breakeven'])}")
    assert a["n_worse"] == 27 and b["n_worse"] == 27 and a["n"] == 28
    has(f"Die Verspätungskosten steigen in {a['n_worse']} von {a['n']} Netzen")
    assert c["dV_pct"] < 0 and de(c["dV_pct"]) == "-2,1"
    assert abs(c["dV_pct"]) < 2 * c["dV_se_pct"]                                                   # „nicht von null trennbar“
    has(f"Greedy → Phasen-Optimum: Verspätungskosten −{de(-c['dV_pct'])} ± {de(c['dV_se_pct'])} % (nicht von null trennbar; in {c['n_better']} von {c['n']} Netzen billiger, in {c['n'] - c['n_better']} teurer)")


def test_h3_umkehr_bei_grossem_m_ausserhalb_der_messreihe():
    """„Immer halten“ gegen „nie halten“ bei M = 200 und 300 (normale Puffer, Phasen-Optimum, 100 Störtage je Netz, gleiche Netze und Störtage wie die Messreihe); die M-Regler der App gehen nur bis 120."""
    import anh_measure as AM
    import anh_scenario as AS

    assert max(AM.MS) == 120
    better = {200: 0, 300: 0}
    n = 0
    for i in range(AM.N_NETS):
        built = AM.build_measure_net(i, "phase", "normal")
        if built is None:
            continue
        _inst, net = built
        seed = AM.net_params(i)[2]
        tot = {M: [0, 0] for M in better}
        for s in range(AM.N_SCEN):
            prim = AS.make_scenario(net, seed * 1000 + s)
            for M in better:
                c = AM._scenario_costs(net, prim, M, [("never",), ("always",)])
                tot[M][0] += c["never"]
                tot[M][1] += c["always"]
        n += 1
        for M in better:
            better[M] += tot[M][1] < tot[M][0]
    assert n == 28 and better == {200: 23, 300: 28}
    has("bei M = 200 ist „immer halten“ in 23 von 28 Netzen billiger als „nie halten“, bei M = 300 in 28 von 28")


# ------------------------------------------------------------------ H8
def test_h8_folgezug_erweiterung(res):
    ext = R.gap_summary(res, "main", "p5", key="ext")
    has(f"in der Erweiterung `p_5` {pm(ext)} %")
    for exp in ("main", "knapp"):
        base = sum(sum(r["ext"]["opt_base_decision"]) for r in res[exp] if r)
        opt = sum(sum(r["ext"]["opt"]) for r in res[exp] if r)
        assert de(100 * (base / opt - 1), 2) == ("0,03" if exp == "main" else "0,05")
    n_open = sum(1 for r in res["knapp"] if r for s in r["ext"]["status"] if s == "FEASIBLE")
    assert n_open == 17
    has(f"nur 0,03 % (knapp 0,05 %, dort in {n_open} von {sp(R.proven_counts(res, 'knapp')[0])} Störtagen das erweiterte Optimum nicht bewiesen) schlechter")
    dm = lambda exp: np.mean([x for r in res[exp] if r for x in r["dprime_mean"]])
    dp = lambda exp: 100 * np.mean([x for r in res[exp] if r for x in r["dprime_pos"]])
    has(f"D′ ist im Mittel {de(dm('main'), 2)} min (knapp {de(dm('knapp'), 2)}), nur {de(dp('main'))} % ({de(dp('knapp'))} %) des Gewichts haben D′ > 0")
    miss = 100 * np.mean([r["miss_share"] for r in res["main"] if r])
    has(f"{de(miss)} % des Umsteigergewichts haben keine nächste Fahrt im Horizont")
    for exp in ("main", "knapp"):
        assert all(c >= 0 for r in res[exp] if r for c in (np.array(r["ext"]["costs"]["never"]) - np.array(r["costs"]["never"])))


# ------------------------------------------------------------------ H10 und Streuung
def test_h10_rangkorrelation_der_luecke_mit_der_linienzahl(res):
    for exp, label in (("main", "−0,12"), ("knapp", "+0,45")):
        nets = [r for r in res[exp] if r]
        rho = rank_corr([r["n_lines"] for r in nets], R.gap_per_net(res, exp, "p5"))
        assert f"{rho:+.2f}".replace("-", "−").replace(".", ",") == label
    has("über die 28 Netze −0,12 (kein Trend); knappe Puffer +0,45")


def test_streuung_je_stoertag(res):
    s = R.scenario_stats(res, "main", "p5")
    t = R.scenario_stats(res, "main", "bal2")
    k = R.scenario_stats(res, "knapp", "p5")
    sd, td, kd = (R.scenario_stats(res, e, r, decided_only=True) for e, r in (("main", "p5"), ("main", "bal2"), ("knapp", "p5")))
    has(f"`p_5` trifft das Optimum in {de(100 * s['share_equal'])} % der Störtage ({de(100 * sd['share_equal'])} % der Störtage mit mindestens einem kritischen Anschluss; Lücke im Median {de(s['median'])} %, P90 {de(s['p90'])} %, P99 {de(s['p99'])} %, Maximum {de(s['max'])} %)")
    has(f"trifft es in {de(100 * t['share_equal'])} % ({de(100 * td['share_equal'])} % der Störtage mit mindestens einem kritischen Anschluss; Median {de(t['median'], 2)} %, aber P99 {de(t['p99'])} % und Maximum {de(t['max'])} %)")
    assert t["share_equal"] > s["share_equal"] and t["p99"] > s["p99"]                  # „ihr Tail ist dicker“ und „trifft öfter“
    assert R.gap_summary(res, "main", "bal2")[0] > R.gap_summary(res, "main", "p5")[0]  # „im Mittel schlechter“
    has(f"Bei knappen Puffern trifft `p_5` das Optimum in {de(100 * k['share_equal'])} % der Störtage ({de(100 * kd['share_equal'])} % der Störtage mit mindestens einem kritischen Anschluss)")
    assert sd["n"] == R.proven_counts(res, "main")[0] and kd["n"] == R.proven_counts(res, "knapp")[0]       # Störtage mit Entscheidung
    # Die Pflichttext-Zahlen der Grenzen
    assert f"im Median bei {de(s['median'])} %, im P90 bei {de(s['p90'])} %, im P99 bei {de(s['p99'])} % und im Maximum bei {de(s['max'])} %" in C.ASSUMPTIONS_MARKDOWN


def test_pflichttext_der_grenzen_steht_in_app_und_readme_gleich(res):
    assert C.ASSUMPTIONS_MARKDOWN.strip() in README
    assert "st.markdown(C.ASSUMPTIONS_MARKDOWN)" in (ROOT / "app.py").read_text(encoding="utf-8")
    ext = R.gap_summary(res, "main", "p5", key="ext")[0]
    base = R.gap_summary(res, "main", "p5")[0]
    assert f"nur von {de(base)} auf {de(ext)} % (E5)" in C.ASSUMPTIONS_MARKDOWN
    nets = [r for r in res["main"] if r]
    assert {r["N"] / r["n_lines"] for r in nets} == {80} and min(r["N"] for r in nets) == 320 and max(r["N"] for r in nets) == 800
    assert sorted({r["n_stops"] for r in nets}) == [16, 20, 24]


def test_preset_hilfen_nennen_das_gemessene_beste_w(res):
    rows = {r["M"]: r for r in R.mkurve_rows(res)}
    assert rows[15]["w_best"] == 2 and rows[120]["w_best"] == 9
    assert "bei 2 min (E1)" in C.PRESET_HELP["Folgezug kommt bald"] and "bei 9 min (E1)" in C.PRESET_HELP["Folgezug kommt spät"]
    assert C.PRESETS["Folgezug kommt bald"]["M"] == 15 and C.PRESETS["Folgezug kommt spät"]["M"] == 120


def test_zaehlangaben_der_verifikation_stehen_im_testcode():
    src = (ROOT / "tests" / "test_oracle_delay_management.py").read_text(encoding="utf-8")
    assert src.count("for _ in range(60):") == 2 and "for M in (5, 15, 60)" in src and "range(2)" in src and "range(3)" in src
    has("60 Zufalls-Mini-Netzen × 3 Störtage × 3 Werte von M, die Erweiterung auf 60 Netzen × 2 Störtagen")
    has("drei kleinen echten Netzen")
    assert src.count("@pytest.mark.parametrize(\"nl,ns,seed,variant\"") == 1 and "(3, 14, 7101" in src and "(5, 18, 9001" in src
    has("auf sechs Netzen")
    assert "(4, 16, 9000), (6, 20, 9002), (8, 24, 9017), (10, 20, 9027), (7, 20, 9005), (5, 20, 9012)" in src


def test_mini_beispiel_der_readme_und_der_app():
    mc = ev.mini_costs()
    assert (mc["never"], mc["c0"], mc["c0c2"], mc["opt"]) == (600, 405, 420, 405)
    has("(600 / 405 / 420)")
    has("Optimum 405")
    has("Optimum 420 statt 405")
