"""Takt-Stufen der Linie: zufällige Phasen, Greedy, Phasen-Optimum, Phasen + Aufteilung der Wende-Standzeit.

aus taktfahrplan-demo (tkt_search.py), angepasst: ohne Zusatzzüge und ohne Mindest-Zugfolge (Strafterm entfällt), die Aufteilung ist nur
im Rahmen des vorhandenen Schlupfes erlaubt. Dieses Stück liefert die Takt-Ausgaben der Stücke davor selbst (als einfache Stufen aus kopiertem
Code), weil der Takt hier nur die Puffer der Anschlüsse bestimmt. Zufall nur über einen übergebenen Generator mit `randrange` (SplitMix64).
"""
from __future__ import annotations

import numpy as np

from anh_rng import SplitMix64
from anh_timetable import Instance, Line, fixed_line_times, turn_slack

STUFEN = ("zufall", "greedy", "phase", "split")
STUFEN_NAMEN = {"zufall": "zufällige Phasen", "greedy": "Greedy", "phase": "Phasen-Optimum", "split": "Phasen + Aufteilung"}
PHASE_RESTARTS = 20      # Neustarts des reinen Phasen-Abstiegs (wie in der Fall-Demo)
SPLIT_RESTARTS = 40      # Neustarts der Suche mit Aufteilung (wie in der Fall-Demo)


def base_arrays(inst: Instance):
    """Vorrechnung für schnelle Offset-Bewertung: wait = ((o_lb - o_la + D) mod T) + mt."""
    la, lb, D, W = [], [], [], []
    ev0 = [fixed_line_times(l, inst.T, inst.dwell, inst.tmin, 0)[0] for l in inst.lines]
    for (a, da, ka, b, db, kb), w in inst.transfers.items():
        la.append(a); lb.append(b); W.append(w)
        D.append(ev0[b][("dep", db, kb)] - ev0[a][("arr", da, ka)] - inst.transfer_min)
    return np.array(la), np.array(lb), np.array(D), np.array(W)


def fast_cost(arrs, offsets, T, mt) -> float:
    la, lb, D, W = arrs
    o = np.asarray(offsets)
    return float((W * (((o[lb] - o[la] + D) % T) + mt)).sum())


def random_offsets(n_lines: int, T: int, rng) -> list:
    return [rng.randrange(T) for _ in range(n_lines)]


def greedy_sequential(inst: Instance, arrs) -> list:
    """Linien nach Umsteigegewicht absteigend einplanen; jede bekommt den Offset, der die Umsteigezeit zu den schon eingeplanten Linien minimiert."""
    la, lb, D, W = arrs
    T, mt = inst.T, inst.transfer_min
    n = len(inst.lines)
    weight = np.zeros(n)
    for a, b, w in zip(la, lb, W):
        weight[a] += w; weight[b] += w
    order = list(np.argsort(-weight, kind="stable"))
    placed = {}
    for li in order:
        if not placed:
            placed[li] = 0
            continue
        best_o, best_c = 0, float("inf")
        for o in range(T):
            c = 0.0
            for a, b, d, w in zip(la, lb, D, W):
                if a == li and b in placed:
                    c += w * (((placed[b] - o + d) % T) + mt)
                elif b == li and a in placed:
                    c += w * (((o - placed[a] + d) % T) + mt)
            if c < best_c:
                best_c, best_o = c, o
        placed[li] = best_o
    return [placed[i] for i in range(n)]


def coordinate_descent(inst: Instance, arrs, start: list) -> tuple:
    """Linie für Linie auf den besten Offset setzen, bis sich nichts mehr verbessert."""
    T, mt = inst.T, inst.transfer_min
    o = list(start)
    best = fast_cost(arrs, o, T, mt)
    improved = True
    while improved:
        improved = False
        for li in range(len(o)):
            keep = o[li]
            for cand in range(T):
                o[li] = cand
                c = fast_cost(arrs, o, T, mt)
                if c < best - 1e-9:
                    best, keep, improved = c, cand, True
            o[li] = keep
    return o, best


def local_search_multistart(inst: Instance, arrs, restarts: int, rng) -> tuple:
    best_o, best_c = None, float("inf")
    for _ in range(restarts):
        o, c = coordinate_descent(inst, arrs, random_offsets(len(inst.lines), inst.T, rng))
        if c < best_c:
            best_o, best_c = o, c
    return best_o, best_c


# ---------------------------------------------------------------- Aufteilung der Wende-Standzeit
def valid_splits(line: Line, inst: Instance) -> list:
    """Zulässige (s_end, 0): die Standzeit-Zugabe am Ende der Hinfahrt liegt zwischen 0 und dem Schlupf (höchstens T - 1)."""
    slack = turn_slack(line, inst.T, inst.dwell, inst.tmin)
    return [(s, 0) for s in range(0, min(slack, inst.T - 1) + 1)]


def split_cache(inst: Instance) -> list:
    """cache[li] = (Liste (s, e'), Ereigniszeiten bei Offset 0 je Eintrag)."""
    out = []
    for line in inst.lines:
        opts = valid_splits(line, inst)
        out.append((opts, [fixed_line_times(line, inst.T, inst.dwell, inst.tmin, 0, s, e)[0] for s, e in opts]))
    return out


def cost_split(inst: Instance, cache: list, offsets: list, sidx: list) -> float:
    T, mt = inst.T, inst.transfer_min
    tot = 0.0
    for (la, da, ka, lb, db, kb), w in inst.transfers.items():
        a = offsets[la] + cache[la][1][sidx[la]][("arr", da, ka)]
        d = offsets[lb] + cache[lb][1][sidx[lb]][("dep", db, kb)]
        tot += w * (((d - a - mt) % T) + mt)
    return tot


def line_cost_matrix(inst: Instance, cache: list, o: list, si: list, li: int) -> np.ndarray:
    """Kosten aller Kandidaten (Offset x Aufteilung) für Linie li bei festen anderen Linien (Matrix [T, n_s], ohne die Konstante)."""
    T, mt = inst.T, inst.transfer_min
    n_s = len(cache[li][0])
    oo = np.arange(T)[:, None]
    cost = np.zeros((T, n_s))
    for (la, da, ka, lb, db, kb), w in inst.transfers.items():
        if la == li and lb != li:
            other = o[lb] + cache[lb][1][si[lb]][("dep", db, kb)]
            base = np.array([cache[li][1][x][("arr", da, ka)] for x in range(n_s)])
            cost += w * (((other - (oo + base[None, :]) - mt) % T) + mt)
        elif lb == li and la != li:
            other = o[la] + cache[la][1][si[la]][("arr", da, ka)]
            base = np.array([cache[li][1][x][("dep", db, kb)] for x in range(n_s)])
            cost += w * ((((oo + base[None, :]) - other - mt) % T) + mt)
    return cost


def descent_split(inst: Instance, cache: list, offsets: list, sidx: list) -> tuple:
    """Linie für Linie bester (Offset, Aufteilung) bei festen anderen Linien, bis keine Verbesserung."""
    o, si = list(offsets), list(sidx)
    best = cost_split(inst, cache, o, si)
    improved = True
    while improved:
        improved = False
        for li in range(len(inst.lines)):
            cost = line_cost_matrix(inst, cache, o, si, li)
            idx = np.unravel_index(np.argmin(cost), cost.shape)
            old = (o[li], si[li])
            o[li], si[li] = int(idx[0]), int(idx[1])
            c = cost_split(inst, cache, o, si)
            if c < best - 1e-9:
                best, improved = c, True
            else:
                o[li], si[li] = old
    return o, si, best


def local_search_split(inst: Instance, restarts: int, rng) -> tuple:
    """Rückgabe (offsets, s-Indizes, Kosten, cache)."""
    cache = split_cache(inst)
    best = (None, None, float("inf"), cache)
    for _ in range(restarts):
        o0 = random_offsets(len(inst.lines), inst.T, rng)
        s0 = [rng.randrange(len(c[0])) for c in cache]
        o, si, c = descent_split(inst, cache, o0, s0)
        if c < best[2]:
            best = (o, si, c, cache)
    return best


def splits_of(cache: list, sidx: list) -> list:
    """Die gewählten (s_end, 0)-Paare je Linie."""
    return [cache[li][0][sidx[li]] for li in range(len(sidx))]


# ---------------------------------------------------------------- Einheit: eine Stufe des Takts
def build_takt(inst: Instance, stufe: str, seed: int) -> tuple:
    """Takt einer Stufe für eine Instanz: Rückgabe (Offsets, Aufteilungen oder None). Der Zufallsstrom hängt nur an `seed` und der Stufe."""
    if stufe not in STUFEN:
        raise ValueError(stufe)
    rng = SplitMix64(1_000_003 * seed + 17)
    if stufe == "zufall":
        return random_offsets(len(inst.lines), inst.T, rng), None
    if stufe == "greedy":
        return greedy_sequential(inst, base_arrays(inst)), None
    if stufe == "phase":
        return local_search_multistart(inst, base_arrays(inst), PHASE_RESTARTS, rng)[0], None
    o, si, _, cache = local_search_split(inst, SPLIT_RESTARTS, rng)
    return o, splits_of(cache, si)
