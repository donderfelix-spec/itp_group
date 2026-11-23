# Design “Group Project”

This is how the game should look and play. It was first drafted on 2026-11-18 and has been kept up to date with the game since (last on 2026-11-23). Whatever the team confirms moves into [DECISIONS.md](DECISIONS.md) as a decision. Texts in the game are in English (S-43), so the names of characters, rooms and buttons are written in English here.

Everything without a note is required by Monday. “If time allows” means: only if all required parts work on Saturday (S-33).

## 1. Look

**Style:** Flat and seen from above, with thick dark outlines and strong, sunny colours. Everything is drawn with code (S-28), there are no image files. The look is deliberately our own: characters with a head, a body and one object, with no imitation of the game that inspired this one (S-02).

**Colours**

| Role | Colour | Use |
|---|---|---|
| Outline and text | `#2E2A3B` | all outlines, text |
| Background | `#EADFC8` (sand) | outside the buildings, page background |
| Surface | `#F4EFE3` (cream) | corridors, cards, dialogs |
| Accent | `#FFD23F` (sun yellow) | task stations, main buttons |
| Danger | `#F2695C` (coral) | Free Rider, emergency button, error messages |
| Success | `#5FA86B` (green) | progress bar, “done” |
| Water | `#9CD3E6` | fountain, links |

Every room has its own floor colour, so you know at once where you are: Lecture Hall honey oak, Mon Café terracotta tiles with cream rosettes, Canteen an aqua checkerboard, CTT blue-lilac terrazzo, Pingo Doce cream tiles with olive diamonds (S-148).

**Detail (M2-1.4, S-122; walkways M2-1.19, S-141):** furniture is sized for the characters (a chair about as wide as a body, a table one can sit at), and the rooms keep walkways between the pieces; every room is drawn as densely as the genre's best-known top-down party game, in our own style: each floor has its own pattern (honey-oak planks, terracotta tiles with cream rosettes, an aqua checkerboard, blue-lilac terrazzo, cream tiles with olive diamonds, large paving slabs; S-148), every horizontal wall shows its face, a band 8 units high below it in the room's style (a white wall with a bamboo panel, sage tiles, wooden slats with signs, the taupe slatted façade of the corridor), doors are openings with frames and open glass leaves, and furniture is drawn as what it is, with dark outlines. Floors and fittings stay quieter than stations, rings, players and name labels. Shop names are plain text in the game's lettering, never a copied logo.

**Font:** The system font of the device, with headings in bold. No font has to be downloaded, which saves one dependency.

**Buttons and cards:** Rounded, with a dark outline and a hard shadow to the bottom right, like stickers. The most important button on each screen is yellow, all others are cream.

**Logo:** “GROUP PROJECT” in bold capital letters. One letter is coral red and hangs slightly crooked out of the row: the one who does not pull their weight.

## 2. Map

![Map](design/map.svg)

The map is based on the real campus in Carcavelos: light buildings, a large paved deck in the middle, an outdoor study area, square-trimmed bushes and the beach at the bottom.

- Lecture Hall, Mon Café and Canteen are at the top. On the left, the CTT Student Hall stretches a long way down, and Pingo Doce is at the bottom right. The Main Deck lies between them.
- **Lecture Hall:** a tiered wooden floor with step edges, three deep, slightly curved rows of white desks with black chairs on a riser, facing the front, with a walkway between every two rows and carpeted side aisles, a white front wall with two whiteboards and a clock, a long table with a projector, a lectern on the stage beside the flip chart, a bamboo slatted wall with a dark panel.
- **Mon Café:** the sign "MON Café" (the O a coffee bean) on a white panel framed in wood, a sage-tiled back wall with two menu screens, a black counter on steel with sink, toaster oven, register and pastry case, a chrome espresso machine with cups and two grinders, three columns like in the atrium, two wooden tables with grey-green chairs, a coffee and a slice of cake on each (the door leads straight in to the counter, and no column stands under station 2), a high table with bar stools at the window, a black grid divider with plants, a floor of terracotta tiles with cream rosettes.
- **Canteen:** a steel serving line with a glass guard and seven dishes, a tray rail with trays, cutlery and a register, a menu board and a pass-through to the kitchen, three square tables with trays, an aisle in the middle from the door to the serving line, a microwave corner, recycling bins, a drinks fridge, a tray return with a water fountain below it, and a free aisle along the left wall.
- **CTT Student Hall:** tall and narrow, with a central aisle between eight rows of long white tables on the left and seven short ones on the right, the laptop of station 10 in the place of the eighth (green and a few black chairs, laptops, books, bags), white pillars with "shh" signs and a free aisle along each window, "Please remain silent" on the wall, windows on both long sides with trees outside, a glass double door and the bookshelf at the end.
- **Pingo Doce:** a floor of small cream tiles with olive diamonds and a tiled border, a wooden slat wall with signs (GREENS, PINGO DOCE & GO, READY MEALS) and posters, two turnstile posts with one wide lane behind the door, a green EXIT sign on the floor and two sign totems at the entrance, four full shelves (CANDY, DRINKS, PIZZA, PANTRY) with large, readable goods, fridges along both side walls, the self-checkout with baskets, a round fruit stand, wider than a character, with baskets of fruit and a FRESH FRUITS sign, a hot-food and bakery counter with a coffee corner.
- **Corridor:** the strip of the deck in front of the top rooms is the building's common area: terrazzo floor, the taupe slatted façade, the name "Academic Hall" in dark letters on the floor (S-148), round ceiling lights, grid-cube dividers with plants, two sofas, a black column and a staircase at the left end. A wall with glass doors separates it from the Main Deck: one opening above the study tables and a wide one on the right.
- **Main Deck:** large paving slabs, two light study tables with black chairs on a wooden terrace (where the reflecting pool was, S-148), six bushes trimmed square with small olive leaves and fine shoots, a row of round bushes where the hedge stands, upright along the right wall (S-196), the NOVA sign in dark navy with its O as a ring above a bar on a flat plinth, benches, lamp posts against the walls, a bike rack and a surfboard rack by the exit to the beach; on the sand towels and surfboards big enough for a character. The emergency button, an alarm switch (a red cap with a cream "!" on a yellow plate, on a dark round base), stands centrally on the Main Deck and appears 45 seconds after a round starts. The sixth station is at the bottom, at the exit to the beach: a surfboard standing upright in a small stand, with a block of wax (S-196). You have to walk around all of these, and that is how players lose sight of each other.
- At the bottom, a glass front closes off the deck. You can see the beach and the sea, but you cannot go out.
- Every room has exactly one door to the deck and two task stations (1 to 5 in the corners of the map, so that you really have to walk in Duel, and 7 to 11 at other places); station 12 stands on the Main Deck (S-124). A station is drawn as an object of its room, for example a coffee machine or a book cart (S-128); it is drawn like the furniture around it (thin lines, the room's colours, about the size of a chair or a small table), stands on free floor against a wall or furniture, and neither it nor its outline lies on furniture or a wall. Everything that blocks is drawn to its edges (S-144).
- You only ever see the section around your own character, about one room in size. The camera follows the character.
- In Classic, living players see up to 120 map units from their character (S-185). The view fades softly into the dark towards its edge (S-188). Opaque walls block their view, and open passages let them see through. The server sends only living player positions within that view, subject to the hiding rules. Ghosts keep their wider view.

## 3. Characters

![Characters](design/characters.svg)

The sketch shows the portraits from the front, as used in the lobby list; on the map the characters are drawn in a three-quarter view facing only left or right (S-105).

All characters are the same size and the same speed, they differ only in how they look (S-06). Each one has a body colour, a hairstyle or headwear and an object in the hand, by which you can recognise the character even when it is small. The faces are the same for all of them (S-07). What a character wears on the upper body (tie, vest, straps, lanyard, necklace, print, hoodie strings, collar, buttons) sits in the middle of the torso, also in the three-quarter view and while walking; only the face and the head turn (S-115).

| Character | Colour | How to recognise the character | Line in the lobby |
|---|---|---|---|
| The Consultant | Dark blue suit | red tie, briefcase | “Let’s take this offline.” |
| The Finance Bro | Light blue shirt | quilted vest, phone with a price chart | “What’s the upside?” |
| The Exchange Student | Pink | yellow bucket hat, travel backpack with its straps over the shoulders, lanyard | “Is this graded?” |
| The Surfer | Turquoise | long blond hair, shell necklace, surfboard printed on the shirt | “Waves were good, sorry.” |
| The Founder | Black hoodie | hood up, laptop covered in stickers | “We should pivot.” |
| The Overachiever | Green cardigan | glasses, hair bun, folder with “A+” | “I already started.” |
| The Latecomer | Orange jacket | messy hair, coffee cup | “Did I miss anything?” |
| The Library Local | Purple hoodie | large headphones, stack of books in front of the body | “Shhh.” |

- Each character exists only once per lobby, so that players can be told apart. For this reason there are at most eight players in a lobby. The name is also shown above the character. Name labels never cover each other: where two would overlap, only one is drawn, and the player's own name always wins. Of two other players the name of the character drawn on top is shown; a name that was hidden needs 4 map units of free space to the names that win against it before it comes back, so names do not flicker at the edge. All players start on the one spawn point, so there a player sees only the own name until the others walk away (S-117).
- A moving character runs: between its steps both feet are briefly off the ground and the back foot kicks up, the body hops a little and leans slightly forward, and free hands are held higher and pump against the legs (a hand holding something pumps less). The legs turn around fixed hip points under the body. The steps follow the distance covered, about 5 steps per second. The character looks left or right in the running direction (mirrored); running up or down keeps the side it last faced (S-105, S-118).
- Failed players are half transparent and only visible to other ghosts.
- Where someone was failed, the figure lies on the ground until a player reports it. A crumpled sheet of paper with a red “F” and the portrait of the failed player stays on the ground until the round ends, also after it was reported (S-150, S-163).

## 4. Screens

| No. | Screen | Content |
|---|---|---|
| 1 | Start | Logo, “Log in”, “Sign up”, “Play as guest” |
| 2 | Sign up / Log in | Username, password, error message directly at the field. When signing up, the rules stand below the fields from the start: “3–16 letters or numbers” and “8–64 characters”. A button with an eye in each password field shows or hides what was typed (“Show password” / “Hide password” for screen readers); the password is hidden again whenever the form is left |
| 3 | Home | At the top of the card “Signed in as” and the player's name. “Create lobby” (yellow), “Join with code”, own profile, “Leaderboard”. Profile and leaderboard are two round icons at the top right of the screen (a person and a trophy), not buttons in the card. If time allows: friends list with status |
| 4 | Lobby | Code in large letters for reading aloud, player list with characters, character selection. The panel next to the map has the headings “Lobby code”, “Players”, “Mode” and “Character”. Until the map has been downloaded, “Loading the campus…” stands in the middle of the map. Characters taken by other players are greyed out. Everyone in the lobby already walks on the map, with the lobby shown next to it. The host chooses the mode: “Duel”, “Solo” or “Classic”. Everyone sees the chosen mode. At the bottom right is the yellow button “Start game”, which only the host sees. It is grey as long as too few players are there, and below it there is then a text such as “Classic needs 2 more players”; a host alone in the lobby reads it with the way to play now, “Duel needs 1 more player. Play alone? Choose Solo.” (S-201). All others see “Waiting for the host” in that place. When the host presses “Start game”, the round does not begin at once: everybody sees “Round starts in” and a large number over the map that counts 5, 4, 3, 2, 1, and then the round starts. During this countdown everybody can still walk, but the characters, the mode and the start button are switched off, and nobody can join. A ranking that is still open stays readable; the countdown is then one slim line at the top edge of the map (“Round starts in 3”), above the ranking, and never covers it. If so many players leave during the countdown that too few are left for the mode, the countdown ends without a round and the lobby is open again. While a round is running, the panel shows “Round running” instead of the character selection and the start button. In “Mode”, Duel and Solo stand side by side and Classic below them over the whole width. For the host, a mode that does not fit the number of players is greyed out with a “?” that shows why: Solo with two or more players, Duel when alone, Classic with fewer than four (S-146). Every locked mode has the same grey; when the chosen mode does not fit, it keeps only its dark frame and shadow as the mark of the choice (S-146). When a second player joins a lobby set to Solo, it switches to Duel (S-125). |
| 5 | Role reveal | Three seconds: under “Your role” the role, “High Performer” or “Free Rider” in coral, and one line on what to do (“Complete your 4 tasks.” / “Make High Performers fail without getting caught.”). With two Free Riders each also reads “Other Free Riders:” and the other one’s name; with one Free Rider that line is left out |
| 6 | Game | Map with displays, see below |
| 7 | Minigame | Window on top of the map, closes with Esc |
| 8 | Meeting | Cards of all players, chat, vote, clock, and a small “Leave lobby”, because the meeting covers the panel (S-201) |
| 9 | Vote result | Who received how many votes, the character drifts out to sea (not built yet, M3-3.5: today the result is text only), and whether it was a Free Rider |
| 10 | End | Who won, who was a Free Rider, the statistics, “Back to the lobby”. Only the host also sees “New Round”, with “Start another round with the same lobby.” below the buttons; everybody else sees no “New Round” at all, only “Back to the lobby” and below it “The host can start the next round.” When the host changes while the screen is open, the button follows (Felix, 2026-11-22). |
| 11 | Duel ranking | Placement with times |
| 12 | Profile | Rounds and wins per mode, best Duel time. Opened with “Profile” on the Home screen, only for an account: “Signed in as” and the name at the top, then one row per mode with “Rounds” and “Wins”, below it “Best Duel time” written like in the Duel ranking (“1:12.4”), or “–” as long as there is none, and “Back”. A guest gets the message “Guests have no statistics. Sign up to keep yours.” instead |
| 13 | Leaderboard | All accounts by wins. Opened with “Leaderboard” on the Home screen, also for a guest: the best 20 accounts with “Place”, “Player”, “Wins” and “Best Duel time”, ordered by wins, then by the better Duel time, then by name; the own row is yellow. Before the first round it says “No rounds played yet.”. “Back” leads to the Home screen. If time allows: filter “Friends” |

**Displays in the game**

- Top left: a card with the name of the room you are standing in and your next task (S-129, S-197).
- In the side panel: the progress bar of the group work (“Group progress”, Classic).
- Side panel during a round, the same order in every mode (S-143): first the panel of the mode (Duel and Solo: the heading “Duel” or “Solo”, the next task and the clock; Classic: the heading “Classic”, the own name, then “Group progress” with the bar), then “Players”, then the rest. Outside a round the panel starts with “Players”. In Classic the panel has no task card: the own active task stands in the card at the top left of the map, as in Duel and Solo. In its place that card says “All your tasks are done.” (green) once all four are done, and to the Free Rider “Fake tasks: stand at a station to look busy.” (S-197). A ghost keeps its active task, because ghosts keep doing their tasks.
- Below the progress bar, only for the own Free Rider while he hides in Classic: “Hidden” (S-135).
- Bottom right: large buttons, each with its key first (S-195). A High Performer always has “E Use” (“E Emergency” at the red button). A Free Rider always has “F Let fail” and, above it only while E would do something, a second button “E Emergency”, “E Hide” or “E Leave hiding”. “R Report” appears above the main button for both roles while a report is possible. Each button has a fixed place, so nothing moves when another appears. A button is grey as long as it would do nothing.
- Messages appear briefly at the top centre, errors in coral. On the lobby screen they stand over the map, not over the panel; in a narrow window, where the panel is below the map and the page scrolls, they appear at the bottom centre instead, so they never cover the lobby code (S-113).

**How you notice that a key does something**

The same rule applies to E, R and F. As soon as you stand close enough to a target (25 map units for a station, the red button, a hiding spot or a victim, 8 for an F-sheet; a character is about 10 wide), two things happen at the same time:

1. The target gets a glowing border that pulses slowly (a station: its yellow outline at full strength, S-128).
2. The matching button at the bottom right changes from grey to colour. The button shows the key and the word that goes with it, for example “E Use”.

If you walk away, both disappear again; a station that matters to you keeps its slowly pulsing outline (S-128). If two targets are in range, the closer one counts. There is no speech bubble above the target.

| Key | Target | Border | Button at the bottom right | Special note |
|---|---|---|---|---|
| E | Task station that you need now (in Classic only your one active task, S-197) | Yellow | “E Use” | Stations that you do not need or have already finished do not glow |
| E | Emergency button | Yellow | “E Emergency” | Only as long as you have not yet used up your meeting. For the Free Rider it is his second button, also during the fail cooldown (S-195) |
| E | Hiding spot within 25 map units (S-191) | – | “E Hide”, while hidden “E Leave hiding” (the Free Rider's second button, S-195) | Only the living Free Rider in a Classic round sees it. When a station or the emergency button is in reach as well, E uses the nearest of them |
| R | “F” sheet | Coral | “R Report” | Visible to everyone who is in range |
| F | High Performer in range (25 map units, S-194) | Coral | “F Let fail” | Only the Free Rider sees the border around the High Performer and the button, which is always there (S-195). During the 15-second cooldown it is grey and a darker grey fills it from left to right, with no seconds; charged with nobody in range it is all grey and off; charged with a victim in range it is yellow like an active “E Use”. Q does nothing (S-195) |

Pressing a key that would do nothing at that moment has no effect and also shows no error message.

**Controls**

| Key | Action |
|---|---|
| WASD or arrow keys | Walk |
| E | Use a station, press the emergency button; as the Free Rider in Classic also hide and leave hiding |
| R | Report a failed player |
| F | Fail someone (Free Rider only) |
| M | Open or close the campus overview |
| Enter | Send chat in the meeting |
| Esc | Close the minigame or the map |
| 1, 2, 3 | Catch a page in lane 1, 2 or 3 in “Seagull quality control” (station 12) |

Every action also works with a mouse click on the button. The campus overview shows the whole floor plan, your position and only the station you need now: in Classic your one active task (S-197), in Duel or Solo your next task.

**Walking diagnostic.** Opened with `?debug` at the end of the address, the page shows a small panel in the top left corner with numbers about the connection and the drawing while walking (S-120), and the buttons “Copy”, “Reset” and “Hide”. It is a tool for the team, not part of the game: without `?debug` it does not exist.

**Walking through hold-ups.** When the connection holds the server's positions up while the player walks, the own character walks on by itself for at most about 700 ms with the same movement and wall rule as the server, and the server's positions take over when they arrive (S-121). The server still decides: the character always ends where the server says, and a station can be used when the server's position is in range. `?bridge=off` at the end of the address switches this off, to compare.

## 5. Classic mode

4 to 8 players. With fewer than 4, the round cannot be started.

1. Everyone starts on the Main Deck. Each player sees their role for three seconds. Two Free Riders also see who the other one is.
2. Each High Performer gets four of the eleven tasks (stations 1 to 5 and 7 to 12, S-124), chosen in a random order by the server. Exactly one is active at a time. Finishing it reveals the next randomly ordered task until all four are done. Every finished task fills the shared progress bar, which still counts four tasks per High Performer (S-197).
3. Every player sees only their own current task; only that station pulses and can be opened, any other station is refused with “You do not need that station.” (S-197). The Free Rider has no task list and cannot open a station: they fake tasks by standing at one, and no station pulses for them (S-154).
4. The Free Rider can fail a High Performer who is in range (25 map units, S-194), with key F or the button “F Let fail” (S-195). After that, the Free Rider has to wait 15 seconds. The Free Rider starts with the ability loaded and cannot fail another Free Rider.
5. Reporting happens right on the spot: For any living player, the Free Rider included, who stands within 8 map units of an “F” sheet (S-180), the button “R Report” appears (key R, S-195). Pressing it starts the meeting for everyone at once, and nobody has to walk anywhere. The reported sheet stays on the map until the round ends and cannot be reported again (S-150). Without a find, each living player can call one meeting per round with the red button in the centre of the Main Deck, available 45 seconds after the round starts. The player has to stand within 25 map units of the button, as close as to a station; the server checks this, and only a living player within that range sees “E Emergency”. There is no other cooldown (S-170, S-172).
6. Meeting: 45 seconds of discussion by chat, then 30 seconds for the vote. You vote for one person or “Skip”. The person with the most votes goes, and nobody goes if there is a tie or a majority for “Skip”. After a report, voting is already open during the discussion; after an emergency meeting only in the voting phase (S-161). During the vote the window says “Chat is closed. Choose one living player to eject, or Skip.” Votes are public: each vote button shows on its right, in a round field of fixed size, how many voted for that player (a pale “0” without votes), and its label names the voters, for example “Bo — votes: Ana, Cy” or “Bo — no votes”; the own target is highlighted. All vote buttons have the same size in a fixed grid (four columns, three in a medium window, two in a narrow one); a long name ends in “…”, and nothing moves when votes arrive, change or are taken back. The meeting window always fits the screen: the meeting picture shrinks, and the Skip row, the vote buttons, the message field and “Send” stay visible (Felix, 2026-11-22). Clicking the same player again takes the vote back, another player replaces it (S-160). “Skip” switches the own Skip on and off (“Skip” / “Undo Skip”) and takes back the own vote; the window shows “2 / 3 Skip votes to end voting early.” As soon as 75 % of the living have chosen Skip, rounded up, the meeting ends at once. Anyone who does not vote does not count as “Skip”; Skip with as many votes as the leading player is a tie. Otherwise the vote ends when its 30 seconds run out, also when everybody has voted (S-162). The result stays on screen for a moment (1.8 s), then the window closes and the round goes on; when the result ends the round, the end screen follows at once (S-153).
7. Whoever is voted out drifts out to sea: The character is caught by a wave on the beach, gets smaller and disappears on the horizon (not built yet, M3-3.5). A text says whether it was a Free Rider: “Mara was a Free Rider.” or “Mara was not a Free Rider.”
8. After the meeting everyone stands on the Main Deck again, and the Free Rider’s cooldown starts again.
9. Ghosts keep doing their tasks, but they do not write in the chat and do not vote.

| Value | Setting |
|---|---|
| Players | at least 4, at most 8 |
| Free Riders | 1 with 4 or 5 players, 2 with 6 to 8 |
| Tasks per High Performer | 4 |
| Cooldown “Fail” | 15 s |
| Discussion / vote | 45 s / 30 s |
| Emergency meetings | 1 per player |

Lennart's update (2026-11-22, S-180, S-181, S-194): the Free Rider fail radius is 25 map units (20 until S-194) and the F-sheet report radius is 8. A living Free Rider can report any unreported F-sheet, including their own victim's. The cooldown remains 15 seconds. F-sheets and their victim portraits are drawn 30 % larger.

**High Performers win:** The progress bar is full, or all Free Riders have been voted out.
**Free Riders win:** There are as many Free Riders left as High Performers.

If someone leaves the round, that player counts as failed, and their open tasks disappear from the progress bar.

In all modes, players walk through each other, and nobody can block a door.

**Hiding spots:** There are seven places, each shown on the map as an object that belongs there, standing in a soft shade as large as the spot (S-190, S-196): cardboard boxes below the pizza shelf of Pingo Doce, towards the fruit stand, a beanbag with two books next to the bookshelf of the CTT Student Hall, a potted plant in the bottom right corner of the Canteen, a dark hollow in the hedge along the right wall of the Main Deck, coffee sacks beside a column of Mon Café, two stacks of folding chairs in the bottom left corner of the Lecture Hall, and stacked sun loungers with a folded parasol on the Main Deck by the wall of the CTT Student Hall. The objects are only drawn; everybody walks through them and sees them the same way. Everybody can walk into the hedge. Only the Free Rider hides, and only in Classic. He hides on purpose (S-191): a living Free Rider who stands within 25 map units of a hiding spot presses E (“E Hide”); he is put into the middle of the spot, stands still and is then not sent to any living High Performer, however near (S-192): whoever watches him hide sees him disappear at the object. Standing in a spot alone does not hide. A step, E again (“E Leave hiding”), a meeting, and leaving the lobby end hiding; after a meeting he presses E again to hide. While hidden he cannot fail, report or call a meeting: he steps out first, which is instant. A High Performer or a ghost cannot hide, and in the lobby and in Duel nobody hides. The hidden Free Rider sees his own character half transparent (0.5) with a small crossed-out eye above his name, and the word “Hidden” in the Classic panel, so that he notices that he is hidden (S-131 to S-135, S-192). Ghosts (S-136) and the other Free Rider (S-137, within his own view) still get him, and see him the same way: half transparent with the crossed-out eye. Ghosts themselves are drawn half transparent without the eye, so the eye alone tells a hidden player from a ghost. A living High Performer sees nothing of any of it.

If time allows: Sabotage “WiFi down”. The Free Rider locks all stations until someone restarts the router in the CTT Student Hall.

## 6. Duel mode

2 to 8 players. **Solo** plays the same rules for one player who is alone in the lobby, and counts for no statistics (S-125). In Solo the panel and the ranking say “Solo” instead of “Duel”.

1. For each player, the server draws their own three of the eleven stations in their own order, and every player starts at a different station (S-126). Nobody knows in advance where they have to go, and nobody knows the routes of the others.
2. Everyone starts on the Main Deck. Each player sees only their next station. The one after that appears only when the previous one is done.
3. To keep it fair, the server only draws routes whose walking distance is about the same length.
4. In the Players list of the panel, only the progress is shown for each player: 0/3, 1/3, 2/3, 3/3, with a green bar (S-130). You only see where the others are at the moment if you meet them.
5. Players do not block each other, they walk through each other.
6. Whoever finishes all three first wins. The round continues until everyone is finished or 3 minutes are over, and then the leaderboard with times is shown.

The win and the time go into the statistics (S-40).

**What a player sees in Duel**

- At the top of the panel on the right, above “Players” (S-143): “Next: Build the tray (Canteen)” with the title of the minigame and the room, below it the clock counting down from 3:00. The progress of all players stands in the Players list below, for example “Mara 1/3”. A player who has finished all three sees “Finished in 1:12.4. Waiting for the others.” instead of the next station.
- Every station is drawn as its object; only the next station has the pulsing yellow outline and opens (S-128).
- The card at the top left of the map shows the room you are in and the next task; a small yellow triangle with a dark outline next to your character points straight at the station (S-129). In Classic it points at the player's one active task, and the card names it like in Duel and Solo; the Free Rider has no task, so no arrow, and the card shows his hint “Fake tasks: stand at a station to look busy.”; after the fourth task it says “All your tasks are done.” (S-197).
- When the round is over, the ranking appears over the map for everybody: heading “Duel ranking”, one row per player with place, name and time (“1:12.4”), or “2/3” for a player who did not finish, and the button “Back to lobby”. If the three minutes ran out, the line “Time is up.” stands above the rows. The lobby is open again at that moment, so the host can start the next round.
- A player who leaves during the round is taken out of the list and the ranking. The round goes on for the others, also for a single player.

## 7. Deadline mode (if time allows)

2 to 8 players. Everyone plays together, there is no Free Rider. The group has 5 minutes to finish three tasks per player. Every 45 seconds a random disruption comes. If the progress bar is full before the time runs out, everyone wins.

| Disruption | What happens | How to fix it |
|---|---|---|
| WiFi down | All stations are locked | Someone restarts the router in the CTT Student Hall |
| Power cut | The visible section shrinks to a small circle | Someone flips the fuse switch in the Lecture Hall |
| Fire drill | All minigames close | Everyone has to meet on the Main Deck within 20 seconds |
| Seagull | A seagull steals a tray, the station in the Canteen is locked | Someone runs after the seagull on the Main Deck and touches it |
| Queue at the canteen | The station in the Canteen is locked for 30 seconds | Wait, or do other tasks first |
| Deadline moved | The clock loses 20 seconds | Nothing, the group has to get faster |

## 8. Minigames

Every room has its fixed minigame, it does not change. But the content is shuffled anew every round. All minigames take 10 to 25 seconds, are played with the mouse (station 12 also with the keys 1, 2 and 3) and have the same header: title, one sentence of instructions, close button.

After a mistake, only the wrong piece is reset, never the whole minigame.

A minigame opens with E or the button “E Use” at its station, only while a round is running. While it is open the character stands still. The close button and Esc close it without counting; it can be opened again and then has new content. When it is solved, the window shows “Done” in green for 0.5 seconds and closes automatically; the close button is hidden meanwhile (S-127). A station whose minigame is not built yet shows “This task is still being built.” and a button “Finish task”.

| No. | Room | Title | Task | Done when | After a mistake |
|---|---|---|---|---|---|
| 1 | Lecture Hall | Sort the slides | Put five shuffled slides (Title, Agenda, Analysis, Results, Q&A) into the right order by dragging | all five are in the right place | the slide in the wrong place shakes and jumps back |
| 2 | Mon Café | Brew the order | An order slip names a drink with its recipe, for example Galão: Glass, Espresso, Milk. Press the buttons on the coffee machine in this order. There are six buttons: Cup, Glass, Espresso, Hot water, Milk, Foam | the drink matches the recipe | the wrong button flashes red, the steps so far stay |
| 3 | Canteen | Build the tray | There are six dishes at the counter. The order slip names four of them. Click these four onto the tray, the order does not matter | the four from the order slip are on the tray | the wrong dish goes back to the counter |
| 4 | CTT Student Hall | Shelve the books | Click six numbered books onto the shelf in ascending order | all six are on the shelf | the wrong book falls back onto the stack |
| 5 | Pingo Doce | Self-checkout | The checkout shows a target amount, for example €7.50. Six products with prices are on the belt. Scan as many as needed to get exactly that amount. A click on a scanned product puts it back | the total is exactly right | a product that takes the total above the amount is not accepted: “Unexpected item in the bagging area” |
| 6 | Glass front to the beach on the Main Deck | Catch the wave (if time allows) | A surfboard lies on the water, a wave runs through the picture from left to right. Click exactly when the wave is under the board | three waves have been caught | a wrong click only costs this attempt, the hits stay |

Minigame 6 is the only one with timing instead of sorting, selecting or calculating. It comes first of the “If time allows” minigames. As soon as it is built, station 6 joins the stations of Duel, Solo and Classic.

**Sentences and names in the minigames**

- **Build the tray:** “Put the four dishes from the order slip on the tray.” The six dishes are Soup, Bacalhau, Rice, Salad, Pastel de nata and Fruit. The areas are labelled “Order slip”, “Counter” and “Tray”.
- **Brew the order:** “Press the buttons in the order of the recipe.” The slip is headed “Order”. A second press of the button that was just accepted is ignored, so a double click is not shown as a mistake.
- **Sort the slides:** “Drag the slides into the right order.” Five numbered places stand above the pile. A slide dropped on its right place stays there; on a wrong or filled place it shakes and jumps back; released outside the window it returns without counting.
- **Shelve the books:** “Click the books onto the shelf, lowest number first.” The numbers are six different numbers from 100 to 999.
- **Self-checkout:** “Scan products until the total is exactly the target amount.” The six products are Water, Bread, Cheese, Apples, Coffee and Chocolate, with prices from €0.50 to €4.00. The display shows “Target” and “Total”, the rows are labelled “Belt” and “Bagging area”. The target is never the price of a single product, so there are always at least two clicks.

About the drinks in minigame 2: Bica (Cup, Espresso), Abatanado (Cup, Espresso, Hot water), Meia de leite (Cup, Espresso, Milk), Galão (Glass, Espresso, Milk), Cappuccino (Cup, Espresso, Milk, Foam).

About minigame 5: The prices are multiples of 50 cents, and the target amount is always the total of three of the six products. So there is always a solution, and every combination that hits the amount counts.

**Minigames 7 to 12 (S-124)**

| No. | Room | Title | Instruction |
|---|---|---|---|
| 7 | Lecture Hall | Fix the consultant’s chart | Rebuild the misleading chart from survey counts. Repair its labels, percentages and baseline. |
| 8 | Mon Café | Emergency caffeine protocol | Follow the recipe. The group deadline runs on caffeine. |
| 9 | Canteen | Save the lunch | Remove the discoloured pieces from the tray. |
| 10 | CTT Student Hall | Decode the group chat | Use five chat clues to assign four teammates to four times and four deliverables. |
| 11 | Pingo Doce | Expense the essentials | Scan emergency supplies until the total matches the budget. |
| 12 | Main Deck | Seagull quality control | Rescue six falling pages in three lanes. Catch them in the yellow zone and ignore coffee decoys. |

Stations 7, 10 and 12 each show their own brief inside the task window. Chart and chat edits remain editable after a rejected check. The rescue has twelve increasingly quick flights, eight pages and four coffee decoys. Three mistakes end the attempt and offer a retry. Lane buttons and keys 1, 2 and 3 catch a page in the second half of its flight. Closing a task cancels its timers and input listeners. The old campus-task puzzles of these stations (buzzword slides, word order, clicking the seagull) are gone from the client (S-208); a packet of those kinds is refused as broken. “Save the lunch” is one tray seen from above with 10 rice grains, 3 vegetable and 3 chicken pieces; 3, 1 and 1 of them are discoloured, without labels, and are clicked away. “Expense the essentials” has six products from €1.50 to €4.00; the budget is the total of three of them.

After that, if time allows: “Stop the microwave” (Canteen), “Scan the attendance code” (Lecture Hall), “Fix the formula” (CTT Student Hall).

## 9. Messages and errors

Grading criteria 1 and 2 require that invalid input does not break anything and that errors are shown clearly. For this reason every rejected action has a fixed text:

| Situation | Message |
|---|---|
| Username taken | “That username is taken.” |
| Username or password too short or with characters that are not allowed | “Usernames are 3–16 letters or numbers.” / “Passwords need at least 8 characters.” |
| Wrong password | “Wrong username or password.” |
| Lobby code does not exist | “No lobby with that code.” |
| After 5 wrong log-ins or 10 wrong lobby codes within a minute on one connection | “Too many attempts. Try again in a minute.” |
| Lobby is full, or its countdown or round is already running | “This lobby is full.” / “This round has already started.” |
| Too few players for the mode | “Classic needs at least 4 players.” |
| Calling an emergency meeting further than 25 map units from the red button (only when someone bypasses the page) | “Walk to the red button to call a meeting.” |
| Hiding as a High Performer or a ghost, in a meeting, outside a Classic round (only when someone bypasses the page) | “You cannot hide right now.” |
| Hiding further than 25 map units from every hiding spot (only when someone bypasses the page) | “Walk up to a hiding spot to hide.” |
| Failing, reporting or calling a meeting while hidden | “Leave your hiding spot first.” |
| Opening a station while a meeting runs (only when someone bypasses the page; S-199) | “Tasks wait until the meeting is over.” |
| Skipping when there is no meeting, as a ghost, after the time, or in the discussion of an emergency meeting (only when someone bypasses the page) | “You cannot skip this discussion right now.” |
| Connection lost | “Connection lost. Reconnecting…” After the player signs in again, the page joins the lobby it was in by itself and puts the code into the join field. If that lobby is gone, full or in its countdown or round, the usual text appears at the code field (S-109). |
| Database not reachable | “Accounts are unavailable right now. You can still play as a guest.” |
| Host has left the lobby | “The host left. Mara is the new host.” |
| A Classic round no longer has enough players for its Free Riders because players left | “Too many players left. The round was stopped.” |
| The same account logged in somewhere else, so this browser was signed out | “You were signed in somewhere else.” (shown by the browser on the Start screen) |
| Password too long | “Passwords can have at most 64 characters.” |
| Password with a character that cannot be stored | “Passwords cannot contain that character.” |
| Lobby code is not four letters | “Lobby codes are 4 letters.” |
| Character already taken by another player | “That character is taken.” |
| Action that needs a signed-in player or a guest | “Log in or play as a guest first.” |
| Signing up, logging in or entering as a guest while signed in | “Log out first.” |
| Action that needs a lobby | “You are not in a lobby.” |
| Creating or joining a lobby while in one | “Leave your lobby first.” |
| Choosing the mode or starting the round without being the host | “Only the host can do that.” |
| Choosing a mode that does not exist or is not built yet (only when someone bypasses the page) | “That mode does not exist.” |
| Starting Duel with fewer than 2 players | “Duel needs at least 2 players.” |
| Choosing or starting Solo with two or more players | “Solo is only for one player alone.” |
| Choosing the mode, choosing a character or starting the round during the countdown or while a round is running | “This round has already started.” |
| Opening, closing or finishing a task while no round is running | “No round is running.” |
| Opening a station that does not exist or is not in use (only when someone bypasses the page) | “That station does not exist.” |
| Opening a station from too far away | “You are too far away.” |
| Opening a station that is not on your list, that you have already finished or, in Classic, that is not your active task yet (S-197) | “You do not need that station.” |
| Opening a station while a task is open | “Close your current task first.” |
| Closing or finishing while no task is open | “You have no task open.” |
| Reporting a task as done faster than it can be played | “That was too fast. Try again.” |
| The server fails while opening, closing or finishing a task | “Something went wrong. Try again.” |
| A guest asks for a profile | “Guests have no statistics. Sign up to keep yours.” |
| Profile or leaderboard while the database is not reachable | “Statistics are unavailable right now.” |
| A minigame gets content from the server that it cannot show | “This task could not be loaded.” (shown inside the minigame window) |
| A message that is not text, is not a JSON object or is longer than 2048 bytes (only when someone bypasses the page) | “Messages must be text.” / “That message could not be read.” / “That message is too long.” |
| A message with a type the server does not know (only when someone bypasses the page) | “The server does not know that action.” |
| A message with a field the server does not expect, or without a field it needs (only when someone bypasses the page) | “That message has a field the server does not expect.” / “That message is incomplete.” |
| Choosing a character that does not exist (only when someone bypasses the page) | “That character does not exist.” |
| A walking direction that is not -1, 0 or 1 (only when someone bypasses the page) | “That move could not be read.” |
| A Free Rider opens, closes or finishes a station (only when someone bypasses the page) | “Free Riders cannot complete tasks.” |
| Failing while it is not possible: no Classic round, no High Performer in range, as a High Performer or a ghost | “You cannot fail a player right now.” |
| Failing during the 15-second cooldown | “You can fail again in 12 seconds.” (the seconds left, “1 second” for one) |
| Chatting outside the discussion of a meeting, as a ghost, or too fast after the last message | “You cannot send that chat message right now.” |
| A chat message that is empty, longer than 200 characters or has characters that are not allowed | “Chat messages must contain 1–200 characters.” |
| Voting while voting is closed, as a ghost, or for a player who is not a living player of the round | “You cannot cast that vote right now.” |
| Reporting an F-sheet from too far away, as a ghost, or one that was already reported | “You cannot report that F-sheet right now. Stand at the sheet and try again.” |
| Calling an emergency meeting as a ghost, a second time or outside a Classic round | “You cannot call an emergency meeting right now.” |
| Calling an emergency meeting in the first 45 seconds of a round | “The emergency button unlocks in 20 seconds.” (the seconds left, “1 second” for one) |
| A report with an F-sheet id that is not text of the right form (only when someone bypasses the page) | “That F-sheet could not be identified.” |
| A report with a position that is not two finite numbers (only when someone bypasses the page) | “That position could not be read.” |

## 10. What is deliberately not included

- No voice chat (S-10) and no chat outside of meetings.
- No characters with abilities, no skins to unlock.
- No sound, unless time allows.
- No phone controls, unless time allows (S-14).
- No email addresses and no “forgot password” (S-38).
- No return into a running round after a lost connection: the player signs in again and waits on Home until the round is over (S-109).
