"""Vorgerechnete Messreihe (data/anh_results.json, erzeugt mit tools/build_results.py): Laden, Prüfsumme und Auswertung.

Die App rechnet die Messreihe nie live; alle Statistiken (Netz-Mittel ± Standardfehler, Abstand der Regeln zum Optimum, Wanderung des besten W, Takt-Brücke,
Streuung je Störtag) kommen aus den Einzelwerten je Netz in der Datei. Der Abstand einer Regel zum Optimum wird je Netz als Verhältnis der Summen über die 100
Störtage berechnet (Kosten der Regel / Kosten des Optimums - 1); ausgewiesen wird das Mittel über die 28 Netze ± Standardfehler (Standardabweichung / Wurzel 28).
"""
from __future__ import annotations

import hashlib
import json
import statistics as st
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS_FILE = ROOT / "data" / "anh_results.json"
# Dateien, deren Inhalt die Zahlen der Messreihe bestimmt: ändert sich eine, ist die Datei veraltet (tests/test_results.py prüft die Prüfsumme)
GENERATOR_FILES = ("anh_rng.py", "anh_timetable.py", "anh_takt.py", "anh_network.py", "anh_scenario.py", "anh_propagate.py", "anh_rules.py",
                   "anh_exact.py", "anh_measure.py")


def generator_hash() -> str:
    h = hashlib.sha256()
    for name in GENERATOR_FILES:
        text = (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        h.update(name.encode() + b"\0" + text.encode("utf-8") + b"\0")
    return h.hexdigest()[:16]


def load_results(path=None) -> dict:
    return json.loads(Path(path or RESULTS_FILE).read_text(encoding="utf-8"))


def mean_se(xs) -> tuple:
    xs = list(xs)
    return st.mean(xs), (st.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else float("nan"))


def _nets(res: dict, exp: str) -> list:
    return [r for r in res[exp] if r is not None]


# ---------------------------------------------------------------- Abstände zum Optimum (main / knapp)
def gap_per_net(res: dict, exp: str, rule: str, n_lines: int | None = None, key: str = "costs") -> list:
    """Abstand der Regel zum Optimum je Netz in Prozent der Optimumskosten (Summen über die Störtage). key="ext": Erweiterung „Folgezug ebenfalls verspätet“."""
    out = []
    for r in _nets(res, exp):
        if n_lines is not None and r["n_lines"] != n_lines:
            continue
        src = r if key == "costs" else r["ext"]
        opt = sum(src["opt"])
        out.append(100 * (sum(src["costs"][rule]) / opt - 1))
    return out


def gap_summary(res: dict, exp: str, rule: str, n_lines: int | None = None, key: str = "costs") -> tuple:
    """(Mittel, Standardfehler) des Abstands über die Netze."""
    return mean_se(gap_per_net(res, exp, rule, n_lines, key))


def opt_below_never(res: dict, exp: str, key: str = "costs") -> float:
    """Optimum liegt so viel Prozent unter „nie halten“ (Basis: Kosten von „nie halten“, Summen über alle Netze und Störtage)."""
    rows = _nets(res, exp)
    src = (lambda r: r) if key == "costs" else (lambda r: r["ext"])
    return 100 * (1 - sum(sum(src(r)["opt"]) for r in rows) / sum(sum(src(r)["costs"]["never"]) for r in rows))


def best_w(res: dict, exp: str, ws=range(1, 15), n_lines: int | None = None, key: str = "costs") -> tuple:
    """(bestes W, Abstand dort, Standardfehler) der Regel p_W: das W mit dem kleinsten Netz-Mittel des Abstands."""
    best = min(ws, key=lambda w: gap_summary(res, exp, f"p{w}", n_lines, key)[0])
    return (best,) + gap_summary(res, exp, f"p{best}", n_lines, key)


def best_rule_overall(res: dict, exp: str, families=("p", "c")) -> tuple:
    """(Regelname, Mittel, SE) der besten festen Schwellenregel der Familien p_W/c_W im Rückblick."""
    names = [n for n in res[exp][0]["costs"] if n[0] in families and n[1:].isdigit()]
    best = min(names, key=lambda n: gap_summary(res, exp, n)[0])
    return (best,) + gap_summary(res, exp, best)


def lines_of(res: dict, exp: str = "main") -> list:
    return sorted({r["n_lines"] for r in _nets(res, exp)})


# ---------------------------------------------------------------- Streuung je Störtag
def scenario_gaps(res: dict, exp: str, rule: str, decided_only: bool = False) -> np.ndarray:
    """Lücke der Regel zum Optimum je Störtag in Prozent der Optimumskosten (Störtage mit Optimum 0 entfallen). decided_only: nur Störtage mit mindestens einem
    kritischen Anschluss; auf den übrigen kosten alle Regeln gleich viel, sie zählen sonst als „trifft das Optimum“."""
    gaps = []
    for r in _nets(res, exp):
        for c, o, nc in zip(r["costs"][rule], r["opt"], r["ncrit"]):
            if o and o > 0 and (nc > 0 or not decided_only):
                gaps.append(100 * (c / o - 1))
    return np.array(gaps)


def scenario_stats(res: dict, exp: str, rule: str, decided_only: bool = False) -> dict:
    g = scenario_gaps(res, exp, rule, decided_only)
    return {"n": len(g), "median": float(np.median(g)), "p90": float(np.percentile(g, 90)), "p99": float(np.percentile(g, 99)), "max": float(g.max()),
            "share_equal": float(np.mean(g <= 1e-9))}


def proven_counts(res: dict, exp: str) -> tuple:
    """(Störtage mit Entscheidung, davon bewiesen, nicht bewiesen)."""
    stat = [s for r in _nets(res, exp) for s in r["status"] if s != "NOCRIT"]
    n_ok = sum(1 for s in stat if s == "OPTIMAL")
    return len(stat), n_ok, len(stat) - n_ok


# ---------------------------------------------------------------- Wanderung des besten W (mkurve)
def mkurve_rows(res: dict) -> list:
    """Je M: Optimum unter „nie“ (%), bestes W (Netz-Mittel), Abstand dort ± SE, fester Abstand für W = 5, nie, immer, bal2 (Netz-Mittel des Abstands)."""
    rows = []
    for M in res["meta"]["MS"]:
        nets = [r["M"][str(M)] for r in _nets(res, "mkurve")]
        gaps = lambda rule: [100 * (c["costs"][rule] / c["opt"] - 1) for c in nets if c["opt"] > 0]
        ws = res["meta"]["WS"]
        wbest = min(ws, key=lambda w: st.mean(gaps(f"p{w}")))
        below = 100 * (1 - sum(c["opt"] for c in nets) / sum(c["costs"]["never"] for c in nets))
        wnet = [min(ws, key=lambda w: c["costs"][f"p{w}"]) for c in nets]
        rows.append({"M": M, "below_never": below, "w_best": wbest, "gap_best": mean_se(gaps(f"p{wbest}")), "gap_w5": mean_se(gaps("p5")),
                     "gap_never": mean_se(gaps("never")), "gap_always": mean_se(gaps("always")), "gap_bal2": mean_se(gaps("bal2")),
                     "w_net_min": min(wnet), "w_net_median": float(np.median(wnet)), "w_net_max": max(wnet),
                     "gap_p": {w: st.mean(gaps(f"p{w}")) for w in ws}, "n_unproven": sum(c["n_unproven"] for c in nets)})
    return rows


# ---------------------------------------------------------------- Brücke: Takt bestimmt die Puffer (takt)
def takt_rows(res: dict) -> list:
    """Je Takt-Stufe: Plan-Umsteigezeit, Gewicht mit Puffer <= 5 min, kritische Anschlüsse je Störtag, bestes W und Abstand, bal2, immer (Netz-Mittel)."""
    rows = []
    n_scen = res["meta"]["N_SCEN"]
    for stufe in res["meta"]["TAKT_STUFEN"]:
        cells = [r[stufe] for r in _nets(res, "takt")]
        gaps = lambda rule: [100 * (c["costs"][rule] / c["opt_sum"] - 1) for c in cells]
        wbest = min(range(1, 11), key=lambda w: st.mean(gaps(f"p{w}")))
        rows.append({"stufe": stufe, "plan_wait": st.mean(c["plan_wait"] for c in cells), "share_le5": st.mean(c["share_le5"] for c in cells),
                     "ncrit": st.mean(c["ncrit_sum"] / n_scen for c in cells), "w_best": wbest, "gap_best": mean_se(gaps(f"p{wbest}")),
                     "gap_bal2": mean_se(gaps("bal2")), "gap_always": mean_se(gaps("always")), "P": st.mean(c["P"] for c in cells),
                     "V": st.mean(c["opt_sum"] / n_scen for c in cells), "n_unproven": sum(c["n_unproven"] for c in cells)})
    return rows


def takt_netto(res: dict, a: str, b: str) -> dict:
    """Gewinn an Plan-Umsteigezeit P und Mehrkosten durch Verspätung V je Störtag beim Wechsel von Stufe a auf Stufe b (je Netz gepaart, Einheit Gewicht * Minuten)
    und die Zahl der Störtage je Horizont, bei der beide gleich gut sind (Gleichstand P_a + f V_a = P_b + f V_b)."""
    ca = [r[a] for r in _nets(res, "takt")]
    cb = [r[b] for r in _nets(res, "takt")]
    n_scen = res["meta"]["N_SCEN"]
    dP = np.array([x["P"] - y["P"] for x, y in zip(ca, cb)])
    dV = np.array([(y["opt_sum"] - x["opt_sum"]) / n_scen for x, y in zip(ca, cb)])
    Pa = np.mean([x["P"] for x in ca])
    Va = np.mean([x["opt_sum"] / n_scen for x in ca])
    return {"dP": float(dP.mean()), "dP_pct": float(100 * dP.mean() / Pa), "dV": float(dV.mean()), "dV_pct": float(100 * dV.mean() / Va),
            "dV_se_pct": float(100 * dV.std(ddof=1) / len(dV) ** 0.5 / Va),       # Standardfehler der gepaarten Differenz, in Prozent von V der Ausgangsstufe
            "breakeven": float(dP.mean() / dV.mean()) if dV.mean() > 0 else float("inf"), "n_worse": int((dV > 0).sum()), "n_better": int((dV < 0).sum()), "n": len(dV)}


def core_stats(res: dict) -> dict:
    """Kennzahlen der Kernfrage aus der Messreihe `main` (normale Puffer, M = 60, Phasen-Optimum)."""
    name, gap, se = best_rule_overall(res, "main")
    return {"best_name": f"{name[0]}_{name[1:]}", "best_gap": gap, "best_se": se, "below_never": opt_below_never(res, "main"), "n_nets": len(_nets(res, "main")),
            "n_scen": res["meta"]["N_SCEN"], "never_gap": gap_summary(res, "main", "never")[0], "always_gap": gap_summary(res, "main", "always")[0]}
