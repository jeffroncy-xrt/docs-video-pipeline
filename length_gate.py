#!/usr/bin/env python3
"""Ensure an episode renders >= MIN_SECS by auto-extending SHORT ones with real
new beats (grounded narration + real/AI imagery) — never by stretching clips.

Runs right after voice.py in run_daily.sh / build_manual.sh:
    .venv/bin/python length_gate.py <slug>
Reads render/a_NN.wav (VO) to estimate runtime; on a deficit it asks Groq for
extra grounded beats, inserts them before the outro, rewrites beats.py, and
voices ONLY the new beats.  On any LLM failure it prints QA-WARN and exits 0.
"""
import os, sys, json, math, wave, subprocess


def is_pathb(beats):
    return any((b.get("omni_prompt") or "").strip() for b in beats)


def beats_needed(current_secs, target_secs, avg_beat_secs):
    if current_secs >= target_secs:
        return 0
    if avg_beat_secs <= 0:
        avg_beat_secs = 25.0
    return math.ceil((target_secs - current_secs) / avg_beat_secs)


def estimate_runtime(beats, dur_fn, lead=0.25, tail=0.65, ch_dur=2.6, overlap=0.5):
    n = len(beats)
    total = 0.0
    for i in range(n):
        d = dur_fn(i)
        total += ch_dur if d is None else (lead + d + tail)
    if n > 1:
        total -= overlap * (n - 1)
    return total


def insert_beats(beats, new):
    out_idx = max((i for i, b in enumerate(beats) if b.get("scene") == "outro"),
                  default=None)
    pos = len(beats) if out_idx is None else out_idx
    merged = beats[:pos] + list(new) + beats[pos:]
    idxs = list(range(pos, pos + len(new)))
    return merged, idxs


def shift_wavs(pos, n, old_len, work="render"):
    """After insert_beats() shifts beats [pos, old_len) up by n, move their voice
    files with them: a_{i}.wav -> a_{i+n}.wav, highest index first so overlapping
    ranges never clobber.  Without this the outro's wav stays at its OLD index,
    gets overwritten when the new beats are voiced, and the outro renders as a
    silent 2.6s card (shipped that way in the Jul-2 cherokee-dna-myth video)."""
    for i in range(old_len - 1, pos - 1, -1):
        src = f"{work}/a_{i:02d}.wav"
        if os.path.exists(src):
            os.replace(src, f"{work}/a_{i + n:02d}.wav")


def vo_dur(i, work="render"):
    p = f"{work}/a_{i:02d}.wav"
    if not os.path.exists(p):
        return None
    with wave.open(p) as w:
        return w.getnframes() / float(w.getframerate())


# The prompt-construction helpers (_existing_context, build_extend_prompt)
# are omitted from this excerpt: they embed the tuned generation prompt.
# The duration-gating logic below is the part worth reading.

TARGET = float(os.environ.get("MIN_SECS", "540"))   # 9:00 floor, both paths
MAX_ROUNDS = int(os.environ.get("MAX_EXTEND_ROUNDS", "2"))
MAX_BEATS = int(os.environ.get("MAX_BEATS", "40"))


def _load_topic(slug):
    try:
        for t in json.load(open("topics.json"))["topics"]:
            if t["slug"] == slug:
                return t
    except Exception:
        pass
    return None


def _write_beats(subject, beats, culture=""):
    # CULTURE must survive the rewrite — it anchors veo prompts, archival
    # search, and audit's semantic gate for every stage that runs after us.
    with open("beats.py", "w") as f:
        f.write("# Rewritten by length_gate.py — original + auto-extension beats\n")
        f.write("SUBJECT = " + json.dumps(subject, ensure_ascii=False) + "\n")
        f.write("CULTURE = " + json.dumps(culture or "", ensure_ascii=False) + "\n")
        f.write("BEATS = " + json.dumps(beats, indent=1, ensure_ascii=False) + "\n")


def main(argv):
    slug = argv[1] if len(argv) > 1 else ""
    import importlib, beats as beats_mod
    importlib.reload(beats_mod)
    beats = list(beats_mod.BEATS)
    subject = getattr(beats_mod, "SUBJECT", "")
    culture = getattr(beats_mod, "CULTURE", "")
    topic = _load_topic(slug)
    py = os.environ.get("PYBIN", ".venv/bin/python")

    for rnd in range(MAX_ROUNDS):
        est = estimate_runtime(beats, vo_dur)
        print(f"length_gate: estimate {est/60:.1f} min ({est:.0f}s), target {TARGET/60:.1f} min")
        if est >= TARGET:
            print("length_gate: OK (>= target)"); return 0
        if len(beats) >= MAX_BEATS:
            print(f"QA-WARN: at MAX_BEATS={MAX_BEATS} but still {est/60:.1f} min"); return 0
        avg = est / max(1, len(beats))
        n = min(beats_needed(est, TARGET, avg), MAX_BEATS - len(beats))
        print(f"length_gate: extending by {n} beats (round {rnd+1}/{MAX_ROUNDS})")
        try:
            from gen_script import groq, normalize_beat, rebalance_cues, clean_label
            import re
            raw = re.sub(r"^```json|```$", "", groq(build_extend_prompt(topic, beats, n)).strip()).strip()
            new = json.loads(raw).get("beats", [])
            new = [normalize_beat(b) for b in new if (b.get("narr") or "").strip()][:n]
        except Exception as e:
            print(f"QA-WARN: extension LLM failed ({e}); rendering as-is at {est/60:.1f} min")
            return 0
        if not new:
            print("QA-WARN: LLM returned no usable beats; rendering as-is"); return 0
        for b in new:
            b["scene"] = b.get("scene") if b.get("scene") in ("plain", "dna", "fact") else "plain"
            b.pop("omni_prompt", None)          # extension beats are gap beats (imagery, no clip)
            if b.get("headline"):               # same card-text + people-first hygiene as gen
                b["headline"] = clean_label(b["headline"], 60)
        new = rebalance_cues(new, culture=culture)  # cap abstract + people-convert new beats too
        merged, idxs = insert_beats(beats, new)
        for i in idxs:
            merged[i].setdefault("seed", 100 + i)
        _write_beats(subject, merged, culture=culture)
        # move existing voice files with their shifted beats (outro keeps its VO)
        shift_wavs(idxs[0], len(idxs), len(beats))
        beats = merged
        # voice ONLY the new beats (indices are post-insert positions)
        subprocess.run([py, "voice.py", *[str(i) for i in idxs]], check=False)

    est = estimate_runtime(beats, vo_dur)
    if est < TARGET:
        print(f"QA-WARN: still {est/60:.1f} min after {MAX_ROUNDS} rounds")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
