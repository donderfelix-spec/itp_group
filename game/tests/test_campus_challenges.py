"""New challenge controls solve the generated packets and clean up on close."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from server.modes import room_tasks


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is needed for client interaction tests')
def test_new_challenges_success_retry_and_cancellation():
    packets = {name: generator(random.Random(42)) for name, generator in [
        ('chart', room_tasks.slides), ('chat', room_tasks.chat), ('rescue', room_tasks.seagull),
    ]}
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('challenges_in_node.js'))],
        input=json.dumps(packets), capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('seed', range(30))
def test_chat_clues_admit_exactly_one_schedule(seed):
    """Check the relational clue recipe, rather than trusting its answer packet."""
    import itertools

    content = room_tasks.chat(random.Random(seed))
    answer = content['schedule']
    first, second, third, last = [entry['person'] for entry in answer]
    jobs = [entry['job'] for entry in answer]
    solutions = []
    for people in itertools.permutations(content['people']):
        positions = {person: index for index, person in enumerate(people)}
        if not (positions[first] < positions[third]
                and positions[second] == positions[first] + 1
                and positions[third] == positions[second] + 1
                and positions[last] == 3):
            continue
        for work in itertools.permutations(content['jobs']):
            job_positions = {job: index for index, job in enumerate(work)}
            if (work[positions[first]] == jobs[0] and work[positions[third]] == jobs[2]
                    and job_positions[jobs[1]] < job_positions[jobs[2]]
                    and job_positions[jobs[3]] > job_positions[jobs[2]]):
                solutions.append((people, work))
    assert len(solutions) == 1
    assert list(solutions[0][0]) == [entry['person'] for entry in answer]
    assert list(solutions[0][1]) == jobs
