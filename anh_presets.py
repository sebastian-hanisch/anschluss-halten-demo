"""Permalink (Begrenzen), Presets und Zufalls-Seed-Buttons (Standardmuster aus dem Demo-Portfolio).

Die Regler der Seitenleiste schreiben ihre Werte unter den Schlüsseln aus `SETTING_SPECS`; Presets und Permalink setzen genau diese Schlüssel. Jeder Regler
wird in jedem Lauf gezeichnet (der Schwellenregler W ist bei Regeln ohne Schwelle ausgegraut, nicht ausgeblendet), damit sein Zustand nie verloren geht.
"""

import random
from dataclasses import dataclass

import streamlit as st

import anh_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: object
    default: object
    lo: float | None = None
    hi: float | None = None
    options: tuple | None = None


def _bool(text):
    return str(text).lower() in ("1", "true", "ja", "yes")


SETTING_SPECS = {
    "lines_slider": SettingSpec("lines", int, C.DEFAULT_LINES, C.LINES_MIN, C.LINES_MAX),
    "stufe_select": SettingSpec("takt", str, C.DEFAULT_STUFE, options=C.STUFEN),
    "puffer_select": SettingSpec("puffer", str, C.DEFAULT_PUFFER, options=C.PUFFER),
    "net_seed_input": SettingSpec("netz", int, C.DEFAULT_NET_SEED, 0, C.SEED_MAX),
    "k_slider": SettingSpec("k", int, C.DEFAULT_K, C.K_MIN, C.K_MAX),
    "hmax_slider": SettingSpec("hmax", int, C.DEFAULT_HMAX, C.HMAX_MIN, C.HMAX_MAX),
    "scen_seed_input": SettingSpec("tag", int, C.DEFAULT_SCEN_SEED, 0, C.SEED_MAX),
    "m_slider": SettingSpec("m", int, C.DEFAULT_M, C.M_MIN, C.M_MAX),
    "rule_select": SettingSpec("regel", str, C.DEFAULT_RULE, options=C.RULES),
    "w_slider": SettingSpec("w", int, C.DEFAULT_W, C.W_MIN, C.W_MAX),
    "folgezug_toggle": SettingSpec("folge", _bool, False, options=(False, True)),
}
PRESET_KEYS = {"lines": "lines_slider", "stufe": "stufe_select", "puffer": "puffer_select", "net_seed": "net_seed_input", "k": "k_slider", "hmax": "hmax_slider",
               "scen_seed": "scen_seed_input", "M": "m_slider", "rule": "rule_select", "W": "w_slider", "folgezug": "folgezug_toggle"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def clamp_value(spec: SettingSpec, value):
    """Wert auf die Grenzen bzw. die erlaubten Optionen des Reglers begrenzen; ungültige Optionen fallen auf den Standard zurück."""
    if spec.options is not None:
        return value if value in spec.options else spec.default
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    return value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            st.session_state[state_key] = clamp_value(spec, value)
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen Standardwert) mit dem Session State."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_scen_seed():
    st.session_state["scen_seed_input"] = random.randint(0, C.SEED_MAX)
