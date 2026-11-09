"""Live-Rechnung eines Störtags (`analyse`), Zeilen der kritischen Anschlüsse und PDF."""

import pytest

import anh_constants as C
import anh_evaluation as ev
import anh_pdf_export as PDF


@pytest.fixture(scope="module")
def netz():
    return ev.build_network(6, "phase", "normal", 9601)


def test_analyse_kosten_sind_konsistent(netz):
    a = ev.analyse(ev.Settings(), netz)
    assert a.crit and a.opt.proven and a.cost_opt <= a.cost_rule and a.cost_opt <= a.cost_never and a.cost_opt <= a.cost_always
    assert len(a.prim) == C.DEFAULT_K and all(3 <= h <= 30 for h in a.prim.values())
    assert 0 <= a.same_share <= 1 and a.gap_pct is not None and a.gap_pct >= 0


def test_analyse_ist_wiederholbar_und_haengt_am_seed(netz):
    s = ev.Settings()
    a, b = ev.analyse(s, netz), ev.analyse(s, netz)
    assert (a.prim, a.cost_opt, a.cost_rule, a.crit) == (b.prim, b.cost_opt, b.cost_rule, b.crit)
    c = ev.analyse(ev.Settings(scen_seed=2), netz)
    assert c.prim != a.prim


def test_regler_k_und_hmax_wirken(netz):
    a = ev.analyse(ev.Settings(k=2, hmax=5), netz)
    assert len(a.prim) == 2 and all(3 <= h <= 5 for h in a.prim.values())
    b = ev.analyse(ev.Settings(k=C.K_MAX), netz)
    assert len(b.prim) == C.K_MAX
    c = ev.analyse(ev.Settings(hmax=3), netz)
    assert set(c.prim.values()) == {3}                 # hmax am unteren Rand: alle Verspätungen genau 3 min


def test_kleinste_stoerung_liefert_definierte_werte(netz):
    a = ev.analyse(ev.Settings(k=1, hmax=3, scen_seed=0), netz)
    # eine Verspätung von 3 min kann kritisch werden oder nicht; die Analyse muss in beiden Fällen definierte Werte liefern
    assert a.cost_opt is not None and (a.same_share is None) == (not a.crit)


def test_folgezug_erweiterung_macht_nie_halten_nicht_billiger(netz):
    base = ev.analyse(ev.Settings(), netz)
    ext = ev.analyse(ev.Settings(folgezug=True), netz)
    assert ext.cost_never >= base.cost_never and ext.cost_always >= base.cost_always
    assert ext.cost_never > base.cost_never


def test_regel_tupel_und_beschriftung():
    assert ev.rule_tuple("never", 7) == ("never",) and ev.rule_tuple("p", 7) == ("p", 7) and ev.rule_tuple("d", 3) == ("d", 3, 75)
    assert ev.rule_label("p", 7) == "p_7" and ev.rule_label("bal2", 7) == "Gegenrechnung (verfeinert)"


def test_connection_rows_sortiert_nach_gewicht_und_begrenzt(netz):
    a = ev.analyse(ev.Settings(k=C.K_MAX), netz)
    rows = ev.connection_rows(a, limit=5)
    assert len(rows) == min(5, len(a.crit))
    assert [r["weight"] for r in rows] == sorted((r["weight"] for r in rows), reverse=True)
    for r in rows:
        assert r["plan_dep"] >= r["plan_arr"] + 3 and r["hold_opt"] in (True, False) and r["dep_delay_opt"] >= 0


def test_kein_netz_mit_zu_wenigen_linien_fuehrt_zum_absturz():
    n = ev.build_network(C.LINES_MIN, "split", "knapp", 9601)
    assert n.n_lines >= 2 and n.net.nconn > 0


def test_pdf_ist_ein_pdf_und_vertraegt_umlaute(netz):
    a = ev.analyse(ev.Settings(), netz)
    data = PDF.generate_report_pdf("Anschluss halten oder abfahren", ["Zeile mit Umlauten: äöüß „Zitat“ – Strich"], ev.connection_rows(a))
    assert data[:5] == b"%PDF-" and len(data) > 1000
    assert PDF._clean("a – b → c") == "a - b -> c"


def test_wirksame_halte_an_der_mini_instanz_von_hand():
    """Alle drei Anschlüsse gehalten: c1 braucht dieselbe Abfahrtsverspätung (4 min) wie c0 und ändert nichts; wirksam sind c0 und c2 (siehe conftest.py)."""
    net = ev.mini_example()
    assert ev.effective_holds(net, ev.MINI_PRIM, {0, 1, 2}) == {0, 2}
    assert ev.effective_holds(net, ev.MINI_PRIM, {1}) == {1}
    assert ev.effective_holds(net, ev.MINI_PRIM, set()) == set()
    assert ev.effective_holds(net, ev.MINI_PRIM, {2}) == set()           # B fährt pünktlich: c2 ist ohnehin erreicht, Halten wartet nicht


def test_wirksame_halte_aendern_die_fortpflanzung_nicht(netz):
    import anh_propagate as AP
    import anh_rules as AR
    a = ev.analyse(ev.Settings(k=C.K_MAX), netz)
    net = netz.net
    for held in (a.opt.held, frozenset(range(net.nconn)), a.rule_held):
        eff = ev.effective_holds(net, a.prim, held)
        assert eff <= set(held)
        assert list(AP.propagate(net, a.prim, eff)) == list(AP.propagate(net, a.prim, held))
    D, h = AR.run_rule(net, a.prim, 60, ("p", 5))
    assert ev.effective_holds(net, a.prim, h) == h                      # die Halte einer Regel sind schon wirksam
    assert a.opt_held <= a.opt.held and a.opt_held == ev.effective_holds(net, a.prim, a.opt.held)
