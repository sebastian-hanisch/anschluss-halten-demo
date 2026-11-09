"""Störtage: Primärverspätungen (Ort, Höhe) aus einem Zufalls-Seed. Zufall nur über SplitMix64.

nach der Messreihe `delaylib.make_scenario` (schiene-planung), angepasst: Anzahl und Höhe sind Parameter. Ein Störtag setzt 1 bis 8 Primärverspätungen
von 3 bis 30 min (Annahme der Messreihe, gleichverteilt) an Abfahrten der ersten zwei Stunden.
"""
from __future__ import annotations

from anh_rng import SplitMix64

K_MIN_DEFAULT, K_SPAN_DEFAULT = 1, 8     # Zahl der Primärverspätungen: kmin + below(kspan), also 1..8
H_MIN, H_MAX = 3, 30                     # Höhe in Minuten, gleichverteilt


def make_scenario(net, seed: int, kmin: int = K_MIN_DEFAULT, kspan: int = K_SPAN_DEFAULT, hmin: int = H_MIN, hmax: int = H_MAX) -> dict:
    """Primärverspätungen {Ereignis: Minuten}: k = kmin + below(kspan) verschiedene Abfahrten aus `net.prim_cand` (ohne Zurücklegen), Höhe hmin..hmax."""
    if not (1 <= hmin <= hmax):
        raise ValueError((hmin, hmax))
    rng = SplitMix64(seed)
    k = kmin + rng.below(kspan)
    cand = list(net.prim_cand)
    prim = {}
    for _ in range(min(k, len(cand))):
        e = cand.pop(rng.below(len(cand)))
        prim[e] = hmin + rng.below(hmax - hmin + 1)
    return prim
