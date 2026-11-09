"""Anschluss halten oder abfahren - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Diese Demo gehört zur Linie „Takt und Periodizität“ der Konzepte-Reihe, ein Kontrast zum Takt-Suchen: Am Betriebstag wird aus dem Optimierungsproblem eine Regelfrage.
Aufbau nach DEMO-PLAYBOOK §2. Lauffähig mit: streamlit run app.py
"""

import time

import numpy as np
import pandas as pd
import streamlit as st

import anh_constants as C
import anh_evaluation as ev
import anh_exact as AE
import anh_propagate as AP
import anh_results as R
import anh_rules as AR
import anh_scenario as AS
from anh_evaluation import Settings, analyse, build_network, connection_rows, de, de_int, rule_label
from anh_layout import dunkles_design, kopf_css
from anh_pdf_export import generate_report_pdf
from anh_presets import (
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_scen_seed,
    sidebar_presets,
    sync_query_params,
)
from anh_visualization import (
    build_ext,
    build_gap_by_lines,
    build_mcurve,
    build_spread,
    build_takt_bridge,
    build_timeline,
    build_total,
    build_wcurve,
)

st.set_page_config(page_title="Anschluss halten oder abfahren – Sebastian Hanisch", layout="wide")


@st.cache_resource(show_spinner=False, max_entries=6)
def _network(key):
    return build_network(*key)


@st.cache_resource(show_spinner=False, max_entries=12)
def _analysis(settings):
    return analyse(settings, _network(settings.net_key))


@st.cache_data(show_spinner=False)
def _results():
    try:
        return R.load_results()
    except FileNotFoundError:
        return None


def delta_vs_opt(cost, opt):
    """Delta „mein Wert minus Optimum“ (nie umgekehrt); bei Gleichheit neutral statt eines roten Pfeils."""
    if opt is None:
        return {"delta": None}
    d = cost - opt
    if d == 0:
        return {"delta": "±0 gegen Optimum", "delta_color": "off"}
    return {"delta": f"{d:+,}".replace(",", ".") + " gegen Optimum", "delta_color": "inverse"}


def pct(pair, digits=1):
    """Mittel ± Standardfehler als Text mit Dezimalkomma."""
    return f"{de(pair[0], digits)} ± {de(pair[1], digits)} %"


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in anh_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🚆 Anschluss halten oder abfahren")
st.markdown(
    """
Wenn ein Zubringerzug verspätet ist: Soll der **Folgezug warten**, damit die Umsteiger ihn noch erreichen, oder **abfahren**? Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe
und ist ausdrücklich ein **Kontrast**, kein Fix: Der Takt der übrigen Demos der Linie senkt die **Plan-Umsteigezeit** und nimmt dafür Puffer weg. Am Betriebstag wird daraus eine
**Regelfrage**: Hier rechnet ein exaktes Verfahren (CP-SAT) das **Optimum** je Störtag und misst, wie weit eine einfache **Wartezeitregel** davon entfernt bleibt.
Alles gilt für dieses **Modell** mit synthetischen Netzen, nicht für Betriebsdaten. Abgrenzung: `fahrzeitreserve-demo` (eine Strecke, keine Umsteiger), `bunching-demo` (Ringlinie
ohne Anschlüsse) und `warten-oder-fahren-demo` (ein anderes Modell: Warten, um Aufträge zu sammeln).

Wer das Problem zuerst ohne Fachbegriffe verstehen will, öffnet **💬 In einfachen Worten**. Weiter unten: die Kernfrage, fünf Experimente, **🚧 Wo die Annahmen enden** und der Expander **📐 Mathematische Formulierung**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/anschluss-halten-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Ein Zubringerzug ist verspätet, und Umsteiger wollen in den **Folgezug**. Soll er **warten** oder **abfahren**? Wartet er, erreichen die Umsteiger den Anschluss, aber die Fahrgäste an Bord kommen später an. Fährt er ab, bleibt er pünktlich, und die Umsteiger verlieren Zeit. Die Demo rechnet für jeden Störtag das **Optimum**, also die beste Auswahl der gehaltenen Anschlüsse im Rückblick, und misst, wie nah eine einfache **Wartegrenze** daran kommt. Die beste Grenze hängt davon ab, wie viel ein verpasster Anschluss kostet. Ein Takt mit kurzer Planwartezeit macht mehr Anschlüsse kritisch. Die Netze sind erfunden, der Verlust beim Verpassen ist eine Annahme: Die Ergebnisse zeigen Richtung und Größenordnung, keine Betriebsdaten.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/anschluss-halten-erklaert.html)
        """
    )
# erklaerseite:einfach:end

with st.expander("So funktioniert Delay Management", expanded=True):
    mc = ev.mini_costs()
    st.markdown(
        f"""
1. **Ereignisnetz.** Jede Ankunft und Abfahrt ist ein Ereignis mit Planminute. Zwischen Ereignissen liegen Aktivitäten mit einem **Puffer** (Planzeit minus Mindestzeit):
   eine Verspätung $D$ pflanzt sich nur so weit fort, wie der Puffer sie nicht auffängt (max-plus-Rechnung). Fahren, Halten, Wenden und Fahrzeugumlauf sind Aktivitäten.
2. **Anschluss.** Ein Umsteiger braucht mindestens 3 min. Der Folgezug erreicht den Zubringer, wenn seine Abfahrtsverspätung mindestens (Zubringer-Verspätung − Anschlusspuffer) beträgt.
   Ist der Zubringer **über den Puffer hinaus verspätet**, ist der Anschluss **kritisch**: Dann gibt es eine Entscheidung, *halten* oder *abfahren*.
3. **Kosten.** Gemessen in Fahrgastminuten Verspätung am Ziel (Gewichte relativ). Wer den Anschluss erreicht, zahlt seine Verspätung am Ziel, höchstens $M$; wer ihn verpasst, zahlt $M$
   (Annahme: Der Folgezug fährt pünktlich). Halten kostet die Fahrgäste an Bord und alle Folgeanschlüsse des wartenden Zuges.
4. **Beispiel von Hand** (6 Ereignisse, 3 Anschlüsse, $M = 20$, Zubringer 6 und 4 min verspätet): Wenn der Folgezug nie wartet, kostet der Tag **{de_int(mc['never'])}**
   Fahrgastminuten; wartet er auf den ersten Zubringer, **{de_int(mc['c0'])}**; wartet er zusätzlich auch am nächsten Umsteigeort, wieder **{de_int(mc['c0c2'])}**. Das Optimum ist
   **{de_int(mc['opt'])}**: Halten lohnt, aber nur dort, wo wenige Fahrgäste an Bord ein Warten bezahlen.
"""
    )
    st.markdown("**Wer entscheidet worüber?** Die Regeln kennen die Zubringer-Verspätung genau, sehen aber nur den eigenen Anschluss; das Optimum kennt den ganzen Tag im Voraus.")
    st.dataframe(
        pd.DataFrame(
            [
                {"Regel": C.RULE_NAMEN[r], "Erklärung": AR.REGEL_ERKLAERUNG[r], "Sieht": "nur den eigenen Anschluss" if r != "never" and r != "always" else "nichts",
                 "Kennt M": "ja" if r in ("bal", "bal2") else "nein"}
                for r in C.RULES
            ]
        ),
        hide_index=True,
        width="stretch",
    )

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Netz und Takt**")
    lines = st.slider("Linien", *bounds("lines_slider"), key="lines_slider", help="Wie viele Linien das Netz hat (20 Haltestellen, höchstens 6 Halte je Linie).")
    stufe = st.selectbox("Takt", C.STUFEN, key="stufe_select", format_func=C.STUFEN_NAMEN.get,
                         help="Welcher Takt der Linie die Anschlüsse bestimmt:zufällige Phasen, Greedy, Phasen-Optimum oder Phasen mit Aufteilung der Wende-Standzeit.")
    puffer = st.selectbox("Puffer", C.PUFFER, key="puffer_select", format_func=C.PUFFER_NAMEN.get,
                          help="Wie viel Reserve die Fahrten, Halte und Wenden haben, um Verspätungen aufzufangen.")
    net_seed = st.number_input("Zufalls-Seed des Netzes", *bounds("net_seed_input"), key="net_seed_input", step=1)
    st.markdown("**Störtag**")
    k = st.slider("Primärverspätungen", *bounds("k_slider"), key="k_slider", help="Wie viele Abfahrten in den ersten zwei Stunden verspätet starten.")
    hmax = st.slider("Größte Verspätung (min)", *bounds("hmax_slider"), key="hmax_slider", help="Die Höhe jeder Primärverspätung liegt gleichverteilt zwischen 3 min und diesem Wert.")
    scen_seed = st.number_input("Zufalls-Seed des Störtags", *bounds("scen_seed_input"), key="scen_seed_input", step=1)
    st.button("🎲 Neuen Störtag würfeln", width="stretch", on_click=randomize_scen_seed)
    st.markdown("**Entscheidung**")
    M = st.slider("Verlust beim Verpassen M (min)", *bounds("m_slider"), key="m_slider", step=C.M_STEP,
                  help="Annahme: Wer den Anschluss verpasst, verliert genau M Minuten (der Folgezug fährt pünktlich).")
    rule = st.selectbox("Wartezeitregel", C.RULES, key="rule_select", format_func=C.RULE_NAMEN.get, help="Nach welcher Regel der Folgezug entscheidet; das Optimum steht immer daneben.")
    W = st.slider("Schwelle W (min)", *bounds("w_slider"), key="w_slider", disabled=rule not in C.RULES_WITH_W,
                  help="Schwelle der Regeln c_W, p_W, d_W. Ausgegraut bei Regeln ohne Schwelle.")
    folge = st.toggle("Folgezug ebenfalls verspätet", key="folgezug_toggle",
                      help="Erweiterung: Verpassen kostet M plus die Verspätung der nächsten Fahrt derselben Linie am Ziel (Annahme der Messreihe: Folgezug pünktlich).")

sync_query_params({key: st.session_state[key] for key in
                   ("lines_slider", "stufe_select", "puffer_select", "net_seed_input", "k_slider", "hmax_slider", "scen_seed_input", "m_slider", "rule_select", "w_slider")}
                  | {"folgezug_toggle": int(bool(folge))})

settings = Settings(lines=int(lines), stufe=stufe, puffer=puffer, M=int(M), k=int(k), hmax=int(hmax), rule=rule, W=int(W), folgezug=bool(folge),
                    net_seed=int(net_seed), scen_seed=int(scen_seed))
with st.spinner(f"Baut Netz und Takt, rechnet Regel und Optimum (Zeitlimit {C.LIVE_TIME_LIMIT:.0f} s je Störtag) …"):
    a = _analysis(settings)
net = a.network.net
label = rule_label(settings.rule, settings.W)
res = _results()
if res is not None and res["meta"]["generator_hash"] != R.generator_hash():
    st.warning("Die vorgerechnete Messreihe (data/anh_results.json) gehört zu einem älteren Stand des Codes. Die Experimente unten zeigen den alten Stand, bis sie neu erzeugt ist.")

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ein Störtag")
used_note = "" if a.network.seed_used == settings.net_seed else f" (der erste gültige Seed ab {settings.net_seed} ist {a.network.seed_used})"
st.caption(
    f"Netz mit {a.network.n_lines} Linien, {len(net.prim_cand)} möglichen Verspätungsorten, {net.nconn} Anschlüssen im 4-Stunden-Horizont{used_note}; "
    f"{len(a.prim)} Primärverspätungen, davon {len(a.crit)} Anschlüsse kritisch. Takt: {C.STUFEN_NAMEN[settings.stufe]}."
)
m1, m2, m3, m4 = st.columns(4)
fmt = lambda x: "–" if x is None else de_int(x)
# Delta immer als „mein Wert minus Referenz“; die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
m1.metric("Optimum" + ("" if a.opt.proven else " (nicht bewiesen)"), fmt(a.cost_opt), delta="Referenz", delta_color="off", help="Fahrgastminuten Verspätung am Ziel; CP-SAT, binäre Variable je kritischem Anschluss.")
m2.metric(f"Regel {label}", fmt(a.cost_rule), **delta_vs_opt(a.cost_rule, a.cost_opt))
m3.metric("Nie halten", fmt(a.cost_never), **delta_vs_opt(a.cost_never, a.cost_opt))
m4.metric("Immer halten", fmt(a.cost_always), **delta_vs_opt(a.cost_always, a.cost_opt))
rows = connection_rows(a)
if rows:
    st.plotly_chart(build_timeline(rows, label), width="stretch", key="timeline_chart")
    st.caption(
        f"Kritische Anschlüsse (die {len(rows)} mit dem größten Umsteigergewicht von {len(a.crit)}). Grau: Plan-Ankunft des Zubringers und Plan-Abfahrt des Folgezugs. "
        f"Punkte: tatsächliche Abfahrt des Folgezugs unter der Regel {label} (orange) und unter dem Optimum (grün); gefüllt = gehalten. Rotes Kreuz: Regel und Optimum entscheiden verschieden."
    )
    with st.expander("Tabelle der kritischen Anschlüsse"):
        st.dataframe(
            pd.DataFrame(rows).rename(columns={"station": "Halt", "line_a": "Zubringer-Linie", "line_b": "Folgezug-Linie", "weight": "Gewicht", "buffer": "Puffer (min)",
                                               "plan_arr": "Plan an (min)", "plan_dep": "Plan ab (min)", "arr_delay": "Zubringer verspätet (min, Regel)",
                                               "dep_delay_rule": "Folgezug verspätet (min, Regel)", "dep_delay_opt": "Folgezug verspätet (min, Optimum)",
                                               "hold_rule": "gehalten (Regel)", "hold_opt": "gehalten (Optimum)", "caught_rule": "erreicht (Regel)",
                                               "caught_opt": "erreicht (Optimum)", "c": "Nr."}),
            hide_index=True,
            width="stretch",
        )
    summary = [f"Netz: {a.network.n_lines} Linien, Takt {C.STUFEN_NAMEN[settings.stufe]}, Puffer {settings.puffer}, M = {settings.M} min.",
               f"Regel {label}: {fmt(a.cost_rule)} Fahrgastminuten; Optimum: {fmt(a.cost_opt)}; nie halten: {fmt(a.cost_never)}; immer halten: {fmt(a.cost_always)}.",
               f"{len(a.crit)} kritische Anschlüsse, {len(a.prim)} Primärverspätungen. Modell, keine Betriebsdaten."]
    st.download_button("📄 Bericht als PDF", generate_report_pdf("Anschluss halten oder abfahren", summary, rows), file_name="anschluss-halten.pdf", mime="application/pdf")
else:
    st.info("Auf diesem Störtag ist kein Anschluss kritisch. Ein anderer Zufalls-Seed des Störtags oder mehr und größere Primärverspätungen erzeugen Entscheidungen.")

# --- Kernfrage -----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage: Wie viel gewinnt man, wenn man das Optimum rechnet statt eine einfache Regel anzuwenden?")
kind, text = ev.verdict_rule(a, label)
getattr(st, kind)(text)
if res is not None:
    st.markdown("**Über die ganze Messreihe** (vorgerechnet, normale Puffer, M = 60 min, Phasen-Optimum):")
    getattr(st, "info")(ev.verdict_kern(R.core_stats(res))[1])
st.markdown("---")

# --- E1 ------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 E1: Wohin wandert das beste W?")
st.caption("Die Regel p_W lässt den Folgezug warten, solange er dadurch höchstens W Minuten verspätet abfährt. Welches W am besten ist, hängt von M ab, und im Einsatz kennt niemand M genau.")
if res is None:
    st.error("data/anh_results.json fehlt: die vorgerechnete Messreihe ist nicht erzeugt (tools/build_results.py).")
else:
    mrows = R.mkurve_rows(res)
    st.plotly_chart(build_mcurve(mrows), width="stretch", key="mcurve_chart")
    m_pick = st.select_slider("M für die Kurve von p_W (min)", options=res["meta"]["MS"], value=60, key="e1_m")
    row = next(r for r in mrows if r["M"] == m_pick)
    st.plotly_chart(build_wcurve(row), width="stretch", key="wcurve_chart")
    st.dataframe(
        pd.DataFrame([{"M (min)": r["M"], "Optimum unter „nie halten“ (%, Basis: nie halten)": round(r["below_never"], 1), "bestes W (min)": r["w_best"],
                       "Abstand bei bestem W (%, Mittel ± SE)": pct(r["gap_best"]), "Abstand bei W = 5 (%)": pct(r["gap_w5"]), "Immer halten (%)": pct(r["gap_always"]),
                       "bestes W je Netz (kleinstes / Median / größtes)": f"{r['w_net_min']} / {de(r['w_net_median'], 0)} / {r['w_net_max']}"} for r in mrows]),
        hide_index=True,
        width="stretch",
    )
    kind, text = ev.verdict_mkurve(mrows)
    getattr(st, kind)(text)
    st.caption("Der Abstand ist je Netz das Verhältnis der Kosten der Regel zu den Kosten des Optimums über 100 Störtage (minus 1); Mittel über 28 Netze, SE = Standardfehler. "
               "Das beste W ist im Rückblick gewählt (Minimum über W auf denselben Störtagen).")
st.markdown("---")

# --- E2 ------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 E2: Der bessere Takt, die knapperen Anschlüsse")
st.caption("Die Takt-Stufen der Linie (zufällige Phasen, Greedy, Phasen-Optimum, Phasen mit Aufteilung der Wende-Standzeit) senken die Plan-Umsteigezeit. "
           "Hier misst die Demo, was das für die Puffer der Anschlüsse bedeutet: dieselben Netze und Störtage, nur der Takt wechselt.")
if res is not None:
    trows = R.takt_rows(res)
    st.plotly_chart(build_takt_bridge(trows, C.STUFEN_NAMEN), width="stretch", key="takt_chart")
    netto = R.takt_netto(res, "zufall", "split")
    st.dataframe(
        pd.DataFrame([{"Takt": C.STUFEN_NAMEN[r["stufe"]], "Plan-Umsteigezeit (min je Umsteiger)": round(r["plan_wait"], 1), "Umsteigergewicht mit Puffer ≤ 5 min (Anteil)": round(r["share_le5"], 3),
                       "kritische Anschlüsse je Störtag": round(r["ncrit"], 1), "bestes W": r["w_best"], "Abstand bei bestem W (%)": pct(r["gap_best"]),
                       "Gegenrechnung (%)": pct(r["gap_bal2"]), "Immer halten (%)": pct(r["gap_always"])} for r in trows]),
        hide_index=True,
        width="stretch",
    )
    f = st.slider("Störtage je Horizont (Annahme)", 0.5, 20.0, 5.0, 0.5, key="e2_f",
                  help="Wie oft ein Störtag der angenommenen Art (1 bis 8 Primärverspätungen von 3 bis 30 min) im 4-Stunden-Horizont vorkommt. Nur die Bilanz hängt daran.")
    st.plotly_chart(build_total(trows, C.STUFEN_NAMEN, f), width="stretch", key="total_chart")
    kind, text = ev.breakeven_verdict(netto, f)
    getattr(st, kind)(text)
    kind, text = ev.verdict_takt({r["stufe"]: r for r in trows}, netto)
    getattr(st, kind)(text)
    st.caption("Bilanz je Netz gepaart: Plan-Umsteigezeit P = Summe über alle Anschlüsse im Horizont von Gewicht · (Puffer + 3 min); Verspätungskosten V = mittlere Kosten des Optimums je Störtag "
               "(alle Fahrgäste, M = 60). Nicht getrennt: Die Aufteilung der Wende-Standzeit verändert auch die Wendepuffer, nicht nur die Umsteigepuffer.")
st.markdown("---")

# --- E3 ------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 E3: Regel gegen Optimum im Einzelfall")
st.caption("Im Netz-Mittel liegt die beste feste Regel bei M = 60 (`p_5`, normale Puffer) 3,1 ± 0,4 % über dem Optimum (28 Netze, Standardfehler; Kernfrage oben). Je Störtag streut die Lücke stark: Der Mittelwert verbirgt, wie oft die Regel genau das Optimum trifft und wie schlecht sie in den schlechtesten Fällen ist.")
if res is not None:
    exp = "main" if st.radio("Puffer", ["normal", "knapp"], horizontal=True, key="e3_exp", format_func=lambda x: C.PUFFER_NAMEN[x].split(" (")[0]) == "normal" else "knapp"
    w_all = R.best_w(res, exp)[0]
    rules_e3 = {"p_5": "p5", f"p_{w_all} (bestes W im Rückblick)": f"p{w_all}", "Gegenrechnung (bal2)": "bal2", "nie halten": "never", "immer halten": "always"}
    stats = {name: R.scenario_stats(res, exp, r) for name, r in rules_e3.items()}
    stats_dec = {name: R.scenario_stats(res, exp, r, decided_only=True) for name, r in rules_e3.items()}
    st.plotly_chart(build_spread({n: R.scenario_gaps(res, exp, r) for n, r in rules_e3.items() if r in ("p5", "bal2", f"p{w_all}", "always")}), width="stretch", key="spread_chart")
    st.dataframe(
        pd.DataFrame([{"Regel": n, "Störtage": s["n"], "Anteil gleich Optimum (%)": round(100 * s["share_equal"], 1),
                       "dito, nur Störtage mit kritischem Anschluss (%)": round(100 * stats_dec[n]["share_equal"], 1), "Median der Lücke (%)": round(s["median"], 1),
                       "P90 (%)": round(s["p90"], 1), "P99 (%)": round(s["p99"], 1), "Maximum (%)": round(s["max"], 1)} for n, s in stats.items()]),
        hide_index=True,
        width="stretch",
    )
    n_dec, n_ok, n_open = R.proven_counts(res, exp)
    st.caption(f"Basis jeder Lücke: Kosten des Optimums des Störtags. {n_dec} Störtage mit mindestens einem kritischen Anschluss, davon {n_ok} mit bewiesenem Optimum, {n_open} nicht bewiesen "
               f"(Zeitlimit {res['meta']['time_limit_s']:.0f} s in der Messreihe). Störtage ohne kritischen Anschluss zählen als „gleich“, soweit ihre Kosten größer als 0 sind; die Spalte „nur Störtage mit kritischem Anschluss“ lässt sie weg.")
    st.markdown("**Live auf dem gewählten Netz:** 100 Störtage (1 bis 8 Primärverspätungen), gleicher Takt, gleiche Puffer, gleiches M.")
    if st.button("▶️ 100 Störtage auf diesem Netz rechnen", key="live_run_button"):
        t_end = time.perf_counter() + C.LIVE_RUN_BUDGET
        sums = {"opt": 0, "never": 0, "always": 0, "p5": 0, "bal2": 0, f"p{settings.W}": 0}
        done = unproven = 0
        with st.spinner(f"Rechnet {C.LIVE_RUN_SCENARIOS} Störtage, höchstens {C.LIVE_RUN_BUDGET:.0f} s …"):
            for s in range(C.LIVE_RUN_SCENARIOS):
                if time.perf_counter() > t_end:
                    break
                prim = AS.make_scenario(net, a.network.seed_used * 1000 + s)
                opt = AE.solve_optimum(net, prim, settings.M, C.LIVE_TIME_LIMIT, follow=settings.folgezug)
                unproven += 0 if opt.proven else 1
                sums["opt"] += opt.cost
                for name in list(sums)[1:]:
                    D, _ = AR.run_rule(net, prim, settings.M, AR.parse_rule(name))
                    sums[name] += AP.total_cost(net, D, settings.M, settings.folgezug)
                done += 1
        st.session_state["live_run"] = {"key": settings.net_key + (settings.M, settings.folgezug), "sums": sums, "done": done, "unproven": unproven}
    live = st.session_state.get("live_run")
    if live and live["key"] == settings.net_key + (settings.M, settings.folgezug) and live["sums"]["opt"] > 0:
        sums = live["sums"]
        st.dataframe(
            pd.DataFrame([{"Regel": n, "Kosten (Fahrgastminuten)": de_int(v), "Abstand zum Optimum (%, Basis: Optimum)": round(100 * (v / sums["opt"] - 1), 1)} for n, v in sums.items()]),
            hide_index=True,
            width="stretch",
        )
        st.caption(f"{live['done']} Störtage gerechnet, {live['unproven']} davon mit nicht bewiesenem Optimum (Zeitlimit {C.LIVE_TIME_LIMIT:.0f} s je Störtag). "
                   "Ein Netz, kein Netz-Mittel: Einzelne Netze weichen vom Mittel der Messreihe ab.")
st.markdown("---")

# --- E4 ------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 E4: Gegenrechnung im eigenen Zug")
st.caption("Die Gegenrechnung wägt im wartenden Zug ab: Gewinn der Umsteiger gegen die Kosten der Fahrgäste an Bord. Sie sieht aber nur den eigenen Zug, nicht die Folgeverspätungen anderer Züge. "
           "Dort, wo Verspätungen sich weit fortpflanzen (knappe Puffer, Netze mit vielen Linien), sollte sie schlechter werden; das prüft dieses Experiment.")
if res is not None:
    exp4 = "main" if st.radio("Puffer", ["normal", "knapp"], horizontal=True, key="e4_exp", format_func=lambda x: C.PUFFER_NAMEN[x].split(" (")[0]) == "normal" else "knapp"
    ls = R.lines_of(res, exp4)
    w4 = R.best_w(res, exp4)[0]
    series = {"Gegenrechnung (bal2)": "bal2", f"p_{w4} (bestes W insgesamt)": f"p{w4}", **({"p_5": "p5"} if w4 != 5 else {}), "nie halten": "never", "immer halten": "always"}
    vals = {n: [R.gap_summary(res, exp4, r, n_lines=l)[0] for l in ls] for n, r in series.items()}
    st.plotly_chart(build_gap_by_lines(ls, {n: v for n, v in vals.items() if n != "immer halten"}), width="stretch", key="lines_chart")
    st.dataframe(
        pd.DataFrame([{"Linien": l, **{n: f"{de(np.mean(g))} ± {de(np.std(g, ddof=1))}" for n, r in series.items() for g in [R.gap_per_net(res, exp4, r, n_lines=l)]}} for l in ls]),
        hide_index=True,
        width="stretch",
    )
    st.caption("Abstand zum Optimum in % (Basis: Optimum); Mittel ± Standardabweichung über die 4 Netze je Linienzahl. „Immer halten“ steht nur in der Tabelle. "
               "Der Mechanismus (Folgeverspätungen dritter Züge) ist hier nicht durch einen Eingriff geprüft; die Messung zeigt den Zusammenhang, nicht seine Ursache.")
st.markdown("---")

# --- E5 ------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 E5: Folgezug ebenfalls verspätet")
st.caption("Das Grundmodell lässt den Folgezug pünktlich fahren. In der Erweiterung kostet das Verpassen M plus die Verspätung D′ der nächsten Fahrt derselben Linie am Ziel "
           "(aus derselben Fortpflanzung); das Optimum kennt D′, die Regeln nicht. Schalter in der Seitenleiste: „Folgezug ebenfalls verspätet“.")
if res is not None:
    labels5, base5, ext5 = [], [], []
    for exp5, name5 in (("main", "normal"), ("knapp", "knapp")):
        w5 = R.best_w(res, exp5)[0]
        for r, rname in (("never", "nie"), ("p5", "p_5"), (f"p{w5}", f"p_{w5}"), ("bal2", "Gegenr.")):
            labels5.append(f"{rname} ({name5})")
            base5.append(R.gap_summary(res, exp5, r)[0])
            ext5.append(R.gap_summary(res, exp5, r, key="ext")[0])
    st.plotly_chart(build_ext(labels5, base5, ext5), width="stretch", key="ext_chart")
    dm = np.mean([x for r in res["main"] if r for x in r["dprime_mean"]])
    dp = 100 * np.mean([x for r in res["main"] if r for x in r["dprime_pos"]])
    miss = 100 * np.mean([r["miss_share"] for r in res["main"] if r])
    st.caption(f"Wie stark die Erweiterung wirkt, hängt am Netz: Im Mittel ist D′ {de(dm, 2)} min (gewichtet über die Umsteiger, bei „nie halten“); {de(dp)} % des Umsteigergewichts haben D′ > 0, "
               f"und {de(miss)} % des Umsteigergewichts haben keine nächste Fahrt im 4-Stunden-Horizont (dort gilt D′ = 0). Der Test ist deshalb schwächer, als er klingt.")
st.markdown("---")

# --- Grenzen -------------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(C.ASSUMPTIONS_MARKDOWN)
st.markdown("---")


with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/anschluss-halten-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind ein Ereignisnetz mit Plan- und Mindestzeiten, Primärverspätungen an einigen Abfahrten, die Anschlüsse mit den Gewichten ihrer Umsteiger und der Verlust $M$ beim Verpassen. Gesucht ist die Menge der gehaltenen Anschlüsse mit den kleinsten Kosten in Fahrgastminuten Verspätung am Ziel.

| Symbol | Bedeutung |
|---|---|
| $e$ | Ereignis (Ankunft oder Abfahrt) mit Planminute |
| $p_{se}$ | Puffer der Aktivität $(s, e)$: Planzeit minus Mindestzeit |
| $\delta_e$ | Primärverspätung des Ereignisses $e$ (null, wenn keine vorliegt) |
| $D_e$ | Verspätung des Ereignisses $e$ in Minuten |
| $c = (A_c, B_c)$ | Anschluss: Zubringer-Ankunft $A_c$ und Folgezug-Abfahrt $B_c$ |
| $p_c$ | Puffer des Anschlusses $c$ |
| $y_c \in \{0, 1\}$ | Anschluss $c$ wird gehalten (1) oder nicht (0) |
| $w_g$, $z_g$ | Gewicht (Fahrgäste) der Gruppe $g$ und ihr Zielereignis |
| $M$ | Verlust beim Verpassen in Minuten (Annahme) |
| $\text{need}$, $b$, $\text{extra}$ | nötige Abfahrtsverspätung des Folgezugs, seine ohnehin vorhandene Verspätung und die zusätzliche Wartezeit $\text{need} - b$ |
| $W$ | Schwelle der Regeln $c_W$ und $p_W$ in Minuten |
| $p_W$, $c_W$ | Namen von Regeln, nicht der Puffer $p_c$ und nicht der Anschluss $c$ (die Buchstaben $p$ und $c$ haben hier zwei Bedeutungen) |
| $n_{\text{an Bord}}$ | Fahrgäste an Bord des Folgezugs, einschließlich der Umsteiger $w_c$ dieses Anschlusses |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/anschluss-halten-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        r"""
**Zu den Symbolen.** Zwei Buchstaben der Tabelle haben eine zweite Bedeutung: $p$ ist der Puffer ($p_{se}$, $p_c$), aber auch die Regel $p_W$ (Schwelle auf die nötige Abfahrtsverspätung); $c$ ist ein Anschluss ($c = (A_c, B_c)$),
aber auch die Regel $c_W$ (Schwelle auf die zusätzliche Wartezeit). Die Rechnung ist davon nicht berührt: Ein Puffer trägt als Index eine Aktivität oder einen Anschluss, eine Regel die Schwelle $W$.

**Fortpflanzung.** Ohne Halten und für feste $y$:

$$D_e = \max\Big(\delta_e,\ \max_{(s,e)} (D_s - p_{se}),\ \max_{c:\,B_c = e,\ y_c = 1} (D_{A_c} - p_c)\Big)$$

**Erreicht** ist ein Anschluss, wenn $D_{B_c} \ge D_{A_c} - p_c$.

**Kosten.** Direkte Gruppen zahlen $w_g D_{z_g}$; Umsteiger zahlen $w_g \min(D_{z_g}, M)$, wenn sie den Anschluss erreichen, sonst $w_g M$ (Erweiterung: $M + D'_g$ statt $M$):

$$\min_{y}\ \sum_{g\ \text{direkt}} w_g D_{z_g} + \sum_{g\ \text{Umsteiger}} w_g \cdot \begin{cases} \min(D_{z_g}, M) & \text{erreicht} \\ M & \text{verpasst} \end{cases}$$

Das ist ein gemischt-ganzzahliges Programm mit einer Binärvariable je kritischem Anschluss (CP-SAT); die Verspätungen $D_e$ sind ganzzahlig und nach unten durch die Fortpflanzung beschränkt.

**Regeln.** Sei $\text{need} = D_{A_c} - p_c$ die Abfahrtsverspätung, die der Folgezug annehmen müsste, $b$ die Verspätung, die er ohnehin hat, und $\text{extra} = \text{need} - b$.
$c_W$ hält bei $\text{extra} \le W$, $p_W$ bei $\text{need} \le W$. Die Gegenrechnung hält, wenn $w_c M \ge \text{extra} \cdot (n_{\text{an Bord}} - w_c)$ (verfeinert: $w_c \max(0, M - \text{need})$ statt $w_c M$).

**Literatur.** Zur Einordnung (Delay Management als gemischt-ganzzahliges Programm auf dem Ereignis-Aktivitäten-Netz, NP-schwer): Die Quellenlage ist in dieser Demo nicht im Volltext geprüft, deshalb nennt sie hier bewusst keine Autoren und Jahre.
        """
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html)."
)
