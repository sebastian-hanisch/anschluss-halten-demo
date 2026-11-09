"""Störtage: Bereiche, Wiederholbarkeit, Orte."""

import pytest

import anh_network as AN
import anh_scenario as AS
import anh_takt as AT


@pytest.fixture(scope="module")
def net():
    inst, demand, _, seed = AN.build_valid_instance(20, 6, 9101)
    o, sp = AT.build_takt(inst, "phase", seed)
    return AN.build_event_net(inst, demand, o, sp, "normal")


def test_anzahl_hoehe_und_orte_im_sollbereich(net):
    ks, hs = [], []
    for s in range(300):
        prim = AS.make_scenario(net, 77_000 + s)
        ks.append(len(prim))
        hs.extend(prim.values())
        assert all(e in set(net.prim_cand) for e in prim)
        assert all(net.ev_key[e][3][0] == "dep" and net.tp[e] < 120 for e in prim)
    assert min(ks) == 1 and max(ks) == 8 and min(hs) == 3 and max(hs) == 30
    assert abs(sum(ks) / len(ks) - 4.5) < 0.4 and abs(sum(hs) / len(hs) - 16.5) < 1.0


def test_gleicher_seed_gleiches_szenario_und_anderer_seed_anderes(net):
    assert AS.make_scenario(net, 5) == AS.make_scenario(net, 5)
    assert any(AS.make_scenario(net, 5) != AS.make_scenario(net, s) for s in range(6, 12))


def test_feste_anzahl_und_hoehe_ueber_die_regler(net):
    for s in range(20):
        prim = AS.make_scenario(net, s, kmin=5, kspan=1, hmin=3, hmax=10)
        assert len(prim) == 5 and all(3 <= h <= 10 for h in prim.values())


def test_randfaelle_der_bereiche(net):
    assert all(h == 7 for h in AS.make_scenario(net, 1, kmin=3, kspan=1, hmin=7, hmax=7).values())    # hmin = hmax
    n_cand = len(net.prim_cand)
    assert len(AS.make_scenario(net, 1, kmin=n_cand + 5, kspan=1)) == n_cand                          # mehr Verspätungen als Orte
    with pytest.raises(ValueError):
        AS.make_scenario(net, 1, hmin=9, hmax=4)
