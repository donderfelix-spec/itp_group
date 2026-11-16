# Entscheidungen „We Be(a)t“

Hier steht jede Entscheidung zum Projekt mit ihrer Begründung. Neue Entscheidungen kommen unten in die Tabelle ihres Themas, mit Datum.

**Regeln für dieses Dokument**

- Jede Entscheidung bekommt eine Nummer, ein Datum, die Entscheidung selbst und die Begründung.
- Einträge werden nicht gelöscht. Wird eine Entscheidung geändert, kommt ein neuer Eintrag dazu, und der alte bekommt den Vermerk „ersetzt durch E-xx“.
- Spalte „Von“: **Team** heißt vom Team so festgelegt. **Vorschlag** heißt von Claude vorgeschlagen und im Prototyp umgesetzt, aber vom Team noch nicht ausdrücklich bestätigt.
- Steht bei der Begründung „nicht festgehalten“, wurde sie im Gespräch nicht genannt. Bitte nachtragen.

## Geld und Abrechnung

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-01 | 16.11.2026 | Gewettet wird in einer fiktiven Währung. Die App hält, überweist und verdient kein Geld. | Sobald die App echtes Geld bewegt, greifen Glücksspiel- und Zahlungsdiensterecht mit Lizenzpflichten. | Team |
| E-02 | 16.11.2026 | Abrechnung wie bei Splitwise: Jeder startet in jeder Gruppe mit Saldo 0. Es gibt kein Startguthaben, keinen Bonus und keine Guthabenprüfung. | Das Team wollte ein einfaches Schuldenmodell statt eines Wallets mit Guthaben. | Team |
| E-03 | 16.11.2026 | Der Saldo ändert sich erst bei der Auflösung einer Wette. Beim Beitritt wird der Einsatz nur vorgemerkt. | Bei ungültigen oder nicht durchführbaren Wetten muss dann nichts zurückgebucht werden. | Vorschlag |
| E-04 | 16.11.2026 | Am Ende gibt es Ausgleichszahlungen. Die App schlägt die wenigsten Zahlungen vor, bezahlt wird außerhalb der App. | Folgt aus E-01 und E-02. Wenige Zahlungen sind für die Gruppe am bequemsten. | Team |
| E-05 | 16.11.2026 | Eine Ausgleichszahlung zählt erst, wenn der Empfänger sie bestätigt. | Schützt davor, dass jemand eine Zahlung als erledigt markiert, die nie ankam. | Vorschlag |
| E-06 | 16.11.2026 | Salden und Einsätze werden als fiktive Euro-Beträge angezeigt, nicht als Credits. | nicht festgehalten | Team |
| E-07 | 16.11.2026 | Topf-Modell: Alle Einsätze bilden einen Topf, die Gewinner teilen ihn anteilig nach ihrem Einsatz. Rundungsreste gehen an den Gewinner mit dem höchsten Einsatz. | Funktioniert mit beliebig vielen Teilnehmern und unterschiedlichen Einsätzen, ohne Quoten. Die Salden einer Gruppe ergeben so immer 0. | Vorschlag |
| E-08 | 16.11.2026 | Der Ersteller legt pro Wette einen Mindest- und Höchsteinsatz fest. | Begrenzt das Risiko pro Wette und erlaubt trotzdem unterschiedliche Einsätze. | Vorschlag |

## Gruppen

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-09 | 16.11.2026 | Eine Gruppe kann allein erstellt werden. Wetten sind erst ab 2 Mitgliedern möglich, darauf weist die App hin. | Man soll eine Gruppe anlegen und danach einladen können. Allein zu wetten ergibt keinen Sinn. | Team |
| E-10 | 16.11.2026 | Wer allein in einer Gruppe ist, kann nur Admin-Aufgaben erledigen (einladen, Gruppe verwalten). | Folgt aus E-09. | Team |
| E-11 | 16.11.2026 | Beitritt zu einer Gruppe nur per Einladung (Code oder Link), keine öffentliche Gruppensuche. | Die App ist für Freundesgruppen gedacht, nicht für Fremde. | Vorschlag |
| E-12 | 16.11.2026 | Der Ersteller einer Gruppe ist ihr Admin. | Es braucht jemanden, der die Gruppe verwalten darf. | Vorschlag |

## Wetten

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-13 | 16.11.2026 | Es gibt zwei Wett-Typen: Event-Wette und Reallife-Wette. Beim Erstellen wählt man zuerst den Typ. | Stand so in der ursprünglichen Skizze des Teams. Die Typen unterscheiden sich bei Annahmeschluss und Auflösung. | Team |
| E-14 | 16.11.2026 | Annahmeschluss bei Event-Wetten ist der Eventstart. | Nach dem Start wäre das Ergebnis absehbar. Stand so in der Skizze. | Team |
| E-15 | 16.11.2026 | Annahmeschluss bei Reallife-Wetten ist 24 Stunden vor der Deadline. | Stand so in der Skizze („24 h vor Fälligkeit nicht ändern“). | Team |
| E-16 | 16.11.2026 | Eine Wette lässt sich nach dem ersten fremden Beitritt nicht mehr ändern. Der Ersteller kann sie nur noch stornieren, solange sie offen ist. | Wer beigetreten ist, hat den Bedingungen zugestimmt, wie sie waren. | Vorschlag |
| E-17 | 16.11.2026 | Tritt bis zum Annahmeschluss niemand bei, wird die Wette als „nicht durchführbar“ markiert und geschlossen. Es wird nichts gebucht. | Ohne Gegenspieler gibt es nichts zu gewinnen oder zu verlieren. | Team |
| E-18 | 16.11.2026 | Dasselbe gilt, wenn zwar Leute beitreten, aber alle auf derselben Seite stehen. | Auch dann gibt es keinen Gegenspieler. Erweiterung von E-17. | Vorschlag |
| E-19 | 16.11.2026 | Man kann jede Wette, an der man beteiligt ist, jederzeit ansehen, egal in welchem Status. | Wunsch des Teams: bestehende Wetten sollen einsehbar sein. | Team |

## Auflösung

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-20 | 16.11.2026 | Event-Wetten werden nach dem Event automatisch aufgelöst (Ergebnis aus einer Sportdaten-Quelle). | Stand so in der Skizze („Auflösung nach Event“). Niemand muss das Ergebnis von Hand eintragen. | Team |
| E-21 | 16.11.2026 | Reallife-Wetten: Der Ersteller meldet das Ergebnis, die Teilnehmer bestätigen oder legen Einspruch ein. | Der Verlierer soll das Ergebnis nicht allein bestimmen können. | Vorschlag |
| E-22 | 16.11.2026 | Ohne Reaktion gilt ein gemeldetes Ergebnis nach 48 Stunden als bestätigt. | Sonst blockiert ein einzelner inaktiver Teilnehmer die Auflösung. | Vorschlag |
| E-23 | 16.11.2026 | Bei Einspruch stimmen alle Teilnehmer ab, die Mehrheit entscheidet. Ohne Mehrheit ist die Wette ungültig. | Einfachste Regel, die ohne Schiedsrichter von außen auskommt. | Vorschlag |
| E-24 | 16.11.2026 | Gewinnt ein Ausgang, auf den niemand gesetzt hat, ist die Wette ungültig und es wird nichts gebucht. | Es gibt keinen Gewinner, an den der Topf gehen könnte. | Vorschlag |

## Produkt und Gestaltung

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-25 | 16.11.2026 | Die App heißt „We Be(a)t“. | nicht festgehalten | Team |
| E-26 | 16.11.2026 | Alle Texte in der App sind Englisch. | nicht festgehalten | Team |
| E-27 | 16.11.2026 | Die App ist für das Handy optimiert. | Vorgabe des Teams für den ersten Draft. | Team |
| E-28 | 16.11.2026 | Auffälliges Farbschema: Schwarz mit Neongrün. | Vorgabe des Teams für den ersten Draft. | Team |
| E-29 | 16.11.2026 | Solange es keine Profil- und Gruppenbilder gibt, werden Platzhalter verwendet. | Die Stellen sollen im Layout schon vorhanden sein. | Team |

## Technik und Zusammenarbeit

| Nr. | Datum | Entscheidung | Begründung | Von |
|---|---|---|---|---|
| E-30 | 16.11.2026 | Der erste Draft ist ein klickbarer Prototyp aus reinem HTML, CSS und JavaScript, ohne Server, ohne Konten, mit Beispieldaten. | Schnell baubar, läuft per Doppelklick, braucht kein Setup. | Vorschlag |
| E-31 | 16.11.2026 | Die Skripte sind normale `<script>`-Dateien ohne Module und ohne Build-Schritt. | Module laufen nicht, wenn man die Datei direkt im Browser öffnet. | Vorschlag |
| E-32 | 16.11.2026 | Die Arbeit ist in vier Bereiche geteilt. Jede Datei gehört genau einem Bereich. | Vier Leute sollen parallel arbeiten, ohne dieselben Dateien anzufassen. | Team |
| E-33 | 16.11.2026 | Ein Branch pro To-do, Merge per Pull Request, kein direkter Push auf `main`. | Verhindert, dass sich Änderungen gegenseitig überschreiben, und jede Änderung wird einmal angesehen. | Vorschlag |
| E-34 | 16.11.2026 | Das Git-Repo ist die führende Version, nicht der veröffentlichte Prototyp-Link. | Nur das Repo können alle bearbeiten, auch mit Codex. | Vorschlag |

## Offene Entscheidungen

Diese Punkte sind noch nicht entschieden. Sobald sie es sind, wandern sie mit Nummer und Begründung in die Tabellen oben.

| Frage | Betrifft | Bisherige Überlegung |
|---|---|---|
| Ist der Adminbereich nur für Admins sichtbar, oder für alle mit eingeschränkten Rechten? | Bereich 4 | Wandert „Mitglieder“ komplett in den Adminbereich, sehen normale Mitglieder die Liste und den Einladungscode nicht mehr. |
| Was passiert beim Ergebnis-Tipp, wenn niemand das genaue Ergebnis trifft? | Bereich 2 und 3 | Varianten: nur exakt zählt (sonst ungültig), oder wer näher dran ist, gewinnt. |
| Gibt es ein Schuldenlimit je Gruppe? | Bereich 3 | Ohne Startguthaben kann jemand unbegrenzt ins Minus wetten. Vorschlag: einstellbares Limit, z. B. −500 €. |
| Welche Optionen bekommt das Beweis-Dropdown? | Bereich 2 | Genannt wurden Foto-Beweis und Bestätigung durch die Wett-Teilnehmer. Denkbar: Video, Schiedsrichter aus der Gruppe. |
| Woher kommen Events und Ergebnisse für Event-Wetten? | später | Braucht eine Sportdaten-Quelle, die meist Geld kostet. |
| Mit welcher Technik wird die echte App gebaut (Server, Konten, App-Stores)? | später | Der Prototyp hat keinen Server. Die Entscheidung sollte fallen, bevor viel Arbeit in den Prototyp fließt. |
| Braucht es eine rechtliche Prüfung, wenn Gruppen die fiktiven Euro in echtem Geld ausgleichen? | später | Die App bewegt kein Geld, faktisch sind es dann aber Geldwetten unter Freunden. |
