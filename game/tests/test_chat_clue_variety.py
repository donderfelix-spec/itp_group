"""Station 10, "Decode the group chat" (to-do M2-4.22).

The clues are read the way a player reads them: every sentence is turned into
a rule, and all 24 orders are tried. Exactly one may fit, the one the
server checks against. The structure of the clues varies between rounds.
Since S-223 only the time is asked: no clue names a deliverable.
"""

import itertools
import random
import re

import pytest

from server.modes import room_tasks

SEEDS = range(200)
NAME = r"(Mara|Tiago|Ines|Rui)"
JOB = r"(Slides|Survey|Budget|Sources)"  # the work categories before S-223

# Each sentence a clue can contain, with the rule it states. `me` is the
# speaker; `slot` maps a person to 0..3.
SENTENCES = [
    (rf"I present before {NAME}\.", lambda me, other: lambda slot: slot[me] < slot[other]),
    (rf"I present after {NAME}\.", lambda me, other: lambda slot: slot[me] > slot[other]),
    (rf"I go immediately before {NAME}\.", lambda me, other: lambda slot: slot[me] + 1 == slot[other]),
    (rf"I go immediately after {NAME}\.", lambda me, other: lambda slot: slot[me] == slot[other] + 1),
    (rf"My slot is immediately after {NAME}'s\.", lambda me, other: lambda slot: slot[me] == slot[other] + 1),
    (r"I'm first\. Somebody has to wake everyone up\.", lambda me: lambda slot: slot[me] == 0),
    (r"I'm second\. Not first, not last\.", lambda me: lambda slot: slot[me] == 1),
    (r"I'm the third to present\.", lambda me: lambda slot: slot[me] == 2),
    (r"I'm last\. Please leave some coffee\.", lambda me: lambda slot: slot[me] == 3),
]


def rules_of(content):
    """Every clue as a list of rules; fail on any sentence the test cannot read."""
    rules = []
    for clue in content["clues"]:
        rest = clue["text"]
        while rest:
            for pattern, rule in SENTENCES:
                found = re.match(pattern + r" ?", rest)
                if found:
                    rules.append(rule(clue["from"], *found.groups()))
                    rest = rest[found.end():]
                    break
            else:
                pytest.fail(f"Unreadable clue: {rest!r}")
    return rules


@pytest.mark.parametrize("seed", SEEDS)
def test_the_clues_admit_exactly_the_one_schedule_the_server_checks(seed):
    content = room_tasks.chat(random.Random(seed))
    rules = rules_of(content)
    solutions = []
    for people in itertools.permutations(content["people"]):
        slot = {person: index for index, person in enumerate(people)}
        if all(rule(slot) for rule in rules):
            solutions.append(list(people))
    assert solutions == [[row["person"] for row in content["schedule"]]]


def test_the_speaker_at_nine_does_not_always_say_the_same_kind_of_thing():
    first_sentences = set()
    for seed in SEEDS:
        content = room_tasks.chat(random.Random(seed))
        first = content["schedule"][0]["person"]
        text = next(clue["text"] for clue in content["clues"] if clue["from"] == first)
        # Names vary anyway; compare the bare sentence.
        first_sentences.add(re.sub(NAME, "_", text))
    assert len(first_sentences) >= 3


def test_every_way_of_ordering_the_slots_is_used():
    used = set()
    for seed in SEEDS:
        rng = random.Random(seed)
        content = room_tasks.chat(rng)
        texts = {clue["text"] for clue in content["clues"]}
        used.add(next(index for index, clues in enumerate(room_tasks.SLOT_CLUES)
                      if all(any(text.startswith(sentence) for text in texts)
                             for sentence in clues([row["person"] for row in content["schedule"]]))))
    assert used == set(range(len(room_tasks.SLOT_CLUES)))


def test_no_sentence_has_the_old_ungrammatical_comes_after():
    for seed in SEEDS:
        for clue in room_tasks.chat(random.Random(seed))["clues"]:
            assert "comes after" not in clue["text"]
            assert "My deliverable is" not in clue["text"]


def test_no_clue_names_a_deliverable_and_there_is_no_pinned_message():
    for seed in SEEDS:
        content = room_tasks.chat(random.Random(seed))
        assert "jobs" not in content
        for clue in content["clues"]:
            assert clue["from"] != "Pinned message"
            assert not re.search(JOB, clue["text"]), clue["text"]


def test_each_round_has_four_people_with_one_clue_each():
    for seed in SEEDS:
        content = room_tasks.chat(random.Random(seed))
        senders = [clue["from"] for clue in content["clues"]]
        assert sorted(senders) == sorted(content["people"])
        assert len(content["schedule"]) == 4
