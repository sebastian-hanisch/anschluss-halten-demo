"""Rechnet die Messreihe vor und schreibt data/anh_results.json (höchstens zwei Prozesse, CP-SAT mit einem Arbeiter).

Aufruf (aus dem Repo-Ordner):  python tools/build_results.py [--raw ORDNER] [--procs 2] [--n-scen 100] [--nets 28]
Zwischenstände liegen als eine Datei je (Experiment, Netz) im Ordner --raw und werden bei einem Neustart übernommen. Die Störtage hängen nur an den Zufalls-Seeds der Netze
(nie am Ergebnis); `meta.generator_hash` bindet die Datei an den Stand des Codes (tests/test_results.py).
"""
import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anh_exact as AE  # noqa: E402
import anh_measure as MS  # noqa: E402
import anh_results as R  # noqa: E402

FUNCS = {"main": lambda i, n: MS.run_main(i, "normal", n), "knapp": lambda i, n: MS.run_main(i, "knapp", n),
         "mkurve": lambda i, n: MS.run_mkurve(i, n), "takt": lambda i, n: MS.run_takt(i, n)}


def task(args):
    exp, i, n_scen, raw = args
    path = Path(raw) / f"{exp}_{i:02d}.json"
    if path.exists():
        return exp, i, 0.0
    t0 = time.perf_counter()
    res = FUNCS[exp](i, n_scen)
    path.write_text(json.dumps(res), encoding="utf-8")
    return exp, i, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "tools" / "raw"))
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--n-scen", type=int, default=MS.N_SCEN)
    ap.add_argument("--nets", type=int, default=MS.N_NETS)
    ap.add_argument("--out", default=str(R.RESULTS_FILE))
    a = ap.parse_args()
    Path(a.raw).mkdir(parents=True, exist_ok=True)
    tasks = [(exp, i, a.n_scen, a.raw) for exp in ("main", "knapp", "takt", "mkurve") for i in range(a.nets)]
    t0 = time.perf_counter()
    with mp.Pool(min(a.procs, 2)) as pool:
        for k, (exp, i, secs) in enumerate(pool.imap_unordered(task, tasks)):
            print(f"{k + 1}/{len(tasks)} {exp} Netz {i}: {secs:.0f} s (gesamt {time.perf_counter() - t0:.0f} s)", flush=True)
    res = {"meta": {"generator_hash": R.generator_hash(), "N_NETS": a.nets, "N_SCEN": a.n_scen, "MS": list(MS.MS), "WS": list(MS.WS), "TAKT_STUFEN": list(MS.TAKT_STUFEN),
                    "M_MAIN": MS.M_MAIN, "time_limit_s": AE.MEASURE_TIME_LIMIT, "net_seeds": [MS.net_params(i)[2] for i in range(a.nets)]}}
    for exp in ("main", "knapp", "takt", "mkurve"):
        res[exp] = [json.loads((Path(a.raw) / f"{exp}_{i:02d}.json").read_text(encoding="utf-8")) for i in range(a.nets)]
    # Rechenzeit ist lastbehaftet und steht nirgends als feste Zahl: die Zeiten je Störtag werden nicht gespeichert
    for exp in ("main", "knapp"):
        for r in res[exp]:
            if r is not None:
                r.pop("secs", None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    print("geschrieben:", a.out)


if __name__ == "__main__":
    main()
