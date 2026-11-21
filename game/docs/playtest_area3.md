# Playtest-Protokoll: Area 3 Classic

Beide Skripte verwenden fünf Spieler (`Ari`, `Bea`, `Cal`, `Dev`, `Eli`), die
Stations-IDs 1–5 und Seed `20261119`. Die feste Rollenverteilung lautet vier
High Performer und ein Free Rider (`Dev`). Alle Zeiten sind simulierte Sekunden
ab Rundenstart; es gibt weder echte Wartezeiten noch einen Browser. Die
Spielerpositionen sind im Skript festgelegt, damit die Reichweitenprüfung für Q
reproduzierbar bleibt.

## Durchlauf A — Sieg der HP

| Zeit | Aktion | Ergebnis |
|---:|---|---|
| 00:00 | Runde mit Seed `20261119` starten | 4 HP, 1 FR (`Dev`) |
| 00:08 | FR drückt Q neben `Ari` | `Ari` wird Geist; ein F-Blatt erscheint an seiner Position; Durchfall-Zähler: 1 |
| 00:09 | `Bea` steht am F-Blatt und drückt R | Blatt wird entfernt; Besprechung beginnt; `Ari` ist Geist |
| 00:10 | `Bea` schreibt „I found the sheet by the library.“ | Nachricht erscheint im gemeinsamen Verlauf |
| 00:12 | FR schreibt „I was working near the cafe.“ | Nachricht erscheint im gemeinsamen Verlauf |
| 00:54 | 45 Sekunden Diskussion sind abgelaufen | Phase wechselt zu Voting |
| 00:54–01:24 | Die drei lebenden HP stimmen für den FR; der FR stimmt für `Bea` | Stimmen bleiben bis zur Auswertung verdeckt |
| 01:24 | 30 Sekunden Voting sind abgelaufen | FR wird ausgeschlossen; HP gewinnen; Endgrund `all_free_riders_eliminated` („Alle FR ausgeschlossen“) |

## Durchlauf B — Sieg der FR

| Zeit | Aktion | Ergebnis |
|---:|---|---|
| 00:00 | Neue Runde mit demselben Seed starten | Wieder 4 HP, 1 FR (`Dev`) |
| 00:10 | FR drückt Q neben `Ari` | Erfolg; Durchfall-Zähler: 1 |
| 00:34.999 | FR versucht Q gegen `Bea` | Abgelehnt: Cooldown läuft noch; State und Zähler bleiben unverändert |
| 00:35 | FR drückt Q gegen `Bea` | Erfolg, genau 25 Sekunden nach dem ersten Durchfall; Zähler: 2 |
| 01:00 | FR drückt Q gegen `Cal` | Erfolg, genau 25 Sekunden nach dem zweiten Durchfall; 1 HP und 1 FR leben |
| 01:00 | Siegesprüfung | FR gewinnen durch Parität; Endgrund `free_riders_reached_parity` („FR hat die Mehrheit erreicht“) |

## Ausführung

`uv run pytest tests/test_classic_playtest.py -q`

Die Szenarien rufen die serverseitige `ClassicRound`-Logik samt Regel- und
Besprechungsfunktionen mit einer Fake-Uhr auf. Sie testen keinen Browser und
starten keinen echten WebSocket-Server.
