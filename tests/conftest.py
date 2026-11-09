"""Gemeinsame Fixtures: die von Hand gerechnete Mini-Instanz (DEMO-PLAYBOOK §1b).

Ereignisse 0 bis 5 mit Planminuten 10, 12, 15, 25, 30, 40: 0 und 1 sind Ankünfte zweier Zubringer, 2 ist die Abfahrt des Folgezugs B, 3 seine Ankunft am
Umsteigeort, 4 die Abfahrt des Anschlusszugs C, 5 seine Ankunft am Ziel. Aktivitäten 2 -> 3 mit Puffer 1 (Plan 10 min, Mindestfahrzeit 9), 4 -> 5 mit Puffer 0.
Anschlüsse: c0 = 0 -> 2 (Puffer 15 - 10 - 3 = 2), c1 = 1 -> 2 (15 - 12 - 3 = 0), c2 = 3 -> 4 (30 - 25 - 3 = 2). Gruppen: 10 Fahrgäste von c0 und 20 von c1 zum
Ziel Ereignis 3, 15 von c2 zum Ziel Ereignis 5; direkt 5 bis Ereignis 3 und 300 bis Ereignis 5. An Bord: 35 im Zug B (10 + 20 + 5), 315 im Zug C (15 + 300).
Primärverspätungen: Ereignis 0 um 6, Ereignis 1 um 4. Verlust beim Verpassen M = 20.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anh_network as AN  # noqa: E402

M_MINI = 20
PRIM_MINI = {0: 6, 1: 4}


def mini_parts():
    N = 6
    preds = [[], [], [], [(2, 1)], [], [(4, 0)]]
    conns = [(0, 2, 2), (1, 2, 0), (3, 4, 2)]
    groups = [[(3, 10)], [(3, 20)], [(5, 15)]]
    dirs = [(3, 5), (5, 300)]
    onb = [0, 0, 35, 0, 315, 0]
    return N, preds, conns, groups, dirs, onb


@pytest.fixture
def mini():
    return AN.assemble(*mini_parts())


@pytest.fixture
def mini_follow():
    """Wie `mini`, mit der Erweiterung: Ereignis 6 (Verspätung 10) ist dasselbe Ziel wie 3 eine Periode später, Ereignis 7 (Verspätung 100) wie 5.

    Verpassen kostet dann M + 10 am Ziel 3 und M + 100 am Ziel 5. Von Hand: nie 300 + 600 (c0 und c1 verpasst, je 30 statt 20) = 900;
    {c0}: 30 + 60 + 15 * (20 + 100) + 15 = 1905; {c0, c2}: 30 + 60 + 15 + 15 + 300 = 420, also ist das Optimum 420 (im Grundmodell 405)."""
    N, preds, conns, groups, dirs, onb = mini_parts()
    net = AN.assemble(N + 2, preds + [[], []], conns, groups, dirs, onb + [0, 0], nxt={3: 6, 5: 7})
    return net, {0: 6, 1: 4, 6: 10, 7: 100}
