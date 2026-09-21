#!/usr/bin/env python3
"""Rebuild an episode's YouTube description AFTER render: hook + timestamped
chapters (from real beat durations) + source citation + hashtags.  Chapters need
timestamps that only exist post-render, so this runs between build_v2 and upload.

    .venv/bin/python build_description.py <slug>
Reads episodes/<slug>/{beats.py, seo.json} + render/clip_NN.mp4 durations;
rewrites seo.json['description'] in place (tags untouched)."""
import os, sys, json, subprocess, re

# ⚠ The first two lines are what Google shows as the search snippet; past this
# it truncates mid-sentence. Borrowed, with the budget, from the sibling news pipeline,
# where the snippet limit was measured live.
SNIPPET_LIMIT = 157

# The channel blurb — the credibility claim the channel makes about its own
# method, and the block a viewer reads before subscribing. Roots had no
# equivalent, which is most of why the published description was six lines long.
#
# ⚠ NO channel name in this file: build_description.py SHIPS in the product
# build, which fails closed on author identity (test_dist_manifest). The sibling channel
# keeps its boilerplate in editorial data for the same reason — it is editorial data,
# not code. Override per-channel with DESC_BOILERPLATE; YouTube already shows
# the channel name above the description, so the default does not need it.
BOILERPLATE = os.environ.get("DESC_BOILERPLATE", "").strip() or (
    "This channel follows what ancient DNA is doing to the story of who our "
    "ancestors were — the peoples it connects, the migrations it rewrites, and "
    "the histories it quietly overturns. Every episode is built from "
    "peer-reviewed genetics and archaeology, with the study named on screen and "
    "cited above."
)


def _mmss(sec):
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def chapter_times(beats, durations, overlap=0.5):
    """[(mm:ss, chapter_title)] at cumulative start of each 'chapter' beat,
    adjusted for the episode xfade overlap shrink.  First entry forced to 00:00."""
    out = []
    clk = 0.0
    for i, b in enumerate(beats):
        start = clk - overlap * i
        if b.get("scene") == "chapter" and (b.get("headline") or "").strip():
            out.append((max(0.0, start), b["headline"].strip()))
        clk += durations[i] if i < len(durations) else 0.0
    if out:
        out[0] = (0.0, out[0][1])           # YouTube requires a 0:00 first chapter
    return [(_mmss(s), t) for s, t in out]


# The model is asked for a description and writes its own chapter list into it
# (gen_script's schema literally says "with a chapters list"). The REAL chapters
# are computed post-render from clip durations, so that list is both duplicate
# and wrong — and on 2026-08-21 the hook was scavenged out of it.
_CHAPTER_BLOCK = re.compile(
    r"(?is)\bchapters?\s*[:\-].*$"       # from "Chapters:" to the end
)
# ⚠ NOT `(?<=[.!?]) `. That splits "1. Grave mystery 2. Ancient genomes" into
# sentences, which is exactly how "Chapters: 1. Grave mystery 2." became the
# published first line. A sentence ends at .!? followed by a space and a
# CAPITAL — a digit or a lowercase letter after the dot is a list or an
# abbreviation ("Lazaridis et al. found ..."), not a new sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00C0-\u00DC])")


def hook_from(desc, limit=SNIPPET_LIMIT):
    """The opening prose of a description: 1-2 real sentences, inside the
    search-snippet budget, with any chapter list the model invented removed.

    Returns "" when the model wrote nothing but a chapter list — the caller
    warns rather than publishing a garbled line.
    """
    text = _CHAPTER_BLOCK.sub("", desc or "").strip()
    text = re.sub(r"(?is)\bsources?\s*:.*$", "", text).strip()
    if not text:
        return ""
    parts = [p.strip() for p in _SENTENCE_END.split(text) if p.strip()]
    hook = " ".join(parts[:2]).strip()
    if len(hook) <= limit:
        return hook
    one = parts[0].strip()
    if len(one) <= limit:
        return one
    cut = one[:limit - 1]                 # -1 leaves room for the full stop
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:") + "."


def hashtags_from_tags(tags, n=6):
    out = []
    for t in tags:
        h = "#" + re.sub(r"[^a-z0-9]", "", t.lower())
        if len(h) > 1 and h not in out:
            out.append(h)
        if len(out) >= n:
            break
    return out


# YouTube renders a chapter list only from >=3 stamps with the first at 0:00.
MIN_CHAPTERS = 3
# YouTube's own floor is 10s; this is an editorial one. Chapters this close
# together are not navigation, they are a symptom — on 2026-08-22 the three
# stamps sat at 0:04/0:30/0:38 because the sixteen beats between them were
# unnarrated and had each collapsed to the 2.6s silent-card minimum.
MIN_CHAPTER_GAP = 20.0


def _secs(stamp):
    """'mm:ss' or 'hh:mm:ss' -> seconds."""
    parts = [int(p) for p in str(stamp).split(":")]
    out = 0
    for p in parts:
        out = out * 60 + p
    return float(out)


def chapter_gaps_ok(chapters, minimum=MIN_CHAPTER_GAP):
    """Whether consecutive stamps are far enough apart to be real navigation."""
    times = [_secs(ts) for ts, _ in chapters]
    return all(b - a >= minimum for a, b in zip(times, times[1:]))


def chapters_ok(chapters):
    """Whether this list will actually render as USEFUL chapters on YouTube."""
    return (len(chapters) >= MIN_CHAPTERS and bool(chapters)
            and chapters[0][0] in ("00:00", "0:00")
            and chapter_gaps_ok(chapters))


def has_chapters(description):
    """Whether a FINISHED description carries a working chapter list.

    Checked against the rendered text rather than the list it was built from, so
    it also catches a description that was replaced or truncated downstream.
    """
    lines = [l.strip() for l in (description or "").splitlines()]
    stamps = [l for l in lines if re.match(r"^\d?\d:\d\d(:\d\d)?\s+\S", l)]
    return len(stamps) >= MIN_CHAPTERS and stamps[0].startswith(("00:00", "0:00"))


def format_description(hook, chapters, source, hashtags, boilerplate=None):
    """Hook -> chapters -> sources -> channel blurb -> hashtags.

    The shape is the sibling pipeline's build_description, which has been the
    better description on this estate for weeks: a snippet head written for a
    human, an emoji-headed chapter table, and a sources block treated as
    load-bearing rather than optional. What shipped here on 2026-08-21 was six
    lines with a garbled first one.
    """
    boilerplate = BOILERPLATE if boilerplate is None else boilerplate
    parts = [hook.strip(), ""]
    if chapters_ok(chapters):                # <3 -> skip rather than emit a broken block
        parts.append("\u23f1 Chapters")
        parts += [f"{ts} {title}" for ts, title in chapters]
        parts.append("")
    if source:
        parts.append("\U0001f52c Sources")
        parts.append(source)
        parts.append("")
    if boilerplate:
        parts.append(boilerplate.strip())
        parts.append("")
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n".join(parts).strip()[:5000]


# ⚠ The garbled hook published silently on 2026-08-21 — nothing looked at the
# finished text. Mirrors the sibling pipeline's check_description.
def check_description(description, source=""):
    """Problems a human should see BEFORE the upload. Never raises."""
    out = []
    d = description or ""
    first = (d.splitlines() or [""])[0].strip()
    if not first:
        out.append("no hook — the first line is empty")
    if re.match(r"(?i)^\s*chapters?\s*[:\-]", first):
        out.append(f"the hook is a chapter list, not prose: {first!r}")
    if len(first) > SNIPPET_LIMIT:
        out.append(f"search snippet is {len(first)} chars, max {SNIPPET_LIMIT}")
    if "\U0001f52c Sources" not in d:
        out.append("missing the Sources block (the credibility signal)")
    if source and source not in d:
        out.append(f"source {source!r} missing from the description")
    if not has_chapters(d):
        out.append(f"no chapter list (YouTube needs {MIN_CHAPTERS} from 00:00)")
    stamps = [l.strip() for l in d.splitlines()
              if re.match(r"^\d?\d:\d\d(:\d\d)?\s+\S", l.strip())]
    chaps = [(s.split(None, 1)[0], s.split(None, 1)[1]) for s in stamps]
    if len(chaps) >= 2 and not chapter_gaps_ok(chaps):
        times = [_secs(ts) for ts, _ in chaps]
        worst = min(b - a for a, b in zip(times, times[1:]))
        out.append(f"chapters only {worst:.0f}s apart (min {MIN_CHAPTER_GAP:.0f}s) — "
                   f"the beats between them are probably unnarrated: "
                   f"{[t for t, _ in chaps]}")
    return out


def _dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        return float(r.stdout.decode().strip())
    except ValueError:
        return 0.0


def main(argv):
    slug = argv[1]
    ep = f"episodes/{slug}"
    import importlib, beats as bm
    importlib.reload(bm)
    beats = list(bm.BEATS)
    seo = json.load(open(f"{ep}/seo.json"))
    durs = [_dur(f"render/clip_{i:02d}.mp4") if os.path.exists(f"render/clip_{i:02d}.mp4")
            else 0.0 for i in range(len(beats))]
    chaps = chapter_times(beats, durs)
    desc = seo.get("description") or ""
    hook = hook_from(desc)
    source = ""
    m = re.search(r"Sources?:\s*(.+)$", desc, re.M)
    if m:
        source = m.group(1).strip()
    # ⚠ Fall back to the TITLE, never to the model's chapter list. An empty
    # hook is how "Chapters: 1. Grave mystery 2." reached YouTube on
    # 2026-08-21 — there was no prose in the description to take.
    if not hook:
        hook = (seo.get("title") or "").strip()
        print("QA-WARN: the model's description carried no prose hook "
              "(it wrote only a chapter list) — falling back to the title")
    hashtags = hashtags_from_tags(seo.get("tags", []))
    seo["description"] = format_description(hook, chaps, source, hashtags)
    json.dump(seo, open(f"{ep}/seo.json", "w"), indent=2, ensure_ascii=False)
    print(f"description rebuilt: {len(chaps)} chapters, "
          f"{len(hashtags)} hashtags, {len(seo['description'])} chars")
    # Loud, because silence is exactly how guanches-canary published with none
    # and how the garbled hook published on 2026-08-21: the text was never read.
    for v in check_description(seo["description"], source):
        print(f"QA-WARN: description — {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
