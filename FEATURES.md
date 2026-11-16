# Funktionsübersicht „We Be(a)t“

Alle Funktionen der App mit ihrem Stand. Wer eine Funktion fertigstellt oder eine neue plant, aktualisiert die Zeile hier.

**Stand-Werte**

- **Vorhanden:** im Prototyp umgesetzt und durchklickbar.
- **Demo:** im Prototyp nur über die „Demo controls“ simuliert, weil es keinen Server, keine Zeit und keine anderen Nutzer gibt.
- **Geplant:** steht als To-do in der [TODO.md](TODO.md).
- **Später:** braucht einen Server oder eine offene Entscheidung, noch kein To-do.

## Bereich 1: Gruppen

| Funktion | Stand | Datei |
|---|---|---|
| Gruppenliste mit eigenem Saldo, Mitgliederzahl und offenen Wetten | Vorhanden | `js/home.js` |
| Gruppe erstellen (Name, Beschreibung), auch allein | Vorhanden | `js/home.js` |
| Hinweis „Wetten erst ab 2 Mitgliedern“ beim Erstellen und im Gruppen-Detail | Vorhanden | `js/home.js`, `js/group.js` |
| „Create bet“ und „Settle up“ gesperrt, solange man allein ist | Vorhanden | `js/group.js` |
| Gruppen-Detail mit eigenem Saldo und Tabs für Wetten, Salden, Mitglieder | Vorhanden | `js/group.js` |
| Wettliste mit Filter „All“, „Mine“, „Finished“ | Vorhanden | `js/group.js` |
| Einer Gruppe per Code oder Link beitreten („Join Group“) | Geplant | `js/home.js` |
| Gruppenbeschreibung im Gruppen-Detail anzeigen | Geplant | `js/group.js` |
| Gruppenbild (Platzhalter) | Geplant | `js/home.js`, `js/group.js` |
| Eigenes Profilbild beim Saldo (Platzhalter) | Geplant | `js/group.js` |
| Gruppe verlassen (nur bei Saldo 0 und ohne offene eigene Wette) | Geplant | `js/group.js` |

## Bereich 2: Wetten erstellen und beitreten

| Funktion | Stand | Datei |
|---|---|---|
| Wette erstellen mit Typwahl Reallife oder Event | Vorhanden | `js/bet-new.js` |
| Grunddaten: Name, Beschreibung, Mindest- und Höchsteinsatz | Vorhanden | `js/bet-new.js` |
| Reallife: zwei frei benennbare Ausgänge und Deadline | Vorhanden | `js/bet-new.js` |
| Event: Event aus einer Liste wählen, Ausgänge kommen vom Event | Vorhanden (Beispiel-Events) | `js/bet-new.js` |
| Eigene Seite und eigenen Einsatz beim Erstellen festlegen | Vorhanden | `js/bet-new.js` |
| Wett-Detail: Topf, Seiten mit Teilnehmern und Einsätzen, Status | Vorhanden | `js/bet-detail.js` |
| Eigener Einsatz und möglicher Gewinn | Vorhanden | `js/bet-detail.js` |
| Wette beitreten: Seite und Einsatz innerhalb der Grenzen wählen | Vorhanden | `js/bet-detail.js` |
| Einsatz zurückziehen, solange die Wette offen ist | Vorhanden | `js/bet-detail.js` |
| Wette stornieren (nur Ersteller, nur solange offen) | Vorhanden | `js/bet-detail.js` |
| Beitritt anderer Mitglieder | Demo | `js/bet-detail.js` |
| Annahmeschluss (Eventstart oder 24 h vor Deadline) | Demo | `js/bet-detail.js` |
| Reallife: Feld „Beweis“ als Dropdown | Geplant | `js/bet-new.js` |
| Event: genaues Ergebnis tippen (z. B. 2:1) | Geplant | `js/bet-new.js`, `js/bet-detail.js` |
| Reallife: mehr als zwei Ausgänge | Geplant | `js/bet-new.js` |

## Bereich 3: Auflösung, Salden und Ausgleich

| Funktion | Stand | Datei |
|---|---|---|
| Wette ohne Gegenspieler wird „Not feasible“ und geschlossen | Vorhanden | `js/logic.js` |
| Topf-Aufteilung anteilig nach Einsatz, mit Rundungsregel | Vorhanden | `js/logic.js` |
| Buchung der Salden bei Auflösung, Eintrag im Kontoverlauf | Vorhanden | `js/logic.js` |
| Wette ungültig, wenn niemand auf den Sieger-Ausgang gesetzt hat | Vorhanden | `js/logic.js` |
| Reallife: Ersteller meldet das Ergebnis | Vorhanden | `js/bet-resolve.js` |
| Reallife: Ergebnis bestätigen oder Einspruch einlegen | Vorhanden | `js/bet-resolve.js` |
| Event: Ergebnis aus der Sportdaten-Quelle | Demo | `js/bet-resolve.js` |
| Abstimmung nach Einspruch, ohne Mehrheit ungültig | Demo | `js/bet-resolve.js` |
| Automatische Bestätigung nach 48 Stunden | Später | `js/bet-resolve.js` |
| Ergebnis-Anzeige mit Gewinn und Verlust je Teilnehmer | Vorhanden | `js/bet-resolve.js` |
| Salden aller Mitglieder und Kontoverlauf | Vorhanden | `js/settle.js` |
| „Settle up“: Vorschlag der wenigsten Zahlungen | Vorhanden | `js/logic.js`, `js/settle.js` |
| Zahlung als bezahlt markieren, Empfänger bestätigt | Vorhanden (Bestätigung anderer: Demo) | `js/settle.js` |
| Gewinnregel für den Ergebnis-Tipp | Geplant | `js/logic.js` |
| Gewählte Beweis-Art beim Melden und Bestätigen anzeigen | Geplant | `js/bet-resolve.js` |
| Schuldenlimit je Gruppe | Geplant | `js/logic.js` |

## Bereich 4: Profil, Admin und Fundament

| Funktion | Stand | Datei |
|---|---|---|
| Navigation zwischen den Screens, Zurück-Knopf | Vorhanden | `js/core.js` |
| Speicherung im Browser, „Reset example data“ | Vorhanden | `js/core.js` |
| Beispieldaten und Datenmodell | Vorhanden | `js/data.js` |
| Farbschema, Schriften, gemeinsame Bausteine (Karten, Knöpfe, Tabs, Status-Pillen) | Vorhanden | `css/styles.css` |
| Mitgliederliste mit Admin-Kennzeichnung | Vorhanden | `js/members.js` |
| Einladungscode anzeigen und kopieren | Vorhanden | `js/members.js` |
| Beitritt eines neuen Mitglieds | Demo | `js/members.js` |
| Profil-Option oben rechts | Geplant | `js/core.js`, neue Datei `js/profile.js` |
| Baustein für Profil- und Gruppenbilder (Platzhalter) | Geplant | `js/core.js`, `css/styles.css` |
| Adminbereich pro Gruppe, „Mitglieder“ zieht dorthin um | Geplant | `js/members.js` |
| Gruppe bearbeiten und löschen | Geplant | `js/members.js` |
| Registrierung, Login, Altersbestätigung 18+ | Später | — |
| Echte Einladungen per Link | Später | — |
| Push-Benachrichtigungen | Später | — |
| Server und gemeinsame Daten für alle Nutzer | Später | — |
