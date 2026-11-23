"""New funny tasks extend Duel without replacing its five original games."""
import itertools
import json
import random

import pytest

from server.modes import brew_order, build_tray, minigames, room_tasks
from server.modes import self_checkout, shelve_books, sort_slides

NEW_STATIONS = tuple(range(7, 13))
ORIGINALS = {1: sort_slides, 2: brew_order, 3: build_tray, 4: shelve_books, 5: self_checkout}


def test_original_games_are_kept_and_six_extra_stations_are_added():
    assert set(minigames.MINIGAMES) == set(range(1, 7)) | set(NEW_STATIONS)
    for station, module in ORIGINALS.items():
        assert minigames.MINIGAMES[station] is module.MINIGAME
    assert set(room_tasks.MINIGAMES) == set(NEW_STATIONS)
    assert set(room_tasks.ROOMS) == set(NEW_STATIONS)


@pytest.mark.parametrize('seed', range(20))
def test_extra_room_contents_are_solvable_and_readable(seed):
    rng = random.Random(seed)
    contents = {station: game.make_content(rng) for station, game in room_tasks.MINIGAMES.items()}
    for station, content in contents.items():
        assert content['kind'] == ('campus_challenge' if station in (7, 10, 12) else 'campus_task')
        assert room_tasks.MINIGAMES[station].min_seconds == 1
        json.dumps(content)
    slides = contents[7]
    assert slides['puzzle'] == 'chart'
    assert len({row['label'] for row in slides['rows']}) == 3
    assert all(2 <= row['count'] <= 8 and row['sample'] == 10 for row in slides['rows'])
    assert set(slides['initial_labels']) == {row['label'] for row in slides['rows']}
    # The requested canteen redesign deliberately replaces six whole dishes
    # with exactly sixteen individual grains/pieces on one mixed lunch tray.
    lunch = contents[9]
    assert lunch['puzzle'] == 'cleanup' and lunch['theme'] == 'food'
    assert len(lunch['items']) == len({item['id'] for item in lunch['items']}) == 16
    for food, label, count, bad in [('rice', 'Rice grain', 10, 3), ('vegetable', 'Vegetable piece', 3, 1),
                                    ('chicken', 'Chicken piece', 3, 1)]:
        pieces = [item for item in lunch['items'] if item['id'].startswith(food + '-')]
        assert {item['id'] for item in pieces} == {f'{food}-{index}' for index in range(count)}
        assert sum(item['remove'] for item in pieces) == bad
        assert sum(not item['remove'] for item in pieces) == count - bad
        for item in pieces:
            assert set(item) == {'id', 'label', 'remove'}
            assert item['label'] == label
    coffee = contents[8]
    assert coffee['recipe'] and set(coffee['recipe']) <= set(coffee['controls'])
    chat = contents[10]
    assert chat['puzzle'] == 'chat_logic'
    assert {row['person'] for row in chat['schedule']} == set(chat['people'])
    assert 'jobs' not in chat
    assert all(set(row) == {'person', 'slot'} for row in chat['schedule'])
    assert sorted(row['slot'] for row in chat['schedule']) == chat['slots']
    assert len(chat['clues']) == 4
    prices = [item['price'] for item in contents[11]['products']]
    target = contents[11]['target']
    assert max(prices) < target
    assert any(sum(three) == target for three in itertools.combinations(prices, 3))
    rescue = contents[12]
    assert rescue['goal'] == 6
    assert sum(wave['cargo'] == 'page' for wave in rescue['waves']) == 8
    assert len(rescue['waves']) == 12
    assert all(0 <= wave['lane'] <= 2 and 1200 <= wave['duration'] <= 2200 for wave in rescue['waves'])


def test_seed_controls_content_and_new_openings_can_have_different_content():
    for game in room_tasks.MINIGAMES.values():
        assert game.make_content(random.Random(3)) == game.make_content(random.Random(3))
        variants = {json.dumps(game.make_content(random.Random(seed)), sort_keys=True) for seed in range(15)}
        assert len(variants) > 1


def test_lunch_piece_ids_are_stable_while_mould_and_order_change_between_openings():
    trays = [room_tasks.lunch(random.Random(seed))['items'] for seed in range(12)]
    expected_ids = {item['id'] for item in trays[0]}
    assert all({item['id'] for item in tray} == expected_ids for tray in trays)
    assert len({tuple(item['id'] for item in tray) for tray in trays}) > 1
    assert len({tuple(sorted(item['id'] for item in tray if item['remove'])) for tray in trays}) > 1
