"""Plan how a narration beat is split into <=10s sub-shots and which cue each uses."""
import math

def num_subshots(beat_duration, n_cues, target=7.0, max_shot=10.0, min_shot=2.5):
    if beat_duration <= 0 or n_cues <= 0:
        return 0
    floor_n = math.ceil(beat_duration / max_shot)      # cap: each shot <= max_shot
    ideal_n = max(1, round(beat_duration / target))    # aesthetic ~target length
    n = max(floor_n, min(ideal_n, max(n_cues, floor_n)))
    # never create shots shorter than min_shot (unless the whole beat is shorter)
    while n > 1 and beat_duration / n < min_shot:
        n -= 1
    return n

def subshot_durations(beat_duration, n_shots):
    if n_shots <= 0:
        return []
    base = beat_duration / n_shots
    ds = [base] * n_shots
    drift = beat_duration - sum(ds)
    ds[-1] += drift                                     # absorb float error
    return ds

def cue_indices(n_shots, n_cues):
    return [i % n_cues for i in range(n_shots)]

def plan_subshots(beat_duration, n_cues, target=7.0, max_shot=10.0, min_shot=2.5):
    n = num_subshots(beat_duration, n_cues, target, max_shot, min_shot)
    if n == 0:
        return []
    return list(zip(cue_indices(n, n_cues), subshot_durations(beat_duration, n)))
