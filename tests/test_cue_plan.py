import math, pytest
from cue_plan import num_subshots, subshot_durations, cue_indices, plan_subshots

def test_short_beat_one_shot():
    assert num_subshots(6.0, 3) == 1          # ~target, one shot is fine

def test_long_beat_honors_max_cap():
    n = num_subshots(50.0, 8)
    assert n >= math.ceil(50.0 / 10.0)        # every shot <= 10s
    assert max(subshot_durations(50.0, n)) <= 10.0 + 1e-6

def test_targets_about_seven_seconds_when_cues_allow():
    assert num_subshots(21.0, 4) == 3         # round(21/7)=3, <=4 cues

def test_cue_count_limits_distinct_but_not_cap():
    # 50s with only 2 cues: still need >=5 shots for the 10s cap; cues cycle
    n = num_subshots(50.0, 2)
    assert n >= 5
    idx = cue_indices(n, 2)
    assert set(idx) == {0, 1} and len(idx) == n

def test_durations_sum_exactly():
    ds = subshot_durations(50.0, 7)
    assert abs(sum(ds) - 50.0) < 1e-6 and len(ds) == 7

def test_floor_prevents_too_short_shots():
    # tiny beat, many cues -> never produce sub-2.5s slivers
    n = num_subshots(4.0, 4)
    assert all(d >= 2.5 - 1e-6 for d in subshot_durations(4.0, n)) or n == 1

def test_plan_subshots_pairs_cue_and_duration():
    plan = plan_subshots(21.0, 4)
    assert [c for c, _ in plan] == [0, 1, 2]
    assert abs(sum(d for _, d in plan) - 21.0) < 1e-6


def test_plan_all_distinct_when_cues_cover_beat():
    plan = plan_subshots(22.0, 3)
    idxs = [c for c, _ in plan]
    assert sorted(idxs) == [0, 1, 2]


def test_plan_repeats_only_when_beat_long_and_cues_few():
    plan = plan_subshots(40.0, 2)
    idxs = [c for c, _ in plan]
    assert len(idxs) >= 4
    assert set(idxs) == {0, 1}


def test_plan_short_beat_one_shot():
    plan = plan_subshots(6.0, 3)
    assert len(plan) == 1
