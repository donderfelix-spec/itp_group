# We Be(a)t

Wett-App für Freundesgruppen: Event- und Reallife-Wetten, abgerechnet in fiktiven Euro, am Ende per Ausgleichszahlung beglichen.

Aktuell ist das ein klickbarer Prototyp ohne Server und ohne Konten. Er läuft mit Beispieldaten, Eingaben bleiben nur im eigenen Browser gespeichert.

## Starten

`prototype/index.html` im Browser öffnen. Es gibt keinen Build-Schritt.

## Dokumente

- [TODO.md](TODO.md): alle To-dos, sortiert nach Bereich
- [FEATURES.md](FEATURES.md): Übersicht aller Funktionen mit Stand
- [DECISIONS.md](DECISIONS.md): alle Entscheidungen mit Begründung

## Die vier Bereiche

| Bereich | Verantwortet | Grenze zu den anderen |
|---|---|---|
| 1 Gruppen | Startseite, Gruppe erstellen und beitreten, Gruppen-Detail mit Wettliste | Zeigt den Tab „Balances“ (Bereich 3) nur an und verlinkt in den Adminbereich (Bereich 4) |
| 2 Wetten erstellen und beitreten | Formular für Event- und Reallife-Wetten, Wett-Detail bis zum Annahmeschluss | Ab Status „Locked“ übernimmt Bereich 3 |
| 3 Auflösung, Salden und Ausgleich | Regeln und Berechnung, Wett-Detail ab „Locked“, Salden, Kontoverlauf, „Settle up“ | Bekommt die fertige Wette von Bereich 2 |
| 4 Profil, Admin und Fundament | Profil, Adminbereich mit Mitgliedern, Datenmodell, Styles, gemeinsame Bausteine, Pull Requests | Liefert Bausteine und Datenmodell an alle |

## Aufbau und Zuständigkeiten

Jede Datei gehört zu genau einem Bereich. Wer etwas in einer fremden Datei braucht, spricht es mit dem Bereich ab, statt es selbst zu ändern.

| Datei | Inhalt | Bereich |
|---|---|---|
| `prototype/js/home.js` | Startseite, Gruppe erstellen, Gruppe beitreten | 1 Gruppen |
| `prototype/js/group.js` | Gruppen-Detail, Wettliste, Tabs, Gruppe verlassen | 1 Gruppen |
| `prototype/js/bet-new.js` | Formular „Create bet“ für Event und Reallife | 2 Wetten erstellen und beitreten |
| `prototype/js/bet-detail.js` | Wett-Detail bis zum Annahmeschluss: beitreten, zurückziehen, stornieren | 2 Wetten erstellen und beitreten |
| `prototype/js/logic.js` | Regeln: Topf-Aufteilung, Ergebnis-Tipp, Auflösung, Annahmeschluss, Schuldenlimit, Ausgleichsvorschläge | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/bet-resolve.js` | Wett-Detail ab „Locked“: Ergebnis melden, bestätigen, Einspruch | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/settle.js` | Salden, Kontoverlauf, „Settle up“ | 3 Auflösung, Salden, Ausgleich |
| `prototype/js/admin.js` | Adminbereich: Gruppe bearbeiten und löschen, Mitglieder, Einladungscode, Schuldenlimit | 4 Profil, Admin, Fundament |
| `prototype/js/profile.js` | Profil-Screen | 4 Profil, Admin, Fundament |
| `prototype/js/core.js` | Zustand, Speicherung, Hilfsfunktionen, Navigation, Kopfzeile, Platzhalter-Bilder | 4 Profil, Admin, Fundament |
| `prototype/js/data.js` | Beispieldaten, Konstanten, Datenmodell | 4 Profil, Admin, Fundament |
| `prototype/css/styles.css` | Farben, Schriften, gemeinsame Bausteine | 4 Profil, Admin, Fundament |
| `prototype/index.html`, `prototype/js/main.js` | Seitengerüst, Ladereihenfolge, Start | 4 Profil, Admin, Fundament |

## So hängen die Dateien zusammen

- Die Skripte sind normale `<script>`-Dateien ohne Module, damit die Seite per Doppelklick läuft. Alles auf oberster Ebene ist global, also auf eindeutige Namen achten.
- Ein Screen meldet sich mit `VIEWS.name = function () { ... }` an und gibt HTML zurück.
- Ein Klick-Handler meldet sich mit `Object.assign(A, { name(d) { ... } })` an. Im HTML löst ihn `data-a="name"` aus.
- Ein Eingabefeld mit `data-m="draft.name"` schreibt seinen Wert nach `ui.draft.name`, ohne neu zu zeichnen.
- Neue Dateien in `index.html` eintragen, vor `main.js`.

## Automatische Checks

Bei jedem Pull Request und jedem Push auf `main` laufen auf GitHub zwei Prüfungen (`.github/workflows/ci.yml`):

- **Syntax check:** Jede Datei unter `prototype/js/` und `tests/` muss gültiges JavaScript sein.
- **Flow tests:** `tests/flows.js` spielt die Abläufe ohne Browser durch und prüft die Regeln, zum Beispiel Topf-Aufteilung, Ergebnis-Tipp, Schuldenlimit, „nicht durchführbar“, Ausgleich auf 0, Gruppe beitreten und verlassen.

Lokal laufen die Tests mit Node.js:

```bash
node tests/run.js
```

Wer eine Regel in `logic.js` ändert oder einen neuen Ablauf baut, ergänzt in `tests/flows.js` einen `check(...)` dazu. Das Aussehen prüfen die Tests nicht, das bleibt Handarbeit im Browser.

## Regeln für die Zusammenarbeit

- Ein Branch pro To-do, Merge per Pull Request. Niemand pusht direkt auf `main`.
- Änderungen am Datenmodell (`data.js`) vorher ankündigen, sie betreffen alle Bereiche.
- Texte in der App sind Englisch. Beträge sind fiktive Euro und laufen über die Hilfsfunktionen `eur()` und `sg()`.
- To-dos stehen in [TODO.md](TODO.md).
