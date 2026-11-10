# Anschluss halten oder abfahren – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-anschluss-halten-demo.streamlit.app/)** -->

Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe auf der Website „Sebastian Hanisch – Operations Research und Machine Learning“ und ist ausdrücklich ein **Kontrast** zum Takt-Suchen, kein Fix. Der Takt der übrigen Demos der Linie senkt die **Plan-Umsteigezeit** und nimmt dafür Puffer weg. Am Betriebstag wird daraus eine Regelfrage: Wenn ein Zubringer verspätet ist, soll der Folgezug **warten** oder **abfahren**? Die Demo rechnet das **Optimum** je Störtag (CP-SAT, eine Binärvariable je kritischem Anschluss) und misst, wie nah einfache **Wartezeitregeln** kommen. Das Vehikel ist dasselbe synthetische Netz wie in `taktfahrplan-demo` (Generator, Linienkonstruktion und Takt-Suche sind von dort kopiert, nicht importiert; die Takt-Stufen zufällige Phasen, Greedy, Phasen-Optimum und Phasen mit Aufteilung der Wende-Standzeit liefert diese Demo selbst als einfache Ausgaben).

Abgrenzung: `fahrzeitreserve-demo` legt Zeitpuffer auf einer Strecke ohne Umsteiger fest und nennt Dispositionseingriffe als „bewusst nicht umgesetzt“, diese Demo setzt dort an; `bunching-demo` hält Fahrzeuge einer Ringlinie ohne Anschlüsse; `warten-oder-fahren-demo` ist ein anderes Modell (Warten, um Aufträge zu sammeln). Die Kernaussage „eine einfache Regel liegt nahe am Optimum“ hat diese Demo mit `revenue-management-demo` und `bunching-demo` gemeinsam; eigen sind die Wanderung des besten W mit dem Verlust M, die Brücke zum Takt und die Gegenrechnung im eigenen Zug.

## Warum dieses Problem

Ein exaktes Verfahren findet für jeden Störtag die beste Menge gehaltener Anschlüsse, aber nur im Rückblick: Es kennt die ganze Störung im Voraus. Im Betrieb entscheidet eine Regel, und die Frage ist, wie viel das Rechnen des Optimums gegenüber einer gut gewählten Regel bringt, und ob die Regel ohne Kenntnis des Verlusts M überhaupt gut gewählt werden kann.

## Modell

Ereignisnetz auf dem Takt (T = 60 min, Horizont 240 min): Ereignisse sind Ankünfte und Abfahrten mit Planminute. Aktivitäten (Fahren mit Mindestfahrzeit = Plan − 7 % gerundet, Halten mit Mindesthalt 1 min, Wende und Fahrzeugumlauf mit Mindestwende 4 min, Anschlüsse mit Mindestumsteigezeit 3 min) tragen einen **Puffer**. Verspätungen pflanzen sich per max-plus fort, Entscheidung zeitlich in Planreihenfolge. Variante „knapp“: Fahrzeiten und Halte ohne Reserve, Wendepuffer höchstens 10 min. Ein Anschluss ist **kritisch**, wenn der Zubringer bei „immer halten“ über den Puffer hinaus verspätet ist. Kosten in Fahrgastminuten Verspätung am Ziel (Gewichte relativ): direkte Gruppen w · D, Umsteiger w · min(D, M) wenn erreicht, sonst w · M (Erweiterung: M + D′ mit der Verspätung D′ der nächsten Fahrt derselben Linie am Ziel). Formeln im Expander „📐 Mathematische Formulierung“ der App.

Die Umsteigeaktivitäten des Takts und die Anschlüsse des Ereignisnetzes kommen aus **einer** Ableitung (`anh_network.route_pairs`, Gleichstand der Umsteigehaltestelle: kleinste Nummer). Zwei getrennte Ableitungen wählten bei Gleichstand verschiedene Haltestellen (Vormessung `fahrplan-planung/vormessung/out_e6_konsistenz_auswertung.txt`, Befunde dort unverändert).

Regeln (Entscheidung je kritischem Anschluss, `need` = nötige Abfahrtsverspätung, `extra` = zusätzliche Wartezeit über die eigene Verspätung hinaus): **nie**, **immer**, `c_W` (extra ≤ W), `p_W` (need ≤ W), `d_W` (wie `c_W`, nur Anschlüsse ab dem 75-Prozent-Quantil des Umsteigergewichts), **Gegenrechnung** (`bal`, `bal2`: Gewinn der Umsteiger gegen die Fahrgäste an Bord, nur im eigenen Zug) und das **Optimum**.

## Methodik

- **Messreihe** (vorgerechnet mit `tools/build_results.py`, `data/anh_results.json`): 28 Netze (Zufalls-Seed 9000 bis 9027, 4 bis 10 Linien mit je 4 Netzen, 16/20/24/20 Haltestellen), je Netz 100 Störtage mit 1 bis 8 Primärverspätungen von 3 bis 30 min an Abfahrten der ersten zwei Stunden, also 2 800 Störtage je Experiment. Ausgewiesen wird das **Netz-Mittel ± Standardfehler** (Standardabweichung / √28); der Abstand einer Regel zum Optimum ist je Netz das Verhältnis der Kosten über die 100 Störtage minus 1. Das Optimum läuft mit 60 s Zeitlimit; nicht bewiesene Störtage werden gezählt.
- **Live** rechnet die App einen Störtag auf dem gewählten Netz: Takt, Ereignisnetz, Regel und Optimum mit 10 s Zeitlimit (danach „nicht bewiesen“).
- Zufall in Netzen, Störtagen, Takt-Stufen und Messreihe nur über den ganzzahligen SplitMix64; die Störtage hängen nur an den Zufalls-Seeds der Netze, nie am Ergebnis. **Einzige Ausnahme:** Die Schaltfläche „Neuen Störtag würfeln“ der App zieht den Zufalls-Seed des Störtags mit Pythons `random` (`anh_presets.randomize_scen_seed`); der Störtag selbst entsteht aus diesem Seed wieder über SplitMix64, und die Messreihe berührt der Knopf nicht.

## Hypothesen

Normale Puffer, M = 60 min, Phasen-Optimum, wenn nichts anderes steht; Abstand in % der Optimumskosten. Belege: `tests/test_claims.py`.

| | Hypothese | Ergebnis |
|---|---|---|
| H1 | Die beste feste Wartezeitregel liegt 2 bis 4 % über dem bewiesenen Optimum | **Ja, im Rückblick gewählt und im Netz-Mittel (M = 60, diese 28 Netze; je Linienzahl 2,3 bis 4,2 %).** `p_5` liegt 3,1 ± 0,4 % über dem Optimum (2 605 von 2 605 Störtagen mit Entscheidung bewiesen); bei knappen Puffern `p_3` 3,0 ± 0,3 % (2 720 von 2 721 bewiesen). Das Optimum liegt 10,4 % unter „nie halten“ (Basis: „nie halten“), bei knappen Puffern 5,7 % |
| H2 | Das beste W wandert mit dem Verlust M | **Ja.** Bestes W (Netz-Mittel) für M = 10, 15, 20, 30, 45, 60, 90, 120: 1, 2, 2, 3, 4, 5, 8, 9 min. Je Netz streut es (M = 60: 4 bis 8, Median 5). Die Kurve ist flach um das Minimum: bei 6 der 8 Werte von M liegt ein benachbartes W um weniger als 0,1 Prozentpunkte über dem besten W; die Wanderung ist als Richtung belastbar, einzelne Werte liegen innerhalb des Standardfehlers. Eine feste Schwelle W = 5 kostet gegenüber dem besten W bis zu 4,2 Prozentpunkte (bei M = 10 und bei M = 120) |
| H3 | „Immer halten“ ist schlimmer als „nie halten“, für die gemessenen M (10 bis 120 min) | **Ja für die gemessenen M; die Umkehr liegt außerhalb.** Bei M = 60 in allen 28 Netzen (normal und knapp), für die übrigen sieben M im Netz-Mittel (bei M = 120, normale Puffer, Phasen-Optimum, ist „immer halten“ gezählt über die Netzkosten der 100 Störtage in 8 von 28 Netzen billiger als „nie halten“; Zählung in `tests/test_claims.py` aus `data/anh_results.json`). Bei M = 60: 71,7 ± 6,0 % über dem Optimum gegen 11,2 ± 0,9 % für „nie halten“; über die Linienzahl steigt es von 28,7 % (4 Linien) auf 98,6 % (10 Linien), nicht streng monoton. Außerhalb der Messreihe und der M-Regler der App nachgerechnet (normale Puffer, Phasen-Optimum, je 100 Störtage): bei M = 200 ist „immer halten“ in 23 von 28 Netzen billiger als „nie halten“, bei M = 300 in 28 von 28 |
| H4 | Die Gegenrechnung im eigenen Zug versagt bei knappen Puffern und Netzen mit vielen Linien | **Ja bei knappen Puffern, nicht trennbar bei normalen** (der Takt „Dichter Takt“ der App, also die Aufteilung der Wende-Standzeit, ist etwas anderes als Netze mit vielen Linien). Knapp: `bal2` 8,6 ± 1,4 % gegen 3,0 ± 0,3 % für das im Rückblick beste W, auch schlechter als „nie halten“ mit 5,8 %; die Differenz je Netz beträgt 5,6 ± 1,4 Prozentpunkte, in 6 von 28 Netzen ist `bal2` besser. Normal: `bal2` 3,9 ± 0,7 % gegen 3,1 ± 0,4 %; die Differenz 0,7 ± 0,8 Prozentpunkte ist nicht von null trennbar (13 von 28 Netzen `bal2` besser). Über die Linienzahl steigt `bal2` von 1,4 % (4 Linien) auf 8,1 % (10 Linien) bei normalen und von 2,8 % auf 17,3 % bei knappen Puffern (nicht streng monoton). **Der Mechanismus (Folgeverspätungen dritter Züge) ist vermutet, nicht durch einen Eingriff geprüft** |
| H5 | Bekanntes M oder bekannte Folgezug-Verspätung rettet die Gegenrechnung | **Nicht neu gemessen.** `bal2` kennt M bereits; bei M = 10, 15 und 20 liegt sie gleichauf oder unter dem besten W. Die Vormessung `fahrplan-planung/vormessung/out_e6_folgezug_extern_auswertung.txt` (Gegenrechnung mit bekannter Folgezug-Verspätung wird nicht besser) steht nicht in diesem Repo |
| H6 | Ein Takt mit geringerer Planwartezeit macht mehr Anschlüsse kritisch | **Ja, zwischen Greedy und Phasen-Optimum ist der Unterschied gering.** Kritische Anschlüsse je Störtag bei zufälligen Phasen 7,8, Greedy 16,4, Phasen-Optimum 16,6, Phasen + Aufteilung 35,5 (Phasen-Optimum gegen Greedy in 17 von 28 Netzen höher); Plan-Umsteigezeit 31,2, 23,3, 22,8, 17,9 min je Umsteiger |
| H7 | Der bessere Takt zahlt sich trotzdem aus | **Nur, wenn Störtage selten genug sind; die Häufigkeit ist eine Annahme, nicht gemessen.** Zufällige Phasen → Phasen-Optimum: Plan-Umsteigezeit −22,7 %, Verspätungskosten je Störtag +17,9 % (Basis: Takt davor), Gleichstand bei 8,6 Störtagen je Horizont; Phasen-Optimum → Aufteilung: −17,8 % und +25,6 %, Gleichstand bei 3,1. Die Verspätungskosten steigen in 27 von 28 Netzen; es sind die des Optimums (bestmögliche Disposition), nicht die einer Regel. Greedy → Phasen-Optimum: Verspätungskosten −2,1 ± 1,7 % (nicht von null trennbar; in 17 von 28 Netzen billiger, in 11 teurer) |
| H8 | „Folgezug pünktlich“ stützt den Befund | **Ja, soweit die Erweiterung reicht.** Beste Regel in der Erweiterung `p_5` 3,2 ± 0,4 %; die Entscheidung des Grundmodell-Optimums ist im erweiterten Modell nur 0,03 % (knapp 0,05 %, dort in 17 von 2 721 Störtagen das erweiterte Optimum nicht bewiesen) schlechter als das erweiterte Optimum. **Der Test ist schwach:** D′ ist im Mittel 0,49 min (knapp 1,38), nur 4,9 % (11,9 %) des Gewichts haben D′ > 0, und 32,1 % des Umsteigergewichts haben keine nächste Fahrt im Horizont |
| H9 | Das Optimum je Störtag ist live rechenbar | **Ja für fast alle Störtage der Messreihe (1 bis 8 Primärverspätungen).** Im vorgerechneten Lauf blieb bei normalen Puffern kein Störtag nach 60 s unbewiesen, bei knappen Puffern einer von 2 721; live gilt ein Limit von 10 s, danach die Anzeige „nicht bewiesen“. Die Messreihe deckt das Reglermaximum von 16 Primärverspätungen nicht ab: bei knappen Puffern und 10 Linien blieb dort in einer Stichprobe der unabhängigen Prüfung etwa jeder dritte bis zweite Störtag unbewiesen (nicht Teil der Messreihe). Rechenzeiten hängen von Maschine und Last ab und stehen hier nicht |
| H10 | Die Lücke der Regel hängt an der Linienzahl | **Offen.** Normale Puffer: Rangkorrelation (Spearman, mittlere Ränge bei gleicher Linienzahl) zwischen Linienzahl und Abstand von `p_5` über die 28 Netze −0,12 (kein Trend); knappe Puffer +0,45 |
| H11 | Welche Haltestelle bei Gleichstand gewählt wird, ändert den Befund | **Nein** (Vormessung `out_e6_konsistenz_auswertung.txt`: `p_5` 2,81 → 2,77 %); in diesem Repo nicht neu gemessen, die Ableitung ist hier nur einmal vorhanden (Test mit Gleichstandspaar) |

## Befunde und Korrekturen

- **Streuung je Störtag.** Der Netz-Mittelwert verbirgt die Verteilung (Störtage mit Optimumskosten > 0, normale Puffer): `p_5` trifft das Optimum in 39,5 % der Störtage (35,1 % der Störtage mit mindestens einem kritischen Anschluss; Lücke im Median 0,8 %, P90 8,1 %, P99 26,6 %, Maximum 91,5 %); die Gegenrechnung `bal2` trifft es in 49,7 % (46,0 % der Störtage mit mindestens einem kritischen Anschluss; Median 0,02 %, aber P99 54,3 % und Maximum 250,7 %). Der Mittelwert von `bal2` liegt etwas höher (nicht von `p_5` trennbar, siehe H4); `bal2` trifft häufiger, hat aber den dickeren Tail. Bei knappen Puffern trifft `p_5` das Optimum in 17,4 % der Störtage (15,0 % der Störtage mit mindestens einem kritischen Anschluss).
- **Basis der Prozentzahl.** Frühere Notizen nannten „11,0 %“ und „11,7 %“ als „Optimum unter nie“; das mischte zwei Basen („nie halten liegt 11,0 % über dem Optimum“ gegen „das Optimum liegt 11,7 % unter nie halten“). Auf der Basis „Optimum unter nie halten“ liefern drei Netzsätze 9,9 / 11,7 / 10,3 % (Quellen: Vormessung `out_e6_basis_okt.txt` 9,9 %, `fahrplan-planung/PLAN.md` 11,7 %, Vormessung `out_e6_folgezug_auswertung.txt` 10,3 %), dieser Lauf 10,4 %. Im Text steht immer die Basis.
- **„Immer halten“.** Frühere Notizen nannten „+31 bis +89 %“ je Liniengröße und auf dem dritten Netzsatz „+28 bis +107 %“ (nicht in diesem Repo, hier nicht nachgeprüft); stabil ist nur die Richtung (wächst mit der Linienzahl), nicht die Spanne. Dieser Lauf: 28,7 bis 98,6 % je Linienzahl (Netz-Mittel über 4 Netze).
- **„Plan-Puffer aus dem Takt eher groß“** gilt nur für das Phasen-Optimum ohne Aufteilung; der Anteil des Umsteigergewichts mit Puffer ≤ 5 min liegt bei zufälligen Phasen bei 0,117, beim Phasen-Optimum bei 0,266 und mit Aufteilung bei 0,447.
- **Feste Schwelle.** Die „beste“ Regel ist im Rückblick gewählt; mit falsch angenommenem M kostet eine feste Schwelle bis zu 4,2 Prozentpunkte (H2).

## Ehrliche Grenzen

- **M ist eine Annahme.** Wer den Anschluss verpasst, verliert genau M Minuten (10 bis 120 wählbar); der Folgezug fährt pünktlich. Die Erweiterung (Folgezug verspätet) verschiebt den Abstand der besten festen Regel zum Optimum nur von 3,1 auf 3,2 % (E5), ersetzt aber keine Betriebsdaten.
- **Keine Trassenkonflikte:** Ein wartender Zug blockiert keine anderen Züge, es gibt keine Überholungen, Kapazitäten oder Zugfolgezeiten. Reale Kettenwirkungen sind eher unterschätzt.
- **Keine Umlegung** der Fahrgäste auf andere Wege, keine Wartezeitobergrenze; **Gewichte relativ** (Nachfrage-Generator mit zwei Hubs), keine echten Fahrgastzahlen. Verspätungen nur als Primärverspätungen an Abfahrten der ersten zwei Stunden, 3 bis 30 min gleichverteilt (in der Messreihe 1 bis 8 je Störtag).
- **Die Regeln kennen die Zubringerverspätung exakt** (vollinformiert) und sehen nur den eigenen Anschluss; das Optimum sieht alle Entscheidungen des Tages und die ganze Störung im Voraus, ist also **kein online umsetzbares Verfahren**, sondern der Maßstab.
- **Alle Linien haben 6 Haltestellen** (80 Ereignisse je Linie im Horizont, 320 bis 800 je Netz); synthetische Netze mit 16 bis 24 Haltestellen (live 20). Die Befunde gelten für diese Netze und diesen Generator, nicht für reale Netze; die Zahlen sind keine Prognose.
- **Die „beste Regel“ ist im Rückblick gewählt** (Minimum über W auf denselben Störtagen); im Einsatz kennt niemand M. Die Streuung je Störtag ist groß: Die Lücke von p_5 zum Optimum liegt im Median bei 0,8 %, im P90 bei 8,1 %, im P99 bei 26,6 % und im Maximum bei 91,5 % (Basis: Optimum des Störtags, M = 60, normale Puffer).
- **Das Optimum läuft live mit Zeitlimit** (10 s je Störtag); danach zeigt die App die beste gefundene Entscheidung und „nicht bewiesen“. Die vorgerechnete Messreihe lief mit 60 s Limit. Bei bis zu 16 Primärverspätungen (Reglermaximum), knappen Puffern und 10 Linien blieb in einer Stichprobe der unabhängigen Prüfung etwa jeder dritte bis zweite Störtag unbewiesen (nicht Teil der Messreihe).

## Verifikation

- **Kern gegen Handrechnung:** Mini-Instanz mit 6 Ereignissen und 3 Anschlüssen (`tests/conftest.py`): alle acht Mengen gehaltener Anschlüsse (600 / 405 / 420), Regeln `p_5` 420 und Gegenrechnung 405, Optimum 405; Erweiterung an einer zweiten Handinstanz (Optimum 420 statt 405).
- **Orakel** (`tests/test_oracle_delay_management.py`, zweiter Rechenweg in reinem Python): Fortpflanzung, Kosten und Regeln gegen die Modellbeschreibung; das Optimum gegen die Aufzählung **aller** Teilmengen **aller** Anschlüsse auf 60 Zufalls-Mini-Netzen × 3 Störtage × 3 Werte von M, die Erweiterung auf 60 Netzen × 2 Störtagen, das Optimum gegen die Aufzählung der kritischen Teilmengen auf drei kleinen echten Netzen, die Umsteigeaktivitäten gegen eine Neuherleitung auf sechs Netzen. Der Aufbau des Ereignisnetzes stimmt mit der Messreihe `schiene-planung/messreihe_delay/delaylib.py` überein (Vergleich einmalig im Scratch-Lauf, nicht im Repo: 5 Netze in beiden Puffervarianten: Netzaufbau, Regeln und Kosten auf 12 Störtagen je Netz, Optimum auf den ersten 4).
- **Zweig-Tests** (`tests/test_branches.py`): jede Regel weicht von „nie halten“ ab, die Spalte `p_W` ist nicht konstant, das Optimum schlägt „nie“ und „immer“ strikt, die Erweiterung ändert Störtage, die Takt-Stufen unterscheiden sich in den kritischen Anschlüssen, knappe Puffer machen mehr Anschlüsse kritisch.
- **Messreihe:** `tests/test_results.py` bindet `data/anh_results.json` per Prüfsumme an den Stand des Codes; `tests/test_claims.py` rechnet jede Zahl dieser README aus der Datei nach.
- **Oberfläche:** AppTest-Rauchtest (jeder Knopf, jeder Regler an Minimum und Maximum, jede Regel, jede Takt-Stufe, Permalink, der Live-Knopf einzeln), Layout (Schnellstart oben in der Seitenleiste, aktives Preset hervorgehoben), Footer, Laufzeit-Importe.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore`, `.streamlit/config.toml` | venv, Caches; Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `anh_rng.py`, `anh_timetable.py`, `anh_takt.py` | aus `taktfahrplan-demo` kopiert und angepasst: SplitMix64, Takt-Zeitmodell, Takt-Stufen |
| `anh_network.py` | Netzgenerator (kopiert), `route_pairs` (die eine Ableitung der Routen), Ereignisnetz |
| `anh_scenario.py`, `anh_propagate.py`, `anh_rules.py`, `anh_exact.py` | Störtage, Fortpflanzung und Kosten, Regeln, Optimum (CP-SAT) und Aufzählung |
| `anh_measure.py`, `anh_results.py`, `tools/build_results.py`, `data/anh_results.json` | Messreihe je Netz, Auswertung, Vorrechnung, Ergebnisdatei |
| `anh_constants.py`, `anh_presets.py`, `anh_layout.py`, `anh_evaluation.py`, `anh_visualization.py`, `anh_pdf_export.py` | Konstanten und Presets, Permalink, fester Kopf, Live-Rechnung und Verdikte, Abbildungen, PDF |
| `app.py` | Streamlit-App |
| `requirements.txt`, `requirements-dev.txt` | Laufzeit-Bibliotheken (ungepinnt) und Tests |
| `tests/` | Handrechnung, Orakel, Zweige, Ergebnisdatei, Claims, Oberfläche |

## Bewusst nicht umgesetzt

- **Trassenkonflikte** (ein wartender Zug blockiert andere): gehört in einen eigenen Baustein (`trassenkonflikt-demo`).
- **Fahrgastumlegung** auf andere Wege, echte Fahrgastzahlen, Wartezeitobergrenzen.
- **Fahrzeugumlauf im Detail** (hier nur als Aktivität Wende/Umlauf mit Mindestwende).
- **Online-Regeln ohne Kenntnis der Zubringerverspätung** und Verfahren, die nur Teile des Tages im Voraus kennen (rollierender Horizont).
- **Folgezug-Verspätung von außen** (unabhängig vom Netz gezogen): in der Vormessung `fahrplan-planung/vormessung/e6_folgezug_extern.py` gemessen, in der App nur die aus der Fortpflanzung abgeleitete Form.
- **Quellenlage:** Autoren und Jahre der Literatur zum Delay Management sind in dieser Demo nicht im Volltext geprüft und deshalb nicht genannt.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Die Messreihe (`data/anh_results.json`) ist beigelegt; neu erzeugen mit `python tools/build_results.py` (mehrere Minuten, zwei Prozesse).

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy und OR-Tools (CP-SAT).

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html).
