"""Per-run numbers from measure_walk.js: frame time, gaps between positions
messages, and frames in which the camera stood still while the server said
the player walks (a stall). Usage: python3 analyze_walk.py RUN.json ..."""
import json, sys, statistics as st, bisect

def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p / 100 * len(xs)))] if xs else float('nan')

def analyze(path):
    d = json.load(open(path))
    me = d['ownName']
    frames = d['frames']; msgs = d['msgs']
    mt = [m['t'] for m in msgs]
    mx = []
    for m in msgs:
        own = [p for p in m['players'] if p['name'] == me]
        mx.append(own[0]['x'] if own else None)
    gaps = [b - a for a, b in zip(mt, mt[1:])]
    ft = [f['t'] for f in frames]
    fint = [b - a for a, b in zip(ft, ft[1:])]
    dur = [f['dur'] for f in frames]
    scale = frames[0]['scale']
    moving_frames = stalls = episodes = jumps = 0
    run = longest = 0; slow = 0; in_stall = False; moves = []
    for i in range(1, len(frames)):
        t = ft[i]
        k = bisect.bisect_right(mt, t)  # msgs[k-1] is last before t
        if k < 2 or k >= len(msgs):
            continue
        a, b, c = mx[k - 2], mx[k - 1], mx[k]
        moving = None not in (a, b, c) and abs(b - a) > 1 and abs(c - b) > 1 and (b - a) * (c - b) > 0
        dist = abs(frames[i]['cx'] - frames[i - 1]['cx'])
        if not moving:
            if in_stall: in_stall = False
            run = 0; continue
        moving_frames += 1; moves.append(dist)
        slow += dist < 0.75
        if dist < 0.05:
            stalls += 1; run += fint[i - 1]; longest = max(longest, run)
            if not in_stall: episodes += 1; in_stall = True
        else:
            if in_stall and dist > 2.25: jumps += 1
            in_stall = False; run = 0
    secs = (ft[-1] - ft[0]) / 1000
    walk_secs = moving_frames / 60
    return {
        'file': path, 'players': d['players'], 'seconds': round(secs, 1),
        'fps': round(len(frames) / secs, 1),
        'frame_interval_p50/p99/max_ms': [round(pct(fint, 50), 1), round(pct(fint, 99), 1), round(max(fint), 1)],
        'draw_ms_mean/p95/max': [round(st.mean(dur), 2), round(pct(dur, 95), 2), round(max(dur), 2)],
        'msg_gap_mean/p5/p95/max_ms': [round(st.mean(gaps), 1), round(pct(gaps, 5), 1), round(pct(gaps, 95), 1), round(max(gaps), 1)],
        'msg_gaps_over_67ms_%': round(100 * sum(g > 66.7 for g in gaps) / len(gaps), 1),
        'msg_gaps_under_20ms': sum(g < 20 for g in gaps),
        'walking_frames': moving_frames,
        'stall_frames_%': round(100 * stalls / max(1, moving_frames), 1),
        'stall_episodes_per_s': round(episodes / max(0.01, walk_secs), 2),
        'jumps_after_stall': jumps,
        'slow_frames_%(<half speed)': round(100 * slow / max(1, moving_frames), 1),
        'longest_stall_ms': round(longest, 1),
        'move_per_frame_units_mean/sd': [round(st.mean(moves), 2), round(st.pstdev(moves), 2)],
        'px_per_unit': round(scale, 2),
    }

for p in sys.argv[1:]:
    print(json.dumps(analyze(p)))
