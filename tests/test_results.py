"""Die vorgerechnete Messreihe (data/anh_results.json): Bindung an den Code, Aufbau, innere Konsistenz.

Die Datei entsteht mit `python tools/build_results.py`. Ändert sich eine Datei aus `anh_results.GENERATOR_FILES`, ist die Prüfsumme veraltet und dieser Test
schlägt fehl: Dann muss die Messreihe neu erzeugt werden (und die Zahlen in README und tests/test_claims.py neu gelesen)."""

import pytest

import anh_results as R


@pytest.fixture(scope="module")
def res():
    return R.load_results()


def test_pruefsumme_gehoert_zum_stand_des_codes(res):
    assert res["meta"]["generator_hash"] == R.generator_hash(), "data/anh_results.json ist veraltet: python tools/build_results.py neu ausführen"


def test_generator_hash_ist_unabhaengig_vom_zeilenende_und_reagiert_auf_aenderungen(tmp_path, monkeypatch):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    lf.mkdir(), crlf.mkdir()
    for name in R.GENERATOR_FILES:
        text = (R.ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        (lf / name).write_bytes(text.encode("utf-8"))
        (crlf / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.setattr(R, "ROOT", lf)
    h_lf = R.generator_hash()
    monkeypatch.setattr(R, "ROOT", crlf)
    assert R.generator_hash() == h_lf and len(h_lf) == 16
    (crlf / "anh_rules.py").write_bytes((crlf / "anh_rules.py").read_bytes() + b"# x\r\n")
    assert R.generator_hash() != h_lf


def test_aufbau_28_netze_100_stoertage(res):
    m = res["meta"]
    assert m["N_NETS"] == 28 and m["N_SCEN"] == 100 and m["M_MAIN"] == 60
    assert m["net_seeds"] == list(range(9000, 9028))
    for exp in ("main", "knapp"):
        nets = [r for r in res[exp] if r]
        assert len(nets) == 28
        for r in nets:
            assert len(r["opt"]) == len(r["ncrit"]) == len(r["status"]) == 100
            assert all(len(v) == 100 for v in r["costs"].values()) and all(len(v) == 100 for v in r["ext"]["costs"].values())


def test_je_linienzahl_vier_netze(res):
    from collections import Counter
    for exp in ("main", "knapp"):
        assert Counter(r["n_lines"] for r in res[exp] if r) == {k: 4 for k in range(4, 11)}


def test_kein_regelkosten_unter_dem_optimum_wenn_bewiesen(res):
    for exp in ("main", "knapp"):
        for r in res[exp]:
            for k in range(100):
                if r["status"][k] in ("OPTIMAL", "NOCRIT"):
                    assert all(c[k] >= r["opt"][k] for c in r["costs"].values())
                    if r["ext"]["status"][k] in ("OPTIMAL", "NOCRIT"):
                        assert all(c[k] >= r["ext"]["opt"][k] for c in r["ext"]["costs"].values())
                        assert r["ext"]["opt_base_decision"][k] >= r["ext"]["opt"][k]


def test_mkurve_und_takt_sind_vollstaendig(res):
    assert len([r for r in res["mkurve"] if r]) == 28 and len([r for r in res["takt"] if r]) == 28
    for r in res["mkurve"]:
        assert set(r["M"]) == {str(m) for m in res["meta"]["MS"]}
    for r in res["takt"]:
        assert set(r) == set(res["meta"]["TAKT_STUFEN"])


def test_die_zeiten_sind_nicht_in_der_datei(res):
    assert all("secs" not in r for r in res["main"] if r) and all("secs" not in r for r in res["knapp"] if r)
