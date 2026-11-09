"""Netz, Routen und Ereignisnetz: eine Ableitung für Takt und Anschlüsse, Invarianten der Anschlüsse, Gleichstand der Umsteigehaltestelle."""

import numpy as np
import pytest

import anh_network as AN
import anh_takt as AT
from anh_timetable import Line

NETZE = [(4, 16, 9000), (5, 20, 9001), (6, 20, 9002), (8, 24, 9017), (10, 20, 9027)]


def _tie_lines():
    """Zwei Linien teilen die Halte 2 und 9. Haltestelle 0 liegt nur auf Linie 0, Haltestelle 5 nur auf Linie 1.

    Umstieg an 2: 0 -> 2 (4 min) + 2 -> 5 (8 min) = 12; an 9: 0 -> 9 (8 min) + 9 -> 5 (4 min) = 12: Gleichstand."""
    return [Line([0, 2, 9], [4, 4]), Line([2, 9, 5], [4, 4])]


def _tie_demand():
    demand = np.zeros((10, 10), dtype=np.int64)
    demand[0][5] = demand[5][0] = 6
    return demand


def test_gleichstand_der_umsteigehaltestelle_sortiert_waehlt_die_kleinste_nummer():
    r = [x for x in AN.route_pairs(_tie_lines(), _tie_demand(), "sortiert") if not x.direct]
    assert [(x.la, x.lb, x.s) for x in r] == [(0, 1, 2)]


def test_mengenreihenfolge_waehlt_eine_andere_haltestelle_und_ist_nicht_die_regel():
    """Die Vormessung fand zwei Ableitungen mit verschiedener Wahl; die Mengenreihenfolge von {2, 9} ist 9, 2 (9 mod 8 = 1). Dieser Test hält den Unterschied fest."""
    assert list({2, 9}) == [9, 2]
    r = [x for x in AN.route_pairs(_tie_lines(), _tie_demand(), "menge") if not x.direct]
    assert [(x.la, x.lb, x.s) for x in r] == [(0, 1, 9)]


def test_unbekannte_gleichstandsregel_wird_abgelehnt():
    with pytest.raises(ValueError):
        AN.route_pairs(_tie_lines(), _tie_demand(), "zufall")


def test_derive_connections_teilt_die_nachfrage_je_zur_haelfte_auf_beide_richtungen():
    conns = AN.derive_connections(_tie_lines(), _tie_demand())
    # Hinweg: Linie 0 Richtung f, Ankunft an Position 1 (Halt 2), Umstieg auf Linie 1 Richtung f ab Position 0 (Halt 2); Rückweg gespiegelt; je 6 / 2 = 3
    assert conns == {(0, "f", 1, 1, "f", 0): 3.0, (1, "b", 0, 0, "b", 1): 3.0}


def test_direktverbindung_hat_keinen_umstieg_und_waehlt_kuerzere_fahrzeit_dann_kleinere_linie():
    lines = [Line([0, 1, 2], [5, 5]), Line([0, 2], [6])]        # 0 -> 2: Linie 0 braucht 10, Linie 1 braucht 6
    demand = np.zeros((3, 3), dtype=np.int64)
    demand[0][2] = 4
    (r,) = AN.route_pairs(lines, demand)
    assert r.direct and r.la == 1
    (r2,) = AN.route_pairs([Line([0, 2], [6]), Line([0, 2], [6])], demand)
    assert r2.la == 0
    assert AN.derive_connections(lines, demand) == {}


@pytest.mark.parametrize("nl,ns,seed", NETZE)
def test_anschluesse_sind_ankunft_zu_abfahrt_andere_linie_gleiche_haltestelle(nl, ns, seed):
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    net = AN.build_event_net(inst, demand, *AT.build_takt(inst, "zufall", seed), "normal")
    assert net.nconn > 0
    for c in range(net.nconn):
        A, B = net.conn_A[c], net.conn_B[c]
        sl = net.tp[B] - net.tp[A] - inst.transfer_min
        assert net.ev_key[A][3][0] == "arr" and net.ev_key[B][3][0] == "dep"
        assert AN.line_of(net, A) != AN.line_of(net, B) and AN.station_of(net, A) == AN.station_of(net, B)
        assert sl == net.conn_sl[c] and 0 <= sl < net.T


@pytest.mark.parametrize("nl,ns,seed", NETZE)
def test_takt_und_ereignisnetz_haben_dieselben_umsteigeaktivitaeten(nl, ns, seed):
    inst, demand, _ = AN.build_instance(ns, nl, seed)
    net = AN.build_event_net(inst, demand, *AT.build_takt(inst, "greedy", seed), "normal")
    keys = set()
    for c in range(net.nconn):
        _, lA, _, kA = net.ev_key[net.conn_A[c]]
        _, lB, _, kB = net.ev_key[net.conn_B[c]]
        keys.add((lA, kA[1], kA[2], lB, kB[1], kB[2]))
    assert keys == set(inst.transfers)


def test_alle_aktivitaeten_haben_nichtnegativen_puffer_und_vorgaenger_stehen_vorn():
    inst, demand, _ = AN.build_instance(20, 6, 9002)
    for variante in ("normal", "knapp"):
        net = AN.build_event_net(inst, demand, *AT.build_takt(inst, "split", 9002), variante)
        assert all(sl >= 0 and s < e for e in range(net.N) for s, sl in net.preds[e])
        assert all(net.tp[net.conn_A[c]] < net.tp[net.conn_B[c]] for c in range(net.nconn))
        assert net.tp == sorted(net.tp)


def test_knappe_puffer_sind_kleiner_als_normale():
    inst, demand, _ = AN.build_instance(20, 6, 9002)
    off, sp = AT.build_takt(inst, "phase", 9002)
    nn = AN.build_event_net(inst, demand, off, sp, "normal")
    nk = AN.build_event_net(inst, demand, off, sp, "knapp")
    assert nn.N == nk.N
    assert sum(sl for e in range(nn.N) for _, sl in nn.preds[e]) > sum(sl for e in range(nk.N) for _, sl in nk.preds[e])


def test_gueltiger_seed_ueberspringt_netze_ohne_umstieg():
    inst, demand, _, used = AN.build_valid_instance(16, 4, 9000)
    assert used >= 9000 and inst.transfers and len(inst.lines) >= 2
    with pytest.raises(ValueError):
        AN.build_valid_instance(16, 4, 9000, attempts=0)


def test_ereignisnetz_traegt_naechste_fahrt_nur_im_horizont():
    inst, demand, _ = AN.build_instance(20, 6, 9002)
    net = AN.build_event_net(inst, demand, *AT.build_takt(inst, "phase", 9002), "normal")
    assert len(net.nxt_g) == len(net.g_e)
    assert (net.nxt_g >= 0).any() and (net.nxt_g < 0).any()
    for e, n in zip(net.g_e, net.nxt_g):
        if n >= 0:
            assert net.ev_key[n][1] == net.ev_key[e][1] and net.ev_key[n][2] == net.ev_key[e][2] + 1 and net.ev_key[n][3] == net.ev_key[e][3]
            assert net.tp[n] == net.tp[e] + net.T
