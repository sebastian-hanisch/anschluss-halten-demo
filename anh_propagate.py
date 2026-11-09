"""Fortpflanzung der Verspätungen (max-plus) und Fahrgastkosten.

nach der Messreihe `delaylib.py` (schiene-planung), angepasst. Verspätung D[e] = max(Primärverspätung, max über Vorgänger D[s] - Puffer, max über GEHALTENE
Anschlüsse D[A] - Puffer), nie unter 0. Ein Anschluss ist erreicht, wenn D[B] >= D[A] - Puffer. Kosten in Fahrgastminuten (Gewichte relativ): direkte
Gruppen w * D[Ziel]; Umsteiger w * min(D[Ziel], Verlust) wenn erreicht, sonst w * Verlust, mit Verlust = M (Folgezug pünktlich) bzw. M + D' (Erweiterung,
D' = Verspätung derselben Fahrt eine Periode später am Ziel).
"""
from __future__ import annotations

import numpy as np


def propagate(net, prim: dict, held) -> np.ndarray:
    """Verspätung aller Ereignisse bei fester Menge `held` gehaltener Anschlüsse (Indizes). Ereignisse stehen in Planreihenfolge."""
    held = set(held)
    D = [0] * net.N
    for e in range(net.N):
        b = prim.get(e, 0)
        for s, sl in net.preds[e]:
            v = D[s] - sl
            if v > b:
                b = v
        for c, a, sl in net.conn_in[e]:
            if c in held:
                v = D[a] - sl
                if v > b:
                    b = v
        D[e] = b
    return np.array(D, dtype=np.int64)


def caught_flags(net, D) -> np.ndarray:
    """Erreicht der Folgezug den Zubringer-Fahrgast? D[B] >= D[A] - Puffer."""
    if net.nconn == 0:
        return np.zeros(0, dtype=bool)
    return D[net.cB] >= D[net.cA] - net.cS


def loss_vector(net, D, M: int, follow: bool = False) -> np.ndarray:
    """Verlust je Umsteigergruppe beim Verpassen: M, mit Erweiterung M + D' (D' = 0, wenn die nächste Fahrt hinter dem Horizont liegt)."""
    base = np.full(len(net.g_e), M, dtype=np.int64)
    if not follow or len(net.g_e) == 0:
        return base
    dn = np.where(net.nxt_g >= 0, D[np.maximum(net.nxt_g, 0)], 0)
    return base + dn


def group_costs(net, D, M: int, follow: bool = False):
    """(Kosten der direkten Gruppen je Ziel-Ereignis, Kosten der Umsteigergruppen) in Fahrgastminuten."""
    cd = net.dir_w * D[net.dir_e]
    if len(net.g_e):
        cau = caught_flags(net, D)[net.g_c]
        loss = loss_vector(net, D, M, follow)
        cg = net.g_w * np.where(cau, np.minimum(D[net.g_e], loss), loss)
    else:
        cg = np.zeros(0, dtype=np.int64)
    return cd, cg


def total_cost(net, D, M: int, follow: bool = False) -> int:
    cd, cg = group_costs(net, D, M, follow)
    return int(cd.sum() + cg.sum())
