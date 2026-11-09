"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets."""

# ------------------------------------------------------------------ feste Annahmen
N_STOPS = 20                       # Haltestellen des Live-Netzes (die Messnetze haben 16/20/24/20)
T = 60                             # Takt in Minuten
HORIZON = 240                      # Minuten, die das Ereignisnetz abdeckt
LIVE_TIME_LIMIT = 10.0             # Sekunden je Störtag für das Optimum in der App; danach „nicht bewiesen“
LIVE_RUN_SCENARIOS = 100           # Störtage des Live-Experiments (nur normale Puffer)
LIVE_RUN_BUDGET = 60.0             # Sekunden Gesamtbudget des Live-Experiments; danach bricht es mit der Zahl der geschafften Störtage ab

# ------------------------------------------------------------------ Regler
LINES_MIN, LINES_MAX, DEFAULT_LINES = 4, 10, 6
STUFEN = ("zufall", "greedy", "phase", "split")
STUFEN_NAMEN = {"zufall": "zufällige Phasen", "greedy": "Greedy", "phase": "Phasen-Optimum", "split": "Phasen + Aufteilung"}
DEFAULT_STUFE = "phase"
PUFFER = ("normal", "knapp")
PUFFER_NAMEN = {"normal": "normal (Fahrzeit −7 %, Halt −1 min)", "knapp": "knapp (ohne Reserve, Wendepuffer höchstens 10 min)"}
DEFAULT_PUFFER = "normal"
M_MIN, M_MAX, M_STEP, DEFAULT_M = 10, 120, 5, 60
K_MIN, K_MAX, DEFAULT_K = 1, 16, 5
HMAX_MIN, HMAX_MAX, DEFAULT_HMAX = 3, 30, 30
RULES = ("never", "always", "c", "p", "d", "bal", "bal2")
RULE_NAMEN = {"never": "nie halten", "always": "immer halten", "c": "c_W: zusätzliche Wartezeit höchstens W",
              "p": "p_W: Abfahrtsverspätung höchstens W", "d": "d_W: wie c_W, nur schwere Anschlüsse (oberes Viertel)",
              "bal": "Gegenrechnung im eigenen Zug", "bal2": "Gegenrechnung, verfeinert"}
RULES_WITH_W = ("c", "p", "d")
DEFAULT_RULE = "p"
W_MIN, W_MAX, DEFAULT_W = 1, 14, 5
SEED_MAX = 999999
DEFAULT_NET_SEED, DEFAULT_SCEN_SEED = 9601, 1      # außerhalb der Seeds 9000 bis 9027 der Messnetze

# ------------------------------------------------------------------ Darstellung
COLOR_OPT = "#2e7d4f"
COLOR_RULE = "#c77700"
COLOR_NEVER = "#7d8898"
COLOR_ALWAYS = "#b03a6f"
COLOR_BLUE = "#2a6fb0"
COLOR_PLAN = "rgba(150,150,150,0.8)"

# ------------------------------------------------------------------ Presets
PRESET_ORDER = ["Standard", "Folgezug kommt bald", "Folgezug kommt spät", "Knappe Puffer", "Dichter Takt", "Immer halten", "Folgezug auch verspätet"]
_BASE = {"lines": DEFAULT_LINES, "stufe": DEFAULT_STUFE, "puffer": DEFAULT_PUFFER, "M": DEFAULT_M, "k": DEFAULT_K, "hmax": DEFAULT_HMAX, "rule": DEFAULT_RULE,
         "W": DEFAULT_W, "folgezug": False, "net_seed": DEFAULT_NET_SEED, "scen_seed": DEFAULT_SCEN_SEED}
PRESETS = {
    "Standard": dict(_BASE),
    "Folgezug kommt bald": dict(_BASE, M=15),
    "Folgezug kommt spät": dict(_BASE, M=120),
    "Knappe Puffer": dict(_BASE, puffer="knapp", rule="bal2"),
    "Dichter Takt": dict(_BASE, stufe="split"),
    "Immer halten": dict(_BASE, rule="always"),
    "Folgezug auch verspätet": dict(_BASE, folgezug=True),
}
PRESET_HELP = {
    "Standard": "6 Linien, Phasen-Optimum, normale Puffer, Verlust beim Verpassen M = 60 min, Regel p_5: der Grundfall dieser Demo.",
    "Folgezug kommt bald": "M = 15: Wer den Anschluss verpasst, verliert wenig. Im Mittel über die Messnetze liegt das beste W dann bei 2 min (E1): Die Schwelle 5 min wartet länger.",
    "Folgezug kommt spät": "M = 120: Wer den Anschluss verpasst, verliert viel. Im Mittel über die Messnetze liegt das beste W dann bei 9 min (E1): Die Schwelle 5 min wartet kürzer.",
    "Knappe Puffer": "Fahrzeiten ohne Reserve, Wendepuffer höchstens 10 min, Regel: Gegenrechnung im eigenen Zug. Verspätungen pflanzen sich weiter fort.",
    "Dichter Takt": "Takt mit Aufteilung der Wende-Standzeit: kürzere Plan-Umsteigezeit, aber mehr kritische Anschlüsse je Störtag.",
    "Immer halten": "Der Folgezug wartet auf jeden Zubringer. Die einfachste Regel ist hier (M = 60) meist die schlechteste.",
    "Folgezug auch verspätet": "Verpassen kostet M plus die Verspätung der nächsten Fahrt derselben Linie am Ziel (Erweiterung des Grundmodells).",
}

# ------------------------------------------------------------------ Pflichttext der Modellgrenzen (App und README tragen denselben Wortlaut; tests/test_claims.py vergleicht)
ASSUMPTIONS_MARKDOWN = """- **M ist eine Annahme.** Wer den Anschluss verpasst, verliert genau M Minuten (10 bis 120 wählbar); der Folgezug fährt pünktlich. Die Erweiterung (Folgezug verspätet) verschiebt den Abstand der besten festen Regel zum Optimum nur von 3,1 auf 3,2 % (E5), ersetzt aber keine Betriebsdaten.
- **Keine Trassenkonflikte:** Ein wartender Zug blockiert keine anderen Züge, es gibt keine Überholungen, Kapazitäten oder Zugfolgezeiten. Reale Kettenwirkungen sind eher unterschätzt.
- **Keine Umlegung** der Fahrgäste auf andere Wege, keine Wartezeitobergrenze; **Gewichte relativ** (Nachfrage-Generator mit zwei Hubs), keine echten Fahrgastzahlen. Verspätungen nur als Primärverspätungen an Abfahrten der ersten zwei Stunden, 3 bis 30 min gleichverteilt (in der Messreihe 1 bis 8 je Störtag).
- **Die Regeln kennen die Zubringerverspätung exakt** (vollinformiert) und sehen nur den eigenen Anschluss; das Optimum sieht alle Entscheidungen des Tages und die ganze Störung im Voraus, ist also **kein online umsetzbares Verfahren**, sondern der Maßstab.
- **Alle Linien haben 6 Haltestellen** (80 Ereignisse je Linie im Horizont, 320 bis 800 je Netz); synthetische Netze mit 16 bis 24 Haltestellen (live 20). Die Befunde gelten für diese Netze und diesen Generator, nicht für reale Netze; die Zahlen sind keine Prognose.
- **Die „beste Regel“ ist im Rückblick gewählt** (Minimum über W auf denselben Störtagen); im Einsatz kennt niemand M. Die Streuung je Störtag ist groß: Die Lücke von p_5 zum Optimum liegt im Median bei 0,8 %, im P90 bei 8,1 %, im P99 bei 26,6 % und im Maximum bei 91,5 % (Basis: Optimum des Störtags, M = 60, normale Puffer).
- **Das Optimum läuft live mit Zeitlimit** (10 s je Störtag); danach zeigt die App die beste gefundene Entscheidung und „nicht bewiesen“. Die vorgerechnete Messreihe lief mit 60 s Limit. Bei bis zu 16 Primärverspätungen (Reglermaximum), knappen Puffern und 10 Linien blieb in einer Stichprobe der unabhängigen Prüfung etwa jeder dritte bis zweite Störtag unbewiesen (nicht Teil der Messreihe).
"""
