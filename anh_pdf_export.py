"""Bericht zum gewählten Störtag als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen, Gedankenstrich, Euro-Zeichen, Emoji und U+2212 nicht)."""
from __future__ import annotations

from fpdf import FPDF

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": ".", "„": '"', "“": '"', "′": "'"}


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_report_pdf(title: str, summary_lines: list, rows: list) -> bytes:
    """Kennzahlen des Störtags und die kritischen Anschlüsse (Zeilen aus `anh_evaluation.connection_rows`)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in summary_lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    heads = [("Halt", 14), ("Linien", 22), ("Gewicht", 18), ("Puffer", 16), ("Plan an", 18), ("Regel", 22), ("Optimum", 22), ("verspätet ab (Regel/Opt.)", 48)]
    pdf.set_font("Helvetica", "B", 8)
    for h, w in heads:
        pdf.cell(w, 6, _clean(h), border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in rows:
        cells = [str(r["station"]), f"L{r['line_a']} -> L{r['line_b']}", str(r["weight"]), f"{r['buffer']} min", str(r["plan_arr"]),
                 "hält" if r["hold_rule"] else "fährt", "hält" if r["hold_opt"] else "fährt", f"{r['dep_delay_rule']} / {r['dep_delay_opt']} min"]
        for c, (_, w) in zip(cells, heads):
            pdf.cell(w, 6, _clean(c), border=1)
        pdf.ln()
    return bytes(pdf.output())
