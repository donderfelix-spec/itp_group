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
- **M3 Classic:** A complete Classic round with Free Rider, meeting and vote is playable. Status 2026-11-21: playable with known defects, see M3-3.9 to M3-3.18 in [TODO.md](TODO.md).
- **M4 Extensions:** Sabotage, Deadline mode, finished characters, sound, phone.

As of 2026-11-21. Milestone 1 is on `main` and deployed.

## Area 1: Campus and characters

| Feature | Milestone | Status |
|---|---|---|
| Map with Lecture Hall, Mon Café, Canteen, CTT Student Hall and Pingo Doce, connected by the Main Deck | M1 | Done |
| Move the character with the keyboard (WASD or arrow keys) | M1 | Done |
| Walls and furniture stop the character | M1 | Done |
| Camera follows your own character | M1 | Done |
| See other players with their names above the character; where name labels would cover each other only one is shown, the own name first (S-117) | M1 | Done |
| Stations for tasks on the map | M2 | Done |
| Key hint in range: pulsing border around the target, coloured button with the key at the bottom right (E done; R and Q come with Classic) | M2 | In progress |
| Choose a character from the list of stereotypes | M2 | Done |
| Display of the current room | M2 | Planned |
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
| Limited view: You only see what is nearby and not behind a wall | M3 | Planned |
| Show failed players as ghosts | M3 | Planned |
| Four hiding spots in Classic in which the Free Rider is visible only within 35 map units (S-131 to S-140) | M3 | Done |
| Overview map with your own open tasks | M3 | Planned |
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
| Statistics per account: rounds and wins per mode, best Duel time | M2 | Done |
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
| Each High Performer gets their own list of tasks | M3 | Playable with known defects (the list is not shown yet, M3-3.17) |
| Shared progress bar of the group work | M3 | Done |
| Free Rider fails a nearby player, followed by a cooldown; the sheet shows the victim's portrait (S-163) | M3 | Playable with known defects (M3-3.13, M3-3.15) |
| Find and report a failed player | M3 | Playable with known defects (M3-3.15) |
| Report from 8 map units, also by the Free Rider; let fail from 20 map units with Q or F; F-sheets 30 % larger (S-180, S-181) | M3 | Done (M3-4.25 to M3-4.28) |
| Emergency meeting with the red button in the centre of the Main Deck (S-147), drawn as an alarm switch (S-149), limited per player, range checked by the server, hint only for the living (S-170) | M3 | Playable with known defects (M3-3.15: the wording “E Call meeting”) |
| Meeting with text chat and time limit; the window closes after the result (S-153) and always fits the screen (S-173) | M3 | Playable with known defects (M3-3.13) |
| Own task list per player, only its stations pulse; the Free Rider has none (S-154) | M3 | Done |
| Vote: choose a person or skip, the majority choice is voted out, nobody in case of a tie; votes are public and can be changed, after a report already during the discussion, 75 % Skip ends the meeting (S-160 to S-162); each vote button shows its number of votes in a fixed field (S-173) | M3 | Done |
| Result of the vote: character drifts out to sea, display whether it was a Free Rider | M3 | Playable with known defects (text only, no drifting yet, M3-3.5) |
| Ghosts keep doing their tasks, but they do not talk and do not vote; ghosts see the dead as “Dead” in the Players list (S-164) | M3 | Done (M3-3.9, M3-3.20, 2026-11-22) |
| Check the win conditions and show the end screen that reveals the roles; only the host sees “New Round” (S-173) | M3 | Done (M3-3.11, 2026-11-22) |
| A player who leaves a Classic round counts as failed; the round stops when too few players are left for its Free Riders (S-157, S-158); a leaver's Skip goes too, and 75 % Skip of those left ends the meeting (S-165) | M3 | Done (M3-3.8, M3-3.11, 2026-11-22) |
| Free Riders can only fake tasks | M3 | Planned (M3-3.17) |
| Sabotage “WiFi down”: tasks locked until someone restarts the router | M4 | Planned |
| Sabotage “Fire alarm”: Two players have to stand at two places in time, otherwise the Free Riders win | M4 | Planned |
| Sabotage “Lights out”: view distance of the High Performers decreases | M4 | Later |
| Settings for the host: number of Free Riders, tasks, times, speed | M4 | Later |

## Area 4: Minigames and extra modes

| Feature | Milestone | Status |
|---|---|---|
| Frame for minigames: open at a station, close, report “done” | M2 | Done |
| All minigames playable in narrow and low windows, from 320 px wide | M2 | Done |
| Canteen: put four of six dishes from the order slip onto the tray | M2 | Done |
| Mon Café: prepare a drink by recipe at the coffee machine | M2 | Done |
| Lecture Hall: put slides into the right order | M2 | Done |
| CTT Student Hall: sort books by number onto the shelf | M2 | Done |
| Pingo Doce: scan products until exactly the target amount comes out | M2 | Done |
| Duel: three stations per player, own random route with a walking distance of equal length | M2 | Done |
| Duel: progress of every player as 1/3 with a bar in the Players list of the panel (S-130) | M2 | Done |
| Panel of the mode at the top of the side panel in every mode (Duel and Solo: next task and clock; Classic: own tasks and group progress), visible without scrolling with eight players (S-143) | M2 | Done |
| Six more minigames at stations 7 to 12, in Duel, Solo and Classic (S-124) | M2 | Done |
| Stations 7, 10 and 12 reworked: rebuild a misleading chart from survey counts, deduce a schedule from chat clues, catch falling pages in three lanes; each with its own brief, feedback and retry (S-189) | M2 | Done |
| Solo mode for one player, without statistics (S-125) | M2 | Done |
| Duel: every player starts at a different station, up to 8 players (S-126) | M2 | Done |
| Stations as objects with a pulsing outline when they matter (S-128) | M2 | Done |
| Card at the top left with room and next task, direction arrow (S-129) | M2 | Done |
| Classic: the direction arrow points at the nearest own open task (S-145) | M3 | Done |
| Lobby: modes outside their player range (Classic below 4) locked, all in one grey, the chosen one marked by frame and shadow; smaller “?” with even gaps (S-146) | M2 | Done |
| “Done” for 0.5 s without a close button (S-127) | M2 | Done |
| Duel: leaderboard with times at the end | M2 | Done |
| Beach exit: “Catch the wave”, click at the right moment (first “If time allows” minigame) | M4 | Planned |
| Canteen: stop the microwave at the right moment | M4 | Planned |
| Lecture Hall: record attendance by QR code | M4 | Planned |
| CTT Student Hall: find the mistake in the spreadsheet formula | M4 | Planned |
| Mon Café: put chairs in rows for the event | M4 | Later |
| Deadline mode: shared clock, progress bar, random disruptions | M4 | Planned |
| Duel variants: best of 3, knockout rounds | M4 | Later |
