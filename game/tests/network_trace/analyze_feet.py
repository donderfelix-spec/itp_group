"""Smoothness of one measure_walk.js run, from 1 s after walking began and away
from turnarounds: frozen frames, stalls per second, the longest stall, frames
in which the feet stand still mid-stride, and the fastest catch-up as a
multiple of the normal speed of 90 units per second.
Usage: python3 analyze_feet.py RUN.json ..."""
import json, sys
def own_fig(f):
    if not f['figs']: return None
    return min(f['figs'], key=lambda g: abs(g['x'] - f['cx']))
def stats(path):
    d = json.load(open(path)); fr = d['frames']
    downs = [k['t'] for k in d['keys'] if k['down']]; t0 = downs[0] + 1000; t1 = d['keys'][-1]['t']
    keys = [k['t'] for k in d['keys']]
    frozen = episodes = midair = fast = n = 0; longest = run = 0; prev = False; maxspeed = 0
    for a, b in zip(fr, fr[1:]):
        if not (t0 < b['t'] < t1) or min(abs(b['t'] - k) for k in keys) < 400: prev = False; run = 0; continue
        n += 1
        mv = abs(b['cx'] - a['cx']); dt = b['t'] - a['t']
        speed = mv / dt * 1000
        maxspeed = max(maxspeed, speed)
        if speed > 1.5 * 90: fast += 1
        st = mv < 0.05
        if st:
            frozen += 1; run += dt; longest = max(longest, run)
            if not prev: episodes += 1
        else: run = 0
        prev = st
        ga, gb = own_fig(a), own_fig(b)
        if ga and gb and gb['phase'] is not None and ga['phase'] is not None and gb['phase'] == ga['phase'] and gb['stride'] > 0.5:
            midair += 1
    secs = n / 60
    return f"frozen {100*frozen/n:.1f} % | {episodes/secs:.2f}/s | longest {longest:.0f} ms | feet frozen mid-stride {100*midair/n:.1f} % | max speed {maxspeed/90:.2f}x | frames >1.5x {100*fast/n:.1f} %"
for p in sys.argv[1:]:
    print(p, '|', stats(p))
