"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, jedes Preset hat etwas zu entscheiden."""

import pytest

import anh_constants as C
import anh_evaluation as ev
import anh_presets as P


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP) == set(C.PRESET_ORDER)
    assert list(C.PRESETS) == C.PRESET_ORDER
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_inside_the_regler_bounds():
    for name, preset in C.PRESETS.items():
        for key, state_key in P.PRESET_KEYS.items():
            spec = P.SETTING_SPECS[state_key]
            assert P.clamp_value(spec, preset[key]) == preset[key], (name, key)
        assert preset["M"] % C.M_STEP == 0


def test_default_preset_equals_the_default_settings():
    assert ev.Settings(**C.PRESETS["Standard"]) == ev.Settings()


def test_setting_specs_cover_every_preset_key():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)


def test_clamp_value_begrenzt_zahlen_und_faellt_bei_unbekannter_option_auf_den_standard_zurueck():
    spec_m = P.SETTING_SPECS["m_slider"]
    assert P.clamp_value(spec_m, 5) == C.M_MIN and P.clamp_value(spec_m, 999) == C.M_MAX and P.clamp_value(spec_m, 60) == 60
    spec_r = P.SETTING_SPECS["rule_select"]
    assert P.clamp_value(spec_r, "zufall") == C.DEFAULT_RULE and P.clamp_value(spec_r, "bal2") == "bal2"
    assert P.SETTING_SPECS["folgezug_toggle"].caster("1") is True and P.SETTING_SPECS["folgezug_toggle"].caster("0") is False


def test_nur_das_preset_knappe_puffer_aendert_puffer_und_regel_zugleich():
    base = C.PRESETS["Standard"]
    diffs = {n: {k for k in p if p[k] != base[k]} for n, p in C.PRESETS.items()}
    assert diffs["Standard"] == set()
    assert diffs["Knappe Puffer"] == {"puffer", "rule"} and diffs["Dichter Takt"] == {"stufe"} and diffs["Immer halten"] == {"rule"}
    assert diffs["Folgezug kommt bald"] == {"M"} == diffs["Folgezug kommt spät"] and diffs["Folgezug auch verspätet"] == {"folgezug"}


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_jedes_preset_hat_kritische_anschluesse_und_ein_optimum(name):
    """Ein Preset ohne Entscheidung dürfte keinen Effekt melden (DEMO-PLAYBOOK §11a Nr. 7): hier hat jedes mindestens einen kritischen Anschluss."""
    s = ev.Settings(**C.PRESETS[name])
    a = ev.analyse(s, ev.build_network(s.lines, s.stufe, s.puffer, s.net_seed))
    assert a.crit and a.opt.cost is not None and a.cost_opt <= min(a.cost_never, a.cost_always, a.cost_rule)


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_das_verdikt_jedes_presets_passt_zu_seinen_kosten(name):
    """DEMO-PLAYBOOK §11a Nr. 7: je Preset die erwartete Verdikt-Zeile; ein Preset, dessen Regel das Optimum trifft, meldet keinen Abstand, und umgekehrt."""
    s = ev.Settings(**C.PRESETS[name])
    a = ev.analyse(s, ev.build_network(s.lines, s.stufe, s.puffer, s.net_seed))
    kind, text = ev.verdict_rule(a, ev.rule_label(s.rule, s.W))
    if a.cost_rule == a.cost_opt:
        assert kind == "success" and "trifft hier das Optimum" in text and "mehr als das Optimum" not in text
    else:
        assert kind == "info" and "mehr als das Optimum" in text and f"{ev.de(100 * (a.cost_rule - a.cost_opt) / a.cost_opt)} %" in text
    assert f"{len(a.crit)} kritischen Anschlüsse" in text
