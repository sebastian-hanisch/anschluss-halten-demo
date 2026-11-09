"""Fahrplanmodell des Takts: Linien, Ereigniszeiten im Takt, Wartezeit am Umstieg.

aus taktfahrplan-demo (tkt_timetable.py), angepasst: nur die hier gebrauchten Einheiten; die Ableitung der Umsteigeaktivitäten steht in
`anh_network.py` (eine einzige Ableitung für Takt und Ereignisnetz). Jede Linie fährt in beide Richtungen im Takt T. Ereignisse =
Ankunft/Abfahrt je Haltestelle und Richtung. Kein Zufall, kein Zustand.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Line:
    stops: list          # Haltestellen-Indizes in Reihenfolge
    run: list            # Fahrzeit (Minuten) je Abschnitt k: stops[k] -> stops[k+1]


@dataclass
class Instance:
    T: int
    lines: list
    transfers: dict      # (la, da, ka, lb, db, kb) -> Gewicht; Ankunft (la,da,ka) -> Abfahrt (lb,db,kb)
    dwell: int = 2
    tmin: int = 4
    transfer_min: int = 3


def turn_slack(line: Line, T: int, dwell: int, tmin: int) -> int:
    """Wartezeit an den Endpunkten, die der Zyklus braucht, um ein Vielfaches von T zu werden."""
    m = len(line.stops) - 1
    c0 = 2 * sum(line.run) + 2 * dwell * (m - 1) + 2 * tmin
    return (-c0) % T


def fixed_line_times(line: Line, T: int, dwell: int, tmin: int, offset: int, split: int | None = None, extra: int = 0):
    """Absolute Minuten aller Ereignisse einer Linie bei fester Haltezeit; Rückgabe (dict, Zyklusdauer).

    `split` = Standzeit-Anteil am Ende der Hinfahrt (None: Schlupf halbiert), `extra` = Zusatzzüge (hier immer 0)."""
    m = len(line.stops) - 1
    slack = turn_slack(line, T, dwell, tmin) + T * extra
    s_end = slack // 2 if split is None else split
    turn_end, turn_start = tmin + s_end, tmin + slack - s_end
    ev = {}
    t = offset
    ev[("dep", "f", 0)] = t
    for k in range(1, m + 1):
        t += line.run[k - 1]
        ev[("arr", "f", k)] = t
        if k < m:
            t += dwell
            ev[("dep", "f", k)] = t
    t += turn_end
    ev[("dep", "b", m)] = t
    for k in range(m - 1, -1, -1):
        t += line.run[k]
        ev[("arr", "b", k)] = t
        if k > 0:
            t += dwell
            ev[("dep", "b", k)] = t
    cycle = t + turn_start - offset
    return ev, cycle


def direction(pos_from: int, pos_to: int) -> str:
    return "f" if pos_to > pos_from else "b"


def opposite(d: str) -> str:
    return "b" if d == "f" else "f"


def run_between(line: Line, a: int, b: int) -> int:
    lo, hi = min(a, b), max(a, b)
    return sum(line.run[lo:hi])


def wait_time(arr_min: int, dep_min: int, mt: int, T: int) -> int:
    """Umsteigezeit inkl. Mindestzeit: kleinste Zahl >= mt, die zu (dep - arr) mod T passt."""
    return (dep_min - arr_min - mt) % T + mt
