# To-dos „We Be(a)t“

Stand: 16.11.2026

Die To-dos sind nach den vier Arbeitsbereichen sortiert und innerhalb eines Bereichs in der empfohlenen Reihenfolge. Die Aufteilung selbst steht in der [README.md](README.md), der Stand aller Funktionen in der [FEATURES.md](FEATURES.md), Entscheidungen in der [DECISIONS.md](DECISIONS.md).

Wer ein To-do übernimmt, schreibt seinen Namen dahinter. „Wartet auf“ heißt: erst anfangen, wenn der genannte Punkt erledigt ist.

## Zuerst gemeinsam klären

Diese Punkte blockieren To-dos in mehreren Bereichen. Entscheidung in die DECISIONS.md eintragen.

- [ ] **K1** Datenmodell für Beweis-Feld und Ergebnis-Tipp festlegen: welche Felder bekommt eine Wette? (Bereich 2, 3, 4)
- [ ] **K2** Regel für den Ergebnis-Tipp: Was passiert, wenn niemand das genaue Ergebnis trifft? (Bereich 2, 3)
- [ ] **K3** Optionen im Beweis-Dropdown festlegen (Bereich 2, 3)
- [ ] **K4** Adminbereich: nur für Admins sichtbar oder für alle mit eingeschränkten Rechten? (Bereich 4)
- [ ] **K5** Schuldenlimit: ja oder nein, und wie hoch? (Bereich 3)

## Bereich 1: Gruppen

Dateien: `js/home.js`, `js/group.js`

- [ ] **1.1** „Join Group“ auf der Startseite: Code eingeben und der Gruppe beitreten
- [ ] **1.2** Gruppenbeschreibung im Gruppen-Detail anzeigen
- [ ] **1.3** Gruppenbild als Platzhalter in Gruppenliste und Gruppen-Detail (wartet auf 4.2)
- [ ] **1.4** Eigenes Profilbild bei „Your balance in this group“ (wartet auf 4.2)
- [ ] **1.5** Gruppe verlassen, nur bei Saldo 0 und ohne offene eigene Wette
- [ ] **1.6** Tab „Members“ aus dem Gruppen-Detail entfernen und Einstieg in den Adminbereich einbauen (wartet auf 4.3)

## Bereich 2: Wetten erstellen und beitreten

Dateien: `js/bet-new.js`, `js/bet-detail.js`

- [ ] **2.1** Reallife: Feld „Beweis“ als Dropdown im Formular (wartet auf K1, K3)
- [ ] **2.2** Beweis-Art im Wett-Detail anzeigen (wartet auf 2.1)
- [ ] **2.3** Event: genaues Ergebnis beim Erstellen tippen können (wartet auf K1, K2)
- [ ] **2.4** Event: genaues Ergebnis beim Beitreten tippen können (wartet auf 2.3)
- [ ] **2.5** Tipps der Teilnehmer im Wett-Detail anzeigen (wartet auf 2.3)
- [ ] **2.6** Reallife: mehr als zwei Ausgänge erlauben

## Bereich 3: Auflösung, Salden und Ausgleich

Dateien: `js/logic.js`, `js/bet-resolve.js`, `js/settle.js`

- [ ] **3.1** Gewinnregel für den Ergebnis-Tipp in der Topf-Berechnung umsetzen (wartet auf K1, K2)
- [ ] **3.2** Genaues Ergebnis bei der Auflösung eingeben können statt nur eine Seite zu wählen (wartet auf 3.1)
- [ ] **3.3** Gewählte Beweis-Art beim Melden und Bestätigen des Ergebnisses anzeigen (wartet auf K1, K3)
- [ ] **3.4** Schuldenlimit beim Beitreten und Erstellen prüfen (wartet auf K5)
- [ ] **3.5** Salden-Tab: vorgemerkte Einsätze in offenen Wetten anzeigen
- [ ] **3.6** Kontoverlauf: Eintrag antippen und zur zugehörigen Wette springen

## Bereich 4: Profil, Admin und Fundament

Dateien: `index.html`, `css/styles.css`, `js/core.js`, `js/data.js`, `js/members.js`, `js/main.js`

- [ ] **4.1** Datenmodell nach K1 in `data.js` erweitern und Beispieldaten anpassen (wartet auf K1)
- [ ] **4.2** Baustein für Profil- und Gruppenbilder als Platzhalter bereitstellen (z. B. Initialen im Kreis)
- [ ] **4.3** Adminbereich pro Gruppe anlegen und „Mitglieder“ mit Einladungscode dorthin verschieben (wartet auf K4)
- [ ] **4.4** Profil-Option oben rechts in der Kopfzeile, mit einfachem Profil-Screen (Name, Platzhalter-Bild)
- [ ] **4.5** Gruppe bearbeiten und löschen im Adminbereich (wartet auf 4.3)
- [ ] **4.6** Pull Requests der anderen Bereiche prüfen und mergen (laufend)

## Später

Diese Punkte brauchen einen Server oder eine offene Grundsatzentscheidung und haben noch keinen Bereich.

- [ ] Technik für die echte App entscheiden (Server, Konten, App-Stores)
- [ ] Registrierung, Login, Altersbestätigung 18+
- [ ] Echte Einladungen per Link
- [ ] Sportdaten-Quelle für Events und Ergebnisse
- [ ] Zeitgesteuerte Abläufe: Annahmeschluss, automatische Bestätigung nach 48 Stunden
- [ ] Push-Benachrichtigungen
- [ ] Foto-Upload für Beweise
- [ ] Rechtliche Prüfung, falls Gruppen in echtem Geld ausgleichen

## Erledigt

- [x] App-Name von „Wettrunde“ in „We Be(a)t“ umbenennen
- [x] Alle Texte der App auf Englisch schreiben
- [x] Salden und Einsätze in fiktiven Euro-Beträgen statt in Credits anzeigen
- [x] Prototyp in eine Datei pro Bereich aufteilen
