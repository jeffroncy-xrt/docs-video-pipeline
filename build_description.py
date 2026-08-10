#!/usr/bin/env python3
"""Rebuild an episode's YouTube description AFTER render: hook + timestamped
chapters (from real beat durations) + source citation + hashtags.  Chapters need
timestamps that only exist post-render, so this runs between build_v2 and upload.

    .venv/bin/python build_description.py <slug>
Reads episodes/<slug>/{beats.py, seo.json} + render/clip_NN.mp4 durations;
rewrites seo.json['description'] in place (tags untouched)."""
import os, sys, json, subprocess, re


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


def hashtags_from_tags(tags, n=6):
    out = []
    for t in tags:
        h = "#" + re.sub(r"[^a-z0-9]", "", t.lower())
        if len(h) > 1 and h not in out:
            out.append(h)
        if len(out) >= n:
            break
    return out


def format_description(hook, chapters, source, hashtags):
    parts = [hook.strip(), ""]
    if len(chapters) >= 3:                   # <3 -> skip rather than emit a broken block
        parts.append("Chapters:")
        parts += [f"{ts} {title}" for ts, title in chapters]
        parts.append("")
    if source:
        parts.append(f"Source: {source}")
        parts.append("")
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n".join(parts).strip()


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
    # hook = first 1-2 sentences of the (grounded) LLM description
    hook = " ".join(re.split(r"(?<=[.!?]) ", desc)[:2]).strip()
    source = ""
    m = re.search(r"Sources?:\s*(.+)$", desc)
    if m:
        source = m.group(1).strip()
    hashtags = hashtags_from_tags(seo.get("tags", []))
    seo["description"] = format_description(hook, chaps, source, hashtags)[:5000]
    json.dump(seo, open(f"{ep}/seo.json", "w"), indent=2, ensure_ascii=False)
    print(f"description rebuilt: {len(chaps)} chapters, {len(hashtags)} hashtags")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
