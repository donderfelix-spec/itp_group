"""Keep actor-motion measurements independent of a camera clamped at map edges."""
import json
import math
from pathlib import Path

CAMPUS = json.loads((Path(__file__).parents[1] / "client/js/world/campus.json").read_text())
# Both playback harnesses use a 1280 x 800 Canvas and a 260-unit long side.
HALF_WIDTH = 130
HALF_HEIGHT = 81.25


def with_tracked_player(frames, players, own):
    character = next((player["character"] for player in players if player["name"] == own), None)
    for frame in frames:
        actor = next((actor for actor in frame["characters"] if actor["character"] == character), None)
        if actor is None:
            frame["tracked"] = dict(frame["camera"])
            continue
        point = {"x": actor["x"], "y": actor["middleY"] - 5 + actor["size"] / 2}
        frame["tracked"] = point
        expected = (
            max(HALF_WIDTH, min(CAMPUS["width"] - HALF_WIDTH, point["x"])),
            max(HALF_HEIGHT, min(CAMPUS["height"] - HALF_HEIGHT, point["y"])),
        )
        assert math.dist((frame["camera"]["x"], frame["camera"]["y"]), expected) < 1e-6
    return frames
