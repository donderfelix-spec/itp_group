# To-dos Wett-App „We Be(a)t“

Stand: 16.11.2026

Die To-dos sind nach den vier Arbeitsbereichen sortiert. Welche Dateien zu welchem Bereich gehören, steht in der [README.md](README.md).

## Bereich 1: Gruppen

Dateien: `js/home.js`, `js/group.js`

- [ ] „Join Group“ ergänzen: einer bestehenden Gruppe per Einladungscode oder Link beitreten
- [ ] Gruppenbeschreibung im Gruppen-Detail anzeigen
- [ ] Gruppenbild ergänzen (vorerst Platzhalter)
- [ ] Eigenes Profilbild bei „Your balance in this group“ einbauen (Baustein kommt aus Bereich 4)

## Bereich 2: Wetten erstellen und beitreten

Dateien: `js/bet-new.js`, `js/bet-detail.js`

- [ ] Reallife-Wetten: eigenes Feld „Beweis“ als Dropdown, z. B. Foto-Beweis oder Bestätigung durch die Wett-Teilnehmer
- [ ] Event-Wetten: bei Events mit Spielstand auch das genaue Ergebnis tippen können (z. B. 2:1), Eingabe beim Erstellen und Beitreten

## Bereich 3: Auflösung, Salden und Ausgleich

Dateien: `js/logic.js`, `js/bet-resolve.js`, `js/settle.js`

- [ ] Gewinnregel für den Ergebnis-Tipp festlegen und umsetzen (nur exakt zählt, oder näher dran gewinnt)
- [ ] Gewählte Beweis-Art beim Melden und Bestätigen des Ergebnisses anzeigen
- [ ] Schuldenlimit je Gruppe entscheiden und umsetzen

## Bereich 4: Profil, Admin und Fundament

Dateien: `index.html`, `css/styles.css`, `js/core.js`, `js/data.js`, `js/members.js`, `js/main.js`

- [ ] Profil-Option oben rechts ergänzen
- [ ] Baustein für Profilbilder bereitstellen (vorerst Platzhalter, da es noch keine Profilbilder gibt)
- [ ] Adminbereich pro Gruppe ergänzen und den Bereich „Mitglieder“ dorthin verschieben
- [ ] Datenmodell für Beweis-Feld und Ergebnis-Tipp mit Bereich 2 und 3 abstimmen
- [ ] Pull Requests prüfen und mergen

## Offene Fragen

- Adminbereich: nur für Admins sichtbar, oder für alle mit eingeschränkten Rechten?
- Ergebnis-Tipp: Was passiert, wenn niemand das genaue Ergebnis trifft?

## Erledigt

- [x] App-Name von „Wettrunde“ in „We Be(a)t“ umbenennen
- [x] Alle Texte der App auf Englisch schreiben
- [x] Salden und Einsätze in fiktiven Euro-Beträgen statt in Credits anzeigen
- [x] Prototyp in eine Datei pro Bereich aufteilen
