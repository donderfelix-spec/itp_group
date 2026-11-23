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
| Gruppen-Detail mit eigenem Saldo und Tabs für Wetten und Salden | Vorhanden | `js/group.js` |
| Wettliste mit Filter „All“, „Mine“, „Finished“ | Vorhanden | `js/group.js` |
| „Create bet“ als Plus neben den Filtern, „Settle up“ in der Saldo-Kachel | Vorhanden | `js/group.js` |
| Offene Wetten ohne eigene Teilnahme zeigen „Tap to join“ | Vorhanden | `js/group.js` |
| Einer Gruppe per Einladungscode beitreten („Join group“) | Vorhanden (Beispiel-Code `KICK-3305`) | `js/home.js` |
| Gruppenbeschreibung im Gruppen-Detail anzeigen | Vorhanden | `js/group.js` |
| Gruppenbild (Platzhalter mit Initialen) | Vorhanden | `js/home.js`, `js/group.js` |
| Eigenes Profilbild beim Saldo (Platzhalter mit Initialen) | Vorhanden | `js/group.js` |
| Gruppe verlassen (nur bei Saldo 0 und ohne Einsatz in einer laufenden Wette) | Vorhanden | `js/group.js` |
| Einstieg in den Adminbereich (nur für den Admin) | Vorhanden | `js/group.js` |

## Bereich 2: Wetten erstellen und beitreten

| Funktion | Stand | Datei |
|---|---|---|
| Wette erstellen mit Typwahl Reallife oder Event | Vorhanden | `js/bet-new.js` |
| Grunddaten: Name, Beschreibung, Mindest- und Höchsteinsatz | Vorhanden | `js/bet-new.js` |
| Reallife: zwei bis fünf frei benennbare Ausgänge und Deadline | Vorhanden | `js/bet-new.js` |
| Event: Event aus einer Liste wählen, Ausgänge kommen vom Event | Vorhanden (Beispiel-Events) | `js/bet-new.js` |
| Eigene Seite und eigenen Einsatz beim Erstellen festlegen | Vorhanden | `js/bet-new.js` |
| Wett-Detail: Topf, Seiten mit Teilnehmern und Einsätzen, Status | Vorhanden | `js/bet-detail.js` |
| Eigener Einsatz und möglicher Gewinn | Vorhanden | `js/bet-detail.js` |
| Wette beitreten: Seite oder Tipp und Einsatz innerhalb der Grenzen wählen | Vorhanden | `js/bet-detail.js` |
| Einsatz zurückziehen, solange die Wette offen ist | Vorhanden | `js/bet-detail.js` |
| Wette stornieren (nur Ersteller, nur solange offen) | Vorhanden | `js/bet-detail.js` |
| Beitritt anderer Mitglieder | Demo | `js/bet-detail.js` |
| Annahmeschluss (Eventstart oder 24 h vor Deadline) | Demo | `js/bet-detail.js` |
| Reallife: Feld „Proof“ als Dropdown (Teilnehmer, Foto, Video), Anzeige im Wett-Detail | Vorhanden | `js/bet-new.js`, `js/bet-detail.js` |
| Event: genaues Ergebnis tippen (z. B. 2:1) beim Erstellen und Beitreten, Tipps im Wett-Detail | Vorhanden | `js/bet-new.js`, `js/bet-detail.js` |

## Bereich 3: Auflösung, Salden und Ausgleich

| Funktion | Stand | Datei |
|---|---|---|
| Wette ohne Gegenspieler (niemand beigetreten, gleiche Seite oder gleicher Tipp) wird „Not feasible“ und geschlossen | Vorhanden | `js/logic.js` |
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
| Ergebnis-Tipp: der nächste Tipp gewinnt (erst Tendenz, dann Tor-Abstand), gleich nahe Tipps teilen | Vorhanden | `js/logic.js` |
| Ergebnis-Tipp: Endstand bei der Auflösung eingeben | Demo | `js/bet-resolve.js` |
| Gewählte Beweis-Art beim Melden und Bestätigen anzeigen | Vorhanden | `js/bet-resolve.js` |
| Schuldenlimit je Gruppe, geprüft beim Erstellen und Beitreten | Vorhanden | `js/logic.js` |
| Einsätze in laufenden Wetten im Salden-Tab | Vorhanden | `js/settle.js` |
| Eintrag im Kontoverlauf öffnet die zugehörige Wette | Vorhanden | `js/settle.js` |

## Bereich 4: Profil, Admin und Fundament

| Funktion | Stand | Datei |
|---|---|---|
| Navigation zwischen den Screens, Zurück-Knopf | Vorhanden | `js/core.js` |
| Speicherung im Browser, „Reset example data“ | Vorhanden | `js/core.js` |
| Beispieldaten und Datenmodell | Vorhanden | `js/data.js` |
| Farbschema, Schriften, gemeinsame Bausteine (Karten, Knöpfe, Tabs, Status-Pillen) | Vorhanden | `css/styles.css` |
| Adminbereich pro Gruppe, nur für den Admin | Vorhanden | `js/admin.js` |
| Mitgliederliste mit Admin-Kennzeichnung im Adminbereich | Vorhanden | `js/admin.js` |
| Einladungscode anzeigen und kopieren | Vorhanden | `js/admin.js` |
| Beitritt eines neuen Mitglieds | Demo | `js/admin.js` |
| Profil-Option oben rechts auf jedem Screen | Vorhanden | `js/core.js` |
| Profilbild hochladen über das Plus am Profilbild, entfernen möglich (nur in diesem Browser gespeichert) | Vorhanden | `js/profile.js` |
| Konto löschen mit Rückfrage, nur ohne offene Salden und laufende Einsätze | Demo | `js/profile.js` |
| Logout im Profil mit Login-Screen (Attrappe, da es noch keine Konten gibt) | Demo | `js/profile.js` |
| Profil-Screen: Anzeigename ändern, Saldo über alle Gruppen, Anzahl Gruppen und laufender Wetten | Vorhanden | `js/profile.js` |
| Baustein für Profil- und Gruppenbilder (Platzhalter mit Initialen) | Vorhanden | `js/core.js`, `css/styles.css` |
| Gruppe bearbeiten (Name, Beschreibung, Schuldenlimit) | Vorhanden | `js/admin.js` |
| Gruppe löschen, nur ohne laufende Wetten und offene Salden | Vorhanden | `js/admin.js` |
| Registrierung, Login, Altersbestätigung 18+ | Später | — |
| Echte Einladungen per Link | Später | — |
| Push-Benachrichtigungen | Später | — |
| Upload von Profilbild, Gruppenbild und Beweisen | Später | — |
| Server und gemeinsame Daten für alle Nutzer | Später | — |
