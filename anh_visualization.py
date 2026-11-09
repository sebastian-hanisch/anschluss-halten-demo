"""Plotly-Abbildungen (alle Achsen gesperrt, damit Touch-Scrollen auf der Seite nicht am Diagramm hängen bleibt)."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

import anh_constants as C

# Klassen der Lücke je Störtag (Prozent der Optimumskosten): (Beschriftung, untere Grenze exklusiv, obere Grenze inklusiv); „gleich“ = höchstens 1e-9
SPREAD_CLASSES = [("gleich", None, None), ("bis 1 %", 1e-9, 1), ("1 bis 2 %", 1, 2), ("2 bis 5 %", 2, 5), ("5 bis 10 %", 5, 10), ("10 bis 20 %", 10, 20),
                  ("20 bis 50 %", 20, 50), ("50 bis 100 %", 50, 100), ("über 100 %", 100, float("inf"))]
LAYOUT = dict(margin=dict(l=10, r=10, t=40, b=40), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))


def _lock(fig, height=380):
    fig.update_layout(height=height, **LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def build_timeline(rows: list, rule_label: str) -> go.Figure:
    """Zeitdiagramm der kritischen Anschlüsse: je Zeile ein Anschluss (nach Umsteigegewicht). Grau: Planzeit der Zubringer-Ankunft und der Folgezug-Abfahrt.
    Punkte: tatsächliche Abfahrt des Folgezugs unter der Regel (orange) und unter dem Optimum (grün); gefüllt = Anschluss gehalten, hohl = nicht gehalten.
    Rot umrandet: Regel und Optimum entscheiden verschieden."""
    fig = go.Figure()
    n = len(rows)
    ys = list(range(n))[::-1]
    for y, r in zip(ys, rows):
        fig.add_trace(go.Scatter(x=[r["plan_arr"], r["plan_dep"]], y=[y, y], mode="lines+markers", line=dict(color=C.COLOR_PLAN, width=2),
                                 marker=dict(size=[8, 8], symbol=["triangle-right", "line-ns-open"], color=C.COLOR_PLAN), showlegend=False, hoverinfo="skip"))
    for key, name, color, dy in (("rule", rule_label, C.COLOR_RULE, 0.14), ("opt", "Optimum", C.COLOR_OPT, -0.14)):
        xs = [r["plan_dep"] + r[f"dep_delay_{key}"] for r in rows]
        held = [r[f"hold_{key}"] for r in rows]
        text = [f"Haltestelle {r['station']}, Linie {r['line_a']} → {r['line_b']}, Gewicht {r['weight']}, Puffer {r['buffer']} min<br>"
                f"Abfahrt {r[f'dep_delay_{key}']} min verspätet, {'gehalten' if r[f'hold_{key}'] else 'nicht gehalten'}, "
                f"{'erreicht' if r[f'caught_{key}'] else 'verpasst'}" for r in rows]
        fig.add_trace(go.Scatter(x=xs, y=[y + dy for y in ys], mode="markers", name=name, text=text, hoverinfo="text",
                                 marker=dict(size=11, color=[color if h else "rgba(0,0,0,0)" for h in held], line=dict(color=color, width=2))))
    diff = [(y, r) for y, r in zip(ys, rows) if r["hold_rule"] != r["hold_opt"]]
    if diff:
        fig.add_trace(go.Scatter(x=[max(r["plan_dep"] + r["dep_delay_rule"], r["plan_dep"] + r["dep_delay_opt"]) + 3 for _, r in diff], y=[y for y, _ in diff], mode="markers",
                                 name="Entscheidung weicht ab", marker=dict(symbol="x", size=10, color="#c0392b"), hoverinfo="skip"))
    fig.update_yaxes(tickmode="array", tickvals=ys, ticktext=[f"Halt {r['station']}: L{r['line_a']}→L{r['line_b']}" for r in rows], range=[-0.8, max(n - 0.2, 0.8)])
    fig.update_xaxes(title="Minuten seit Planbeginn")
    return _lock(fig, height=max(260, 34 * n + 120))


def build_mcurve(rows: list) -> go.Figure:
    """E1: bestes W gegen M, Abstand zum Optimum bei bestem W und bei festem W = 5 (Netz-Mittel)."""
    fig = go.Figure()
    ms = [r["M"] for r in rows]
    fig.add_trace(go.Scatter(x=ms, y=[r["w_best"] for r in rows], mode="lines+markers", name="bestes W (Minuten, linke Achse)", line=dict(color=C.COLOR_OPT), yaxis="y"))
    fig.add_trace(go.Scatter(x=ms, y=[r["gap_best"][0] for r in rows], mode="lines+markers", name="Abstand bei bestem W (%, rechts)", line=dict(color=C.COLOR_BLUE, dash="dot"), yaxis="y2"))
    fig.add_trace(go.Scatter(x=ms, y=[r["gap_w5"][0] for r in rows], mode="lines+markers", name="Abstand bei festem W = 5 (%, rechts)", line=dict(color=C.COLOR_RULE, dash="dash"), yaxis="y2"))
    fig.update_layout(yaxis=dict(title="bestes W (min)", rangemode="tozero"), yaxis2=dict(title="Abstand zum Optimum (%)", overlaying="y", side="right", rangemode="tozero"),
                      xaxis=dict(title="Verlust beim Verpassen M (min)", tickvals=ms))
    return _lock(fig)


def build_wcurve(row: dict) -> go.Figure:
    """E1: Abstand der Regel p_W zum Optimum gegen W für ein M (Netz-Mittel)."""
    ws = sorted(row["gap_p"])
    fig = go.Figure(go.Scatter(x=ws, y=[row["gap_p"][w] for w in ws], mode="lines+markers", line=dict(color=C.COLOR_BLUE), name="p_W"))
    fig.add_vline(x=row["w_best"], line=dict(color=C.COLOR_OPT, dash="dot"), annotation_text=f"bestes W = {row['w_best']}", annotation_position="top")
    fig.update_layout(xaxis=dict(title="Schwelle W (min)", tickvals=ws), yaxis=dict(title="Abstand zum Optimum (%)", rangemode="tozero"), showlegend=False)
    return _lock(fig, 320)


def build_takt_bridge(rows: list, names: dict) -> go.Figure:
    """E2: je Takt-Stufe die Plan-Umsteigezeit (Balken, links) und die kritischen Anschlüsse je Störtag (Linie, rechts)."""
    labels = [names[r["stufe"]] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[r["plan_wait"] for r in rows], name="Plan-Umsteigezeit (min je Umsteiger, links)", marker_color=C.COLOR_BLUE, yaxis="y"))
    fig.add_trace(go.Scatter(x=labels, y=[r["ncrit"] for r in rows], mode="lines+markers", name="kritische Anschlüsse je Störtag (rechts)", line=dict(color=C.COLOR_RULE), yaxis="y2"))
    fig.update_layout(yaxis=dict(title="min", rangemode="tozero"), yaxis2=dict(title="kritische Anschlüsse", overlaying="y", side="right", rangemode="tozero"))
    return _lock(fig)


def build_total(rows: list, names: dict, f: float) -> go.Figure:
    """E2: Gesamtkosten je Horizont P + f · V je Takt-Stufe (Einheit Gewicht mal Minuten, Netz-Mittel)."""
    labels = [names[r["stufe"]] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[r["P"] for r in rows], name="Plan-Umsteigezeit P", marker_color=C.COLOR_BLUE))
    fig.add_trace(go.Bar(x=labels, y=[f * r["V"] for r in rows], name=f"Verspätungskosten f · V (f = {f:g})".replace(".", ","), marker_color=C.COLOR_RULE))
    fig.update_layout(barmode="stack", yaxis=dict(title="Gewicht · Minuten je Horizont", rangemode="tozero"))
    return _lock(fig)


def build_spread(gaps_by_rule: dict) -> go.Figure:
    """E3: Verteilung der Lücke zum Optimum je Störtag (Prozent der Optimumskosten), eine Spur je Regel, logarithmische Klassen ab 0."""
    fig = go.Figure()
    classes = SPREAD_CLASSES
    for (name, gaps), color in zip(gaps_by_rule.items(), (C.COLOR_RULE, C.COLOR_BLUE, C.COLOR_ALWAYS, C.COLOR_NEVER)):
        g = np.asarray(gaps)
        share = [100 * float(np.mean((g > lo) & (g <= hi))) if lo is not None else 100 * float(np.mean(g <= 1e-9)) for _, lo, hi in classes]
        fig.add_trace(go.Bar(x=[label for label, _, _ in classes], y=share, name=name, marker_color=color))
    fig.update_layout(barmode="group", yaxis=dict(title="Anteil der Störtage (%)"), xaxis=dict(title="Lücke zum Optimum je Störtag"))
    return _lock(fig)


def build_gap_by_lines(lines: list, series: dict) -> go.Figure:
    """E4: Abstand zum Optimum gegen die Linienzahl (Netz-Mittel über 4 Netze je Linienzahl); `series` = {Name: [Werte]}."""
    fig = go.Figure()
    colors = (C.COLOR_RULE, C.COLOR_BLUE, C.COLOR_ALWAYS, C.COLOR_OPT, C.COLOR_NEVER)
    for (name, vals), color in zip(series.items(), colors):
        fig.add_trace(go.Scatter(x=lines, y=vals, mode="lines+markers", name=name, line=dict(color=color)))
    fig.update_layout(xaxis=dict(title="Linien im Netz", tickvals=lines), yaxis=dict(title="Abstand zum Optimum (%)", rangemode="tozero"))
    return _lock(fig)


def build_ext(labels: list, base: list, ext: list) -> go.Figure:
    """E5: Abstand zum Optimum je Regel im Grundmodell und in der Erweiterung (Folgezug ebenfalls verspätet)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=base, name="Grundmodell: Verlust M", marker_color=C.COLOR_BLUE))
    fig.add_trace(go.Bar(x=labels, y=ext, name="Erweiterung: Verlust M + D′", marker_color=C.COLOR_RULE))
    fig.update_layout(barmode="group", yaxis=dict(title="Abstand zum Optimum (%)", rangemode="tozero"))
    return _lock(fig, 340)
