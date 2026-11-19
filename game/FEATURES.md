# Feature overview for “Group Project”

All features of the game with their status. Whoever finishes a feature or plans a new one updates the row here.

**Status values**

- **Done:** built, played through by the tester, on `main`.
- **In progress:** a branch for it is open.
- **Planned:** listed as a to-do in [TODO.md](TODO.md).
- **Later:** wanted, but no to-do yet.

**Milestones**

- **M1 Walking:** Several players meet in a lobby and walk across the campus together.
- **M2 Duel:** Minigames and the Duel mode are playable.
- **M3 Classic:** A complete Classic round with Free Rider, meeting and vote is playable.
- **M4 Extensions:** Sabotage, Deadline mode, finished characters, sound, phone.

As of 2026-11-18. The project skeleton is built, the game itself starts with milestone 1.

## Area 1: Campus and characters

| Feature | Milestone | Status |
|---|---|---|
| Map with Lecture Hall, Mon Café, Canteen, CTT Student Hall and Pingo Doce, connected by the Main Deck | M1 | Planned |
| Move the character with the keyboard (WASD or arrow keys) | M1 | Planned |
| Walls and furniture stop the character | M1 | In progress |
| Camera follows your own character | M1 | Planned |
| See other players with their names above the character | M1 | Planned |
| Stations for tasks on the map | M2 | Planned |
| Key hint in range: pulsing border around the target, coloured button with the key at the bottom right (E, R, Q) | M2 | Planned |
| Choose a character from the list of stereotypes | M2 | Planned |
| Display of the current room | M2 | Planned |
| Limited view: You only see what is nearby and not behind a wall | M3 | Planned |
| Show failed players as ghosts | M3 | Planned |
| Four hiding spots in which you are visible only from close by | M3 | Planned |
| Overview map with your own open tasks | M3 | Planned |
| Finished graphics for rooms and characters instead of placeholders | M4 | Planned |
| Sounds and music | M4 | Later |
| Touch controls for the phone | M4 | Later |

## Area 2: Network, lobby and foundation

| Feature | Milestone | Status |
|---|---|---|
| Start a server that delivers the client and the game | M0 | Done |
| Create an account with username and password, log in, log out | M1 | In progress |
| Play as a guest, without statistics and friends | M1 | In progress |
| Clear message when a name is taken, the password is wrong or the database is not reachable | M1 | In progress |
| Statistics per account: rounds and wins per mode, best Duel time | M2 | Planned |
| Leaderboard of all accounts | M2 | Planned |
| Add friends by username, accept or decline a request | M4 | Planned |
| See friends with the status “online” and “in a round” | M4 | Planned |
| Invite friends to your own lobby | M4 | Planned |
| Leaderboard among friends | M4 | Planned |
| Create a lobby, get a code with four letters | M1 | In progress |
| Join a lobby by code | M1 | In progress |
| Player list in the lobby, the creator is the host | M1 | In progress |
| Continuously synchronise the positions of all players, with smoothed movement of the others | M1 | Planned |
| Host chooses mode and settings and starts the round | M2 | Planned |
| After the round back to the lobby, new round without a new code | M2 | Planned |
| If someone leaves the game, the round continues, and the host changes if needed | M2 | Planned |
| Players who were disconnected for a short time come back into their round | M3 | Planned |
| Each client gets only the information that its player is allowed to know | M3 | Planned |
| Game reachable at a public URL, deployed automatically from `main` | M0 | Done |
| Several lobbies at the same time | M1 | In progress |

## Area 3: Classic rules

| Feature | Milestone | Status |
|---|---|---|
| Assign roles at random at the start, the role is shown to each player individually | M3 | Planned |
| Each High Performer gets their own list of tasks | M3 | Planned |
| Shared progress bar of the group work | M3 | Planned |
| Free Rider fails a nearby player, followed by a cooldown | M3 | Planned |
| Find and report a failed player | M3 | Planned |
| Emergency meeting with the red button on the Main Deck, limited per player | M3 | Planned |
| Meeting with text chat and time limit | M3 | Planned |
| Vote: choose a person or skip, the majority choice is voted out, nobody in case of a tie | M3 | Planned |
| Result of the vote: character drifts out to sea, display whether it was a Free Rider | M3 | Planned |
| Ghosts keep doing their tasks, but they do not talk and do not vote | M3 | Planned |
| Check the win conditions and show the end screen that reveals the roles | M3 | Planned |
| Free Riders can only fake tasks | M3 | Planned |
| Sabotage “WiFi down”: tasks locked until someone restarts the router | M4 | Planned |
| Sabotage “Fire alarm”: Two players have to stand at two places in time, otherwise the Free Riders win | M4 | Planned |
| Sabotage “Lights out”: view distance of the High Performers decreases | M4 | Later |
| Settings for the host: number of Free Riders, tasks, times, speed | M4 | Later |

## Area 4: Minigames and extra modes

| Feature | Milestone | Status |
|---|---|---|
| Frame for minigames: open at a station, close, report “done” | M2 | Planned |
| Canteen: put four of six dishes from the order slip onto the tray | M2 | Planned |
| Mon Café: prepare a drink by recipe at the coffee machine | M2 | Planned |
| Lecture Hall: put slides into the right order | M2 | Planned |
| CTT Student Hall: sort books by number onto the shelf | M2 | Planned |
| Pingo Doce: scan products until exactly the target amount comes out | M2 | Planned |
| Duel: three stations per player, own random route with a walking distance of equal length | M2 | Planned |
| Duel: progress of the opponents as 1/3 at the edge | M2 | Planned |
| Duel: leaderboard with times at the end | M2 | Planned |
| Beach exit: “Catch the wave”, click at the right moment (first “If time allows” minigame) | M4 | Planned |
| Canteen: stop the microwave at the right moment | M4 | Planned |
| Lecture Hall: record attendance by QR code | M4 | Planned |
| CTT Student Hall: find the mistake in the spreadsheet formula | M4 | Planned |
| Mon Café: put chairs in rows for the event | M4 | Later |
| Deadline mode: shared clock, progress bar, random disruptions | M4 | Planned |
| Duel variants: best of 3, knockout rounds | M4 | Later |
