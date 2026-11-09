"""Wartezeitregeln: wer entscheidet worüber.

nach der Messreihe `delaylib.simulate` (schiene-planung), angepasst: die Entscheidung je Anschluss ist eine reine Funktion (`decide`), der Durchlauf
entscheidet zeitlich in Planreihenfolge. Eine Regel ist ein Tupel: ("never",), ("always",), ("c", W), ("p", W), ("d", W, q), ("bal",), ("bal2",).

Bezeichnungen je kritischem Anschluss (Zubringer verspätet über den Puffer hinaus): `need` = Abfahrtsverspätung, die der Folgezug annehmen müsste, um
den Zubringer zu erreichen (D[A] - Puffer); `b` = Verspätung, die er ohnehin hat; `extra` = need - b = zusätzliche Wartezeit durch das Halten.
"""
from __future__ import annotations

import numpy as np

REGEL_ERKLAERUNG = {
    "never": "nie halten: Der Folgezug fährt pünktlich bzw. mit seiner eigenen Verspätung ab.",
    "always": "immer halten: Der Folgezug wartet auf jeden verspäteten Zubringer, wie lange es auch dauert.",
    "c": "c_W: Halten, wenn die zusätzliche Wartezeit des Folgezugs über seine eigene Verspätung hinaus höchstens W Minuten beträgt.",
    "p": "p_W: Halten, wenn die Abfahrtsverspätung des Folgezugs durch das Halten höchstens W Minuten beträgt.",
    "d": "d_W_q: wie c_W, aber nur für Anschlüsse, deren Umsteigergewicht mindestens das q-Quantil aller Anschlüsse erreicht.",
    "bal": "Gegenrechnung im eigenen Zug: Halten, wenn Umsteiger mal M mindestens die Fahrgäste an Bord mal Wartezeit wiegen.",
    "bal2": "Gegenrechnung, verfeinert: Der Verlust der Umsteiger ist M minus die schon angenommene Verspätung.",
}


def rule_name(rule: tuple) -> str:
    """Kurzname für Tabellen und Dateien: never, always, bal, bal2, p5, c5, d5_75."""
    if rule[0] in ("never", "always", "bal", "bal2"):
        return rule[0]
    if rule[0] == "d":
        return f"d{rule[1]}_{rule[2]}"
    return f"{rule[0]}{rule[1]}"


def parse_rule(name: str) -> tuple:
    """Umkehrung von `rule_name`."""
    if name in ("never", "always", "bal", "bal2"):
        return (name,)
    if name.startswith("d"):
        w, q = name[1:].split("_")
        return ("d", int(w), int(q))
    return (name[0], int(name[1:]))


def decide(rule: tuple, need: int, extra: int, weight: int, onboard: int, M: int, theta: dict) -> bool:
    """Soll der Folgezug auf diesen Anschluss warten? `weight` = Umsteigergewicht des Anschlusses, `onboard` = alle Fahrgäste an Bord des Folgezugs
    (einschließlich der Umsteiger dieses Anschlusses), `theta` = Gewichtsschwellen der Quantile 50 und 75."""
    kind = rule[0]
    if kind == "never":
        return False
    if kind == "always":
        return True
    if kind == "c":
        return extra <= rule[1]
    if kind == "p":
        return need <= rule[1]
    if kind == "d":
        return extra <= rule[1] and weight >= theta[rule[2]]
    if kind == "bal":
        return weight * M >= extra * (onboard - weight)
    if kind == "bal2":
        return weight * max(0, M - need) >= extra * (onboard - weight)
    raise ValueError(kind)


def run_rule(net, prim: dict, M: int, rule: tuple):
    """Fortpflanzung mit Regel; Rückgabe (D, gehaltene Anschlüsse als Menge). Mehrere Anschlüsse an einem Folgezug: aufsteigend nach need."""
    D = [0] * net.N
    held = set()
    for e in range(net.N):
        b = prim.get(e, 0)
        for s, sl in net.preds[e]:
            v = D[s] - sl
            if v > b:
                b = v
        cs = net.conn_in[e]
        if cs:
            pend = sorted((D[a] - sl, cid) for cid, a, sl in cs if D[a] - sl > b)
            for need, cid in pend:
                if need <= b:
                    continue
                extra = need - b
                if decide(rule, need, extra, net.conn_w[cid], net.onb[e], M, net.theta):
                    b = need
                    held.add(cid)
        D[e] = b
    return np.array(D, dtype=np.int64), held
