"""Takt-Stufen: Zeiten von Hand, Ordnung der Stufen, Wiederholbarkeit."""

import pytest

import anh_network as AN
import anh_takt as AT
import anh_timetable as TT
from anh_timetable import Line


def test_ereigniszeiten_einer_linie_von_hand():
    # Linie mit 3 Halten, Fahrzeiten 10 und 8, Halt 2 min, Wende mindestens 4 min, T = 60
    line = Line([0, 1, 2], [10, 8])
    # Zyklus ohne Schlupf: 2 * 18 + 2 * 2 * 1 + 2 * 4 = 48, also Schlupf 12
    assert TT.turn_slack(line, 60, 2, 4) == 12
    ev, cycle = TT.fixed_line_times(line, 60, 2, 4, offset=5)
    assert ev[("dep", "f", 0)] == 5 and ev[("arr", "f", 1)] == 15 and ev[("dep", "f", 1)] == 17 and ev[("arr", "f", 2)] == 25
    # Wende am Ende: 4 + 6 (Schlupf halbiert) = 10 min
    assert ev[("dep", "b", 2)] == 35 and ev[("arr", "b", 1)] == 43 and ev[("dep", "b", 1)] == 45 and ev[("arr", "b", 0)] == 55
    assert cycle == 60                                    # 55 + 4 + 6 - 5
    # Aufteilung 0 / 12: Wende am Ende nur 4 min, am Anfang 4 + 12
    ev2, cycle2 = TT.fixed_line_times(line, 60, 2, 4, offset=5, split=0)
    assert ev2[("dep", "b", 2)] == 29 and cycle2 == 60


def test_wartezeit_ist_modulo_takt_mit_mindestzeit():
    assert TT.wait_time(10, 15, 3, 60) == 5
    assert TT.wait_time(10, 12, 3, 60) == 62           # 2 min reichen nicht für 3 min Umstieg: die Abfahrt eine Stunde später, 72 - 10 = 62
    assert TT.wait_time(10, 13, 3, 60) == 3


@pytest.fixture(scope="module")
def netz():
    inst, demand, _ = AN.build_instance(20, 7, 9005)
    return inst, demand


def _kosten(inst, off, sp):
    cache = AT.split_cache(inst)
    if sp is None:
        sidx = [cache[li][0].index((TT.turn_slack(inst.lines[li], inst.T, inst.dwell, inst.tmin) // 2, 0)) for li in range(len(inst.lines))]
    else:
        sidx = [cache[li][0].index(sp[li]) for li in range(len(sp))]
    return AT.cost_split(inst, cache, off, sidx)


def test_stufen_sind_wiederholbar(netz):
    inst, _ = netz
    for stufe in AT.STUFEN:
        assert AT.build_takt(inst, stufe, 9005) == AT.build_takt(inst, stufe, 9005)


def test_umsteigezeit_sinkt_von_stufe_zu_stufe(netz):
    inst, _ = netz
    c = {s: _kosten(inst, *AT.build_takt(inst, s, 9005)) for s in AT.STUFEN}
    assert c["phase"] <= c["greedy"] + 1e-9 and c["phase"] < c["zufall"]
    assert c["split"] <= c["phase"] + 1e-9


def test_schnelle_kosten_gleich_langsame_kosten(netz):
    inst, _ = netz
    off, _ = AT.build_takt(inst, "phase", 9005)
    assert AT.fast_cost(AT.base_arrays(inst), off, inst.T, inst.transfer_min) == pytest.approx(_kosten(inst, off, None))


def test_unbekannte_stufe_wird_abgelehnt(netz):
    with pytest.raises(ValueError):
        AT.build_takt(netz[0], "optimal", 1)


def test_aufteilung_bleibt_im_schlupf(netz):
    inst, _ = netz
    off, sp = AT.build_takt(inst, "split", 9005)
    for line, (s, e) in zip(inst.lines, sp):
        assert 0 <= s <= TT.turn_slack(line, inst.T, inst.dwell, inst.tmin) and e == 0
