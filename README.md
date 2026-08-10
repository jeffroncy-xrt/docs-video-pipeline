# docs-video-pipeline

> **Portfolio excerpt.** This is a reduced, runnable subset of a private
> production system that renders a narrated documentary video every day,
> unattended, on a memory-constrained host. Script generation, topic selection,
> imagery sourcing and credentials are not included. What is here is the
> timeline, assembly and rendering core, with its tests.

## What the full system does

It plans an episode as a sequence of narrated beats, sources visuals for each,
synthesises a voice track, builds an ffmpeg filter graph with transitions,
renders the episode, and uploads it on a schedule — inside a 1.4 GB memory
ceiling on a host shared with four other services.

## What is in this excerpt

| Module | Responsibility |
|---|---|
| `beats.py` | The narrated beat as the unit of composition |
| `cue_plan.py` | Plans which visual is on screen at which timestamp |
| `xfade_graph.py` | Builds the ffmpeg crossfade filter graph |
| `assemble.py` | Renders the episode |
| `length_gate.py` | Enforces target duration before anything is published |
| `cards.py`, `overlay.py`, `maprender.py` | Title cards, text overlay, map rendering |
| `build_description.py` | Assembles the publish-time description |

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest -q
```

## Decisions worth reading

**A stalled render produces a full-length file.** This is the single most useful
thing in this repo. When a render freezes, the output is not short — it is the
right duration with repeated frames. Every duration-based check passes, and the
video is broken. Freezes have to be detected by comparing successive frames
(PSNR between neighbours collapses toward identical), never by inspecting file
metadata. That cost a day's output before it was understood.

**Never loop a still image into a zoom filter behind a rate-mismatched split.**
An `-loop 1` input feeding a split whose branches consume at different rates
buffers full-resolution frames without bound until the memory ceiling kills the
render. The fix is bounded chunks; the lesson is that ffmpeg filter graphs have
memory characteristics that are not obvious from reading them.

**Render inside a hard ceiling, deliberately.** The unit sets `MemoryMax` and no
`MemoryHigh`, so the render either fits or dies immediately. An earlier
configuration with both limits let a process sit between them, permanently
throttled and never killed, frozen for around ten hours while the supervisor
reported it as healthy.

**Duration is gated before publishing, not after.** `length_gate.py` refuses an
episode that misses its target, because an upstream shortage otherwise produces
a short episode that publishes itself.

## What is not included

Script generation and its prompts, topic selection and research, the imagery
sourcing cascade and its acceptance checks, voice synthesis, thumbnails,
credentials, upload, and the top-level orchestration. Those live in the private
repository this was taken from.
