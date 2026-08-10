"""Build ffmpeg xfade transition chains and their offsets (network-free, testable)."""
import random

# Clean, non-cropping transitions only.  Excludes circlecrop/circleopen and wipes —
# the circle mask cut faces and important areas out of the frame mid-transition.
_PALETTE = ["fade", "dissolve", "fadeblack", "smoothleft", "smoothright",
            "slideup", "slidedown"]

def xfade_offsets(durations, overlap):
    offs = []
    for k in range(1, len(durations)):
        offs.append(sum(durations[:k]) - overlap * k)
    return offs

def pick_transitions(n_transitions, seed, palette=None):
    palette = palette or _PALETTE
    rng = random.Random(seed)
    return [rng.choice(palette) for _ in range(max(0, n_transitions))]

def build_video_xfade(n, durations, overlap, transitions):
    if n <= 1:
        return "[0:v]null[vout]"
    offs = xfade_offsets(durations, overlap)
    prev = "[0:v]"
    parts = []
    for i in range(1, n):
        out = "[vout]" if i == n - 1 else f"[vx{i}]"
        tr = transitions[i - 1] if i - 1 < len(transitions) else "fade"
        parts.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={overlap}:"
                     f"offset={offs[i-1]:.3f}{out}")
        prev = out
    return ";".join(parts)

# ---------- segmented (two-level) assembly helpers ----------
# The episode-level xfade chain opens every clip as a live ffmpeg input; with
# 30+ clips that is >6GB of decoders on a 2GB box (Jul-4 2026 OOM hang).  The
# helpers below split assembly into segments of <= seg_size clips whose
# xfade'd outputs are then xfade-joined, preserving the exact single-pass
# duration ( sum(durs) - overlap*(n-1) ) and transition sequence.

def partition_segments(n, seg_size):
    """Contiguous index runs of at most seg_size covering range(n)."""
    return [list(range(i, min(i + seg_size, n))) for i in range(0, n, seg_size)]

def segment_durations(durations, segments, overlap):
    """Duration of each segment after its internal xfade shrink."""
    return [sum(durations[j] for j in seg) - overlap * (len(seg) - 1)
            for seg in segments]

def segment_transitions(transitions, segments):
    """Split the global transition list (transitions[j] = boundary j->j+1)
    into (per-segment internal transitions, between-segment join transitions).
    Concatenating internal[0] + [joins[0]] + internal[1] + ... rebuilds the
    original list, so the on-screen transition sequence is unchanged."""
    internal = [[transitions[j] for j in seg[:-1]] for seg in segments]
    joins = [transitions[seg[-1]] for seg in segments[:-1]]
    return internal, joins

