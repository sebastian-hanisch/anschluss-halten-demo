"""End-to-end Smoke-Test via Streamlits offiziellem AppTest-Framework: laedt app.py mit den
Standardeinstellungen, klickt jeden Preset-Button und faehrt jeden Slider an seine Grenzen und prueft, dass
kein Python-Fehler auftritt - insbesondere `streamlit.errors.StreamlitDuplicateElementId` (mehrere
st.plotly_chart-Aufrufe ohne eindeutiges key= koennen zufaellig identischen Inhalt rendern und kollidieren)
und `StreamlitAPIException` bei Slidern mit berechneten Grenzen (min == max)."""

import os

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))  # unter Last (parallele Läufe) reichen 180 s nicht immer; Umgebungsvariable zum Anpassen
AUTOPLAY_MARKER = "\u25b6"  # Auto-Play-Buttons (Animation mit sleep) im Smoke-Test auslassen


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_app_loads_without_exception():
    _fresh_app()


def test_every_button_click_does_not_raise():
    labels = [b.label for b in _fresh_app().button]
    assert labels, "keine Buttons gefunden"
    for index, label in enumerate(labels):
        if AUTOPLAY_MARKER in label:
            continue
        at = _fresh_app()
        at.button[index].click().run(timeout=TIMEOUT)
        assert not at.exception, (label, [str(e) for e in at.exception])


def test_every_slider_at_its_min_and_max_does_not_raise():
    labels = [s.label for s in _fresh_app().slider]
    assert labels, "keine Slider gefunden"
    for index, label in enumerate(labels):
        for edge in ("min", "max"):
            at = _fresh_app()
            slider = at.slider[index]
            value = slider.min if edge == "min" else slider.max
            if isinstance(slider.value, int):
                value = int(value)
            slider.set_value(value).run(timeout=TIMEOUT)
            assert not at.exception, (label, edge, [str(e) for e in at.exception])


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Zusatztests (unter der Vorlage): Knöpfe mit ▶️ einzeln, Maxima der Regler, Auswahlfelder, Permalink, Abschnitte

import anh_constants as C


def _texts(at):
    return " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.caption) + " " + " ".join(i.value for i in at.info)


def test_live_knopf_rechnet_stoertage_einzeln(monkeypatch):
    monkeypatch.setattr(C, "LIVE_RUN_SCENARIOS", 4)
    at = _fresh_app()
    knopf = next(b for b in at.button if AUTOPLAY_MARKER in b.label)
    knopf.click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert "4 Störtage gerechnet" in _texts(at)


def test_maxima_zehn_linien_knappe_puffer_sechzehn_verspaetungen_ohne_fehler():
    at = _fresh_app()
    at.slider(key="lines_slider").set_value(C.LINES_MAX)
    at.selectbox(key="puffer_select").set_value("knapp")
    at.slider(key="k_slider").set_value(C.K_MAX)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert "Primärverspätungen" in _texts(at) or at.get("metric")


def test_jede_regel_und_die_erweiterung_laufen():
    for regel in C.RULES:
        at = _fresh_app()
        at.selectbox(key="rule_select").set_value(regel).run(timeout=TIMEOUT)
        assert not at.exception, (regel, [str(e) for e in at.exception])
        assert at.slider(key="w_slider").disabled == (regel not in C.RULES_WITH_W)
    at = _fresh_app()
    at.toggle(key="folgezug_toggle").set_value(True).run(timeout=TIMEOUT)
    assert not at.exception


def test_jede_taktstufe_und_jedes_m_fuer_die_kurven():
    for stufe in C.STUFEN:
        at = _fresh_app()
        at.selectbox(key="stufe_select").set_value(stufe).run(timeout=TIMEOUT)
        assert not at.exception, (stufe, [str(e) for e in at.exception])
    at = _fresh_app()
    for m in at.select_slider(key="e1_m").options:
        at.select_slider(key="e1_m").set_value(m).run(timeout=TIMEOUT)
        assert not at.exception, (m, [str(e) for e in at.exception])


def test_experiment_umschalter_und_slider_der_bilanz():
    at = _fresh_app()
    for key in ("e3_exp", "e4_exp"):
        at.radio(key=key).set_value("knapp").run(timeout=TIMEOUT)
        assert not at.exception, (key, [str(e) for e in at.exception])
    for f in (0.5, 20.0):
        at.slider(key="e2_f").set_value(f).run(timeout=TIMEOUT)
        assert not at.exception


def test_permalink_uebernimmt_werte_und_begrenzt_sie():
    at = AppTest.from_file(APP_PATH)
    at.query_params["m"] = "999"
    at.query_params["regel"] = "unbekannt"
    at.query_params["lines"] = "7"
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert at.slider(key="m_slider").value == C.M_MAX and at.selectbox(key="rule_select").value == C.DEFAULT_RULE and at.slider(key="lines_slider").value == 7


def test_die_abschnitte_stehen_in_der_vorgesehenen_reihenfolge_und_expander_per_titel():
    at = _fresh_app()
    titel = [h.value for h in at.subheader] + [m.value for m in at.markdown if m.value.startswith("## ")]
    for erwartet in ("🔬 E1", "🔬 E2", "🔬 E3", "🔬 E4", "🔬 E5", "🚧 Wo die Annahmen enden", "## 🎯 Ein Störtag", "## ❓ Kernfrage"):
        assert any(t.startswith(erwartet) for t in titel), erwartet
    labels = [e.label for e in at.expander]
    assert "📐 Mathematische Formulierung" in labels and "So funktioniert Delay Management" in labels and "💬 In einfachen Worten" in labels
