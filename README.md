# We Be(a)t

Wett-App für Freundesgruppen: Event- und Reallife-Wetten, abgerechnet in fiktiven Euro, am Ende per Ausgleichszahlung beglichen.

Aktuell ist das ein klickbarer Prototyp ohne Server und ohne Konten. Er läuft mit Beispieldaten, Eingaben bleiben nur im eigenen Browser gespeichert.

## Starten

`prototype/index.html` im Browser öffnen. Es gibt keinen Build-Schritt.

## Aufbau und Zuständigkeiten

Jede Datei gehört zu genau einem Bereich. Wer etwas in einer fremden Datei braucht, spricht es mit dem Bereich ab, statt es selbst zu ändern.

| Datei | Inhalt | Bereich |
|---|---|---|
| `prototype/js/home.js` | Startseite, Gruppe erstellen | 1 Gruppen |
| `prototype/js/group.js` | Gruppen-Detail, Wettliste, Tabs | 1 Gruppen |
| `prototype/js/bet-new.js` | Formular „Create bet“ für Event und Reallife | 2 Wetten erstellen und beitreten |
| `prototype/js/bet-detail.js` | Wett-Detail bis zum Annahmeschluss: beitreten, zurückziehen, stornieren | 2 Wetten erstellen und beitreten |
| `prototype/js/logic.js` | Regeln: Topf-Aufteilung, Auflösung, Annahmeschluss, Ausgleichsvorschläge | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/bet-resolve.js` | Wett-Detail ab „Locked“: Ergebnis melden, bestätigen, Einspruch | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/settle.js` | Salden, Kontoverlauf, „Settle up“ | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/members.js` | Mitgliederliste, Einladungscode (wird zum Adminbereich) | 4 Profil, Admin, Fundament |
| `prototype/js/core.js` | Zustand, Speicherung, Hilfsfunktionen, Navigation | 4 Profil, Admin, Fundament |
| `prototype/js/data.js` | Beispieldaten, Konstanten, Datenmodell | 4 Profil, Admin, Fundament |
| `prototype/css/styles.css` | Farben, Schriften, gemeinsame Bausteine | 4 Profil, Admin, Fundament |
| `prototype/index.html`, `prototype/js/main.js` | Seitengerüst, Ladereihenfolge, Start | 4 Profil, Admin, Fundament |

## So hängen die Dateien zusammen

- Die Skripte sind normale `<script>`-Dateien ohne Module, damit die Seite per Doppelklick läuft. Alles auf oberster Ebene ist global, also auf eindeutige Namen achten.
- Ein Screen meldet sich mit `VIEWS.name = function () { ... }` an und gibt HTML zurück.
- Ein Klick-Handler meldet sich mit `Object.assign(A, { name(d) { ... } })` an. Im HTML löst ihn `data-a="name"` aus.
- Neue Dateien in `index.html` eintragen, vor `main.js`.

## Regeln für die Zusammenarbeit

- Ein Branch pro To-do, Merge per Pull Request. Niemand pusht direkt auf `main`.
- Änderungen am Datenmodell (`data.js`) vorher ankündigen, sie betreffen alle Bereiche.
- Texte in der App sind Englisch. Beträge sind fiktive Euro und laufen über die Hilfsfunktionen `eur()` und `sg()`.
- To-dos stehen in [TODO.md](TODO.md).
