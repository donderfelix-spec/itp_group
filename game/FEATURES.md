# Feature overview for “Group Project”

All features of the game with their status. Whoever finishes a feature or plans a new one updates the row here.

**Status values**

- **Done:** built, played through by the tester, on `main`.
- **In progress:** a branch for it is open.
- **Planned:** listed as a to-do in [TODO.md](TODO.md).
- **Later:** wanted, but no to-do yet.
- **Playable with known defects:** on `main` and playable, with open defects listed as to-dos in [TODO.md](TODO.md).

**Milestones**

- **M1 Walking:** Several players meet in a lobby and walk across the campus together.
- **M2 Duel:** Minigames and the Duel mode are playable.
- **M3 Classic:** A complete Classic round with Free Rider, meeting and vote is playable. Status 2026-11-23: playable through every ending; the open points are in [TODO.md](TODO.md).
- **M4 Extensions:** Sabotage, Deadline mode, finished characters, sound, phone.

As of 2026-11-23. Milestones 1 to 3 are on `main` and deployed; of milestone 4 only some points are built.

## Area 1: Campus and characters

| Feature | Milestone | Status |
|---|---|---|
| Map with Lecture Hall, Mon Café, Canteen, CTT Student Hall and Pingo Doce, connected by the Main Deck | M1 | Done |
| Move the character with the keyboard (WASD or arrow keys) | M1 | Done |
| Walls and furniture stop the character | M1 | Done |
| Camera follows your own character | M1 | Done |
| See other players with their names above the character; where name labels would cover each other only one is shown, the own name first (S-117) | M1 | Done |
| Stations for tasks on the map | M2 | Done |
| Key hint in range: pulsing border around the target, coloured button with the key at the bottom right (E, R and F; S-195) | M2 | Done |
| Choose a character from the list of stereotypes | M2 | Done |
| Display of the current room, in the card at the top left (S-129) | M2 | Done |
| Nicer, more detailed map: every room furnished from photos of the campus, floor patterns, wall faces, doors, drawn from tiles (S-122); walkways between fewer pieces, Hanna's Pingo Doce and round bushes (S-141); stations standing free, aisles without dead ends, everything that blocks drawn to its edges (S-144); Hanna's room floors, leafy square bushes and study tables in place of the pool, “Academic Hall” on the corridor floor (S-148) | M2 | Done |
| Larger characters in a three-quarter view, facing only left or right; held objects stay in the same hand | M2 | Done |
| A small personal motif on every outfit and a softer face (M2-1.18, S-142) | M2 | Done |
| Walking animation: moving feet, head turned in the walking direction | M2 | Done |
| Running animation: flight phase, small hop, pumping arms, legs fixed at the hips, steps tied to the distance covered | M2 | Done |
| Hair, buns and headwear follow the head when it turns in the walking direction | M2 | Done |
| Touch-ups of the characters: no suitcase, larger hat, headphones on the ear, clothes in the middle of the torso when turned | M2 | Done |
| Smooth walking over the internet: characters and the camera keep moving when position messages come late or bunched (gaps up to 250 ms) | M2 | Done |
| The own character and the camera keep walking through longer hold-ups of the connection (up to about 700 ms) and stop sooner after a key is released | M2 | Done |
| Walking diagnostic for the team: with `?debug` in the address a panel measures the connection and the drawing while walking and copies the numbers as text | M2 | Done |
| Limited view in Classic: nearby living players in direct sight, with walls casting shadows (S-185) | M3 | Done |
| The place of an F-sheet only to who sees it, the ghosts and the Free Rider who did it; the others get it when it comes into their sight (S-202) | M3 | Done (M3-3.25) |
| Half-transparent ghosts visible to other ghosts and fallen characters visible until reported (S-186) | M3 | Done |
| Seven hiding spots in Classic (S-131 to S-140), drawn as objects of the map: boxes, a beanbag, a potted plant, a hollow in the hedge (S-190), coffee sacks, folding chairs and sun loungers (S-196); the Free Rider hides on purpose with E and is then sent to no High Performer; himself, the other Free Rider and ghosts see him with a crossed-out eye (S-191, S-192) | M3 | Done |
| Campus overview with your location and the station you need now, in Classic the one active task (S-187, S-197) | M3 | Done |
| Finished graphics for rooms and characters instead of placeholders | M4 | Planned |
| Sounds and music | M4 | Later |
| Touch controls for the phone | M4 | Later |

## Area 2: Network, lobby and foundation

| Feature | Milestone | Status |
|---|---|---|
| Start a server that delivers the client and the game | M0 | Done |
| Create an account with username and password, log in, log out | M1 | Done |
| Play as a guest, without statistics and friends | M1 | Done |
| Clear message when a name is taken, the password is wrong or the database is not reachable | M1 | Done |
| Show or hide the password with an eye icon | M1 | Done |
| A player who is signed out because the account logged in somewhere else is told why | M1 | Done |
| Limit on log-in attempts and lobby-code guessing | M1 | Done |
| Statistics per account: rounds and wins per mode (Duel, and Classic since S-198), best Duel time | M2 | Done |
| Leaderboard of all accounts | M2 | Done |
| Add friends by username, accept or decline a request | M4 | Planned |
| See friends with the status “online” and “in a round” | M4 | Planned |
| Invite friends to your own lobby | M4 | Planned |
| Leaderboard among friends | M4 | Planned |
| Create a lobby, get a code with four letters | M1 | Done |
| Join a lobby by code | M1 | Done |
| Player list in the lobby, the creator is the host | M1 | Done |
| Continuously synchronise the positions of all players, with smoothed movement of the others | M1 | Done |
| Host chooses the mode and starts the round (settings: M4) | M2 | Done |
| Countdown of 5 seconds before every round, counted by the server | M2 | Done |
| After the round back to the lobby, new round without a new code | M2 | Done |
| If someone leaves the game, the round continues, and the host changes if needed | M2 | Done |
| A player who lost the connection in a lobby is put back into it after signing in again, without typing the code (S-109) | M3 | Done |
| Players who were disconnected for a short time come back into their running round | M4 | Later |
| Each client gets only the information that its player is allowed to know | M3 | Done (M3-2.1, 2026-11-22; known limit S-168) |
| Game reachable at a public URL, deployed automatically from `main` | M0 | Done |
| Several lobbies at the same time | M1 | Done |

## Area 3: Classic rules

| Feature | Milestone | Status |
|---|---|---|
| Assign roles at random at the start, the role is shown to each player individually | M3 | Done |
| Each High Performer gets their own four tasks, sent only to them (since S-197 one active task at a time, see below) | M3 | Done |
| Shared progress bar of the group work | M3 | Done |
| Free Rider fails a nearby player, followed by a cooldown that starts again after every meeting; the victim's open task closes; the sheet shows the victim's portrait (S-163, S-199) | M3 | Done |
| Find and report a failed player | M3 | Done |
| Report from 8 map units, also by the Free Rider; let fail from 25 map units with F (S-194, S-195); F-sheets 30 % larger (S-180, S-181) | M3 | Done (M3-4.25 to M3-4.28) |
| Classic action buttons with the key first: the Free Rider always has “F Let fail” (grey charge fill, yellow when a victim is in range; only F lets fail) and his own second button for “E Emergency”, “E Hide”, “E Leave hiding”; “R Report” for everybody (S-195) | M3 | Done (M3-3.26) |
| Emergency meeting with the red button in the centre of the Main Deck (S-147), drawn as an alarm switch (S-149), limited per player, range checked by the server, hint only for the living (S-170), button “E Emergency” (S-195) | M3 | Done |
| Meeting with text chat and time limit; the window closes after the result (S-153) and always fits the screen (S-173) and shows as many chat messages as fit (S-210); nobody walks and no task stays open during it, and afterwards players resume from their previous positions (S-199, S-213); its own “Leave lobby” (S-201) | M3 | Done |
| One random active Classic task per High Performer, next revealed after completion; only the current station pulses and opens, and the arrow leads to it; the Free Rider has none (S-197, replaces the own task list of S-154) | M3 | Done (M3-4.29) |
| Vote: choose a person or skip, the majority choice is voted out, nobody in case of a tie; votes are public and can be changed, after a report or emergency call already during the discussion (S-212), 75 % Skip ends the meeting (S-160 to S-162); each vote button shows its number of votes in a fixed field (S-173) | M3 | Done |
| Result of the vote: character drifts out to sea, display whether it was a Free Rider | M3 | Playable with known defects (text only, no drifting yet, M3-3.5) |
| Ghosts keep doing their tasks, but they do not talk and do not vote; ghosts see the dead as “Dead” in the Players list (S-164) | M3 | Done (M3-3.9, M3-3.20, 2026-11-22) |
| Check the win conditions and show the end screen that reveals the roles; only the host sees “New Round” (S-173) | M3 | Done (M3-3.11, 2026-11-22) |
| A player who leaves a Classic round counts as failed; the round stops when too few players are left for its Free Riders (S-157, S-158); a leaver's Skip goes too, and 75 % Skip of those left ends the meeting (S-165) | M3 | Done (M3-3.8, M3-3.11, 2026-11-22) |
| Free Riders can only fake tasks: they have none and cannot open a station (S-154, S-197) | M3 | Done |
| Sabotage “WiFi down”: tasks locked until someone restarts the router | M4 | Planned |
| Sabotage “Fire alarm”: Two players have to stand at two places in time, otherwise the Free Riders win | M4 | Planned |
| Sabotage “Lights out”: view distance of the High Performers decreases | M4 | Later |
| Settings for the host: number of Free Riders, tasks, times, speed | M4 | Later |

## Area 4: Minigames and extra modes

| Feature | Milestone | Status |
|---|---|---|
| Frame for minigames: open at a station, close, report “done” | M2 | Done |
| All minigames playable in narrow and low windows, from 320 px wide; the six at stations 7 to 12 fit a 1280x600 or 1024x600 window without scrolling (S-206) | M2 | Done |
| Canteen: put four of six dishes from the order slip onto the tray | M2 | Done |
| Mon Café: prepare a drink by recipe at the coffee machine | M2 | Done |
| Lecture Hall: put slides into the right order | M2 | Done |
| CTT Student Hall: sort books by number onto the shelf | M2 | Done |
| Pingo Doce: scan products until exactly the target amount comes out | M2 | Done |
| Duel: three stations per player, own random route with a walking distance of equal length | M2 | Done |
| Duel: progress of every player as 1/3 with a bar in the Players list of the panel (S-130) | M2 | Done |
| Panel of the mode at the top of the side panel in every mode (Duel and Solo: next task and clock; Classic: group progress; the own task is in the card at the top left, S-197), visible without scrolling with eight players (S-143) | M2 | Done |
| Six more minigames at stations 7 to 12, in Duel, Solo and Classic (S-124) | M2 | Done |
| Stations 7, 10 and 12 reworked: rebuild a misleading chart from survey counts, deduce a schedule from chat clues (told in one of four ways, M2-4.22), catch falling pages in three lanes; each with its own brief, feedback and retry (S-189) | M2 | Done |
| Solo mode for one player, without statistics (S-125); a new lobby starts in Solo and the second player switches it to Duel (S-203) | M2 | Done |
| Duel: every player starts at a different station, up to 8 players (S-126) | M2 | Done |
| Stations as objects with a pulsing outline when they matter (S-128); station 6 shows its surfboard too, and stations 4, 8, 9 and 12 stand where Felix drew them (S-196) | M2 | Done |
| Card at the top left with room and next task, direction arrow (S-129) | M2 | Done |
| Classic: current task and arrow use the same top-left card as Duel, which also says “All your tasks are done.” or, to the Free Rider, “Fake tasks: stand at a station to look busy.”; no task card above group progress (S-197, replaces S-145) | M3 | Done (M3-4.29) |
| Lobby: modes outside their player range (Classic below 4) locked, all in one grey, the chosen one marked by frame and shadow; smaller “?” with even gaps (S-146) | M2 | Done |
| “Done” for 0.5 s without a close button (S-127) | M2 | Done |
| Catch the wave at station 6 in Duel, Solo and Classic | M4 | Implemented locally |
| Duel: leaderboard with times at the end | M2 | Done |
| Beach exit: “Catch the wave”, click at the right moment (first “If time allows” minigame) | M4 | Planned |
| Canteen: stop the microwave at the right moment | M4 | Planned |
| Lecture Hall: record attendance by QR code | M4 | Planned |
| CTT Student Hall: find the mistake in the spreadsheet formula | M4 | Planned |
| Mon Café: put chairs in rows for the event | M4 | Later |
| Deadline mode: shared clock, progress bar, random disruptions | M4 | Planned |
| Duel variants: best of 3, knockout rounds | M4 | Later |
