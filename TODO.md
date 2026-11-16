# To-dos „We Be(a)t“

Stand: 16.11.2026

Die To-dos sind nach den vier Arbeitsbereichen sortiert. Die Aufteilung selbst steht in der [README.md](README.md), der Stand aller Funktionen in der [FEATURES.md](FEATURES.md), Entscheidungen in der [DECISIONS.md](DECISIONS.md).

Wer ein To-do übernimmt, schreibt seinen Namen dahinter.

## Vom Team zu bestätigen

Die fünf Klärungspunkte wurden beim Umsetzen mit einem Vorschlag entschieden, damit die To-dos nicht blockiert sind. Bitte bestätigen oder ändern, dann den Eintrag in der DECISIONS.md von „Vorschlag“ auf „Team“ setzen.

- [ ] **K1** Datenmodell für Beweis-Feld und Ergebnis-Tipp (E-35)
- [ ] **K2** Regel für den Ergebnis-Tipp: der nächste Tipp gewinnt (E-36, E-37)
- [ ] **K3** Optionen im Beweis-Dropdown: Bestätigung durch Teilnehmer, Foto, Video (E-38)
- [ ] **K4** Adminbereich nur für den Admin sichtbar (E-39)
- [ ] **K5** Schuldenlimit je Gruppe, Standard 500 €, vom Admin einstellbar (E-40)

## Bereich 1: Gruppen

Dateien: `js/home.js`, `js/group.js`

_Keine offenen To-dos._

## Bereich 2: Wetten erstellen und beitreten

Dateien: `js/bet-new.js`, `js/bet-detail.js`

_Keine offenen To-dos._

## Bereich 3: Auflösung, Salden und Ausgleich

Dateien: `js/logic.js`, `js/bet-resolve.js`, `js/settle.js`

_Keine offenen To-dos._

## Bereich 4: Profil, Admin und Fundament

Dateien: `index.html`, `css/styles.css`, `js/core.js`, `js/data.js`, `js/admin.js`, `js/profile.js`, `js/main.js`

- [ ] **4.6** Pull Requests der anderen Bereiche prüfen und mergen (laufend)

## Alle Bereiche

- [ ] Den Prototyp einmal vollständig im Browser auf dem Handy durchklicken. Die Abläufe wurden bisher nur per Skript geprüft, das Aussehen noch nicht.

## Später

Diese Punkte brauchen einen Server oder eine offene Grundsatzentscheidung und haben noch keinen Bereich.

- [ ] Technik für die echte App entscheiden (Server, Konten, App-Stores)
- [ ] Registrierung, Login, Altersbestätigung 18+
- [ ] Echte Einladungen per Link
- [ ] Sportdaten-Quelle für Events und Ergebnisse
- [ ] Zeitgesteuerte Abläufe: Annahmeschluss, automatische Bestätigung nach 48 Stunden
- [ ] Push-Benachrichtigungen
- [ ] Upload von Profilbild, Gruppenbild und Foto- oder Video-Beweis
- [ ] Rechtliche Prüfung, falls Gruppen in echtem Geld ausgleichen

## Erledigt

**Fundament**

- [x] App-Name von „Wettrunde“ in „We Be(a)t“ umbenennen
- [x] Alle Texte der App auf Englisch schreiben
- [x] Salden und Einsätze in fiktiven Euro-Beträgen statt in Credits anzeigen
- [x] Prototyp in eine Datei pro Bereich aufteilen

**Bereich 1**

- [x] **1.1** „Join Group“ auf der Startseite: Code eingeben und der Gruppe beitreten
- [x] **1.2** Gruppenbeschreibung im Gruppen-Detail anzeigen
- [x] **1.3** Gruppenbild als Platzhalter in Gruppenliste und Gruppen-Detail
- [x] **1.4** Eigenes Profilbild bei „Your balance in this group“
- [x] **1.5** Gruppe verlassen, nur bei Saldo 0 und ohne Einsatz in einer laufenden Wette
- [x] **1.6** Tab „Members“ aus dem Gruppen-Detail entfernt, Einstieg in den Adminbereich eingebaut

**Bereich 2**

- [x] **2.1** Reallife: Feld „Proof“ als Dropdown im Formular
- [x] **2.2** Beweis-Art im Wett-Detail anzeigen
- [x] **2.3** Event: genaues Ergebnis beim Erstellen tippen
- [x] **2.4** Event: genaues Ergebnis beim Beitreten tippen
- [x] **2.5** Tipps der Teilnehmer im Wett-Detail anzeigen
- [x] **2.6** Reallife: bis zu fünf Ausgänge

**Bereich 3**

- [x] **3.1** Gewinnregel für den Ergebnis-Tipp in der Topf-Berechnung
- [x] **3.2** Genaues Ergebnis bei der Auflösung eingeben
- [x] **3.3** Beweis-Art beim Melden und Bestätigen des Ergebnisses anzeigen
- [x] **3.4** Schuldenlimit beim Beitreten und Erstellen prüfen
- [x] **3.5** Salden-Tab: Einsätze in laufenden Wetten anzeigen
- [x] **3.6** Kontoverlauf: Eintrag öffnet die zugehörige Wette

**Bereich 4**

- [x] **4.1** Datenmodell in `data.js` erweitert, Beispieldaten angepasst
- [x] **4.2** Baustein für Profil- und Gruppenbilder als Platzhalter (Initialen)
- [x] **4.3** Adminbereich pro Gruppe mit Mitgliedern und Einladungscode
- [x] **4.4** Profil-Option oben rechts mit Profil-Screen
- [x] **4.5** Gruppe bearbeiten und löschen im Adminbereich
