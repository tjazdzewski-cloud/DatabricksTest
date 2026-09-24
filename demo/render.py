"""Turn the recorded cast plus the narration audio into an mp4.

The recording is twenty minutes, most of it waiting for group membership to
propagate. The narration is under three. So each section is cut out of the cast,
its idle time capped, and then stretched or trimmed to the length of the audio
that talks over it. That keeps the picture on the thing being described.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CAST = ROOT / "demo.cast"
WORK = ROOT / "_render"
IDLE_CAP = 0.6


def load_cast() -> tuple[dict, list]:
    lines = CAST.read_text(errors="ignore").splitlines()
    header = json.loads(lines[0])
    events = []
    for line in lines[1:]:
        try:
            event = json.loads(line)
        except Exception:
            continue
        if isinstance(event, list) and len(event) >= 3:
            events.append(event)
    return header, events


def section_bounds(events: list) -> list[tuple[int, int, int]]:
    """(section number, first event index, last event index)."""
    marks = []
    for index, event in enumerate(events):
        if event[1] != "o":
            continue
        found = re.search(r"^(\d)\.\s{2}\S", event[2], re.M)
        if found:
            marks.append((int(found.group(1)), index))
    bounds = []
    for position, (number, start) in enumerate(marks):
        end = marks[position + 1][1] - 1 if position + 1 < len(marks) else len(events) - 1
        bounds.append((number, start, end))
    return bounds


def write_slice(header: dict, events: list, start: int, end: int, path: pathlib.Path) -> float:
    chunk, total = [], 0.0
    for event in events[start : end + 1]:
        interval = min(float(event[0]), IDLE_CAP)
        total += interval
        chunk.append([round(interval, 3), event[1], event[2]])
    with path.open("w") as handle:
        handle.write(json.dumps(header) + "\n")
        for event in chunk:
            handle.write(json.dumps(event) + "\n")
    return total


def duration(path: pathlib.Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def run(*args: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(" ".join(args[:3]) + " -> " + result.stderr.strip()[-400:])


def main() -> int:
    WORK.mkdir(exist_ok=True)
    header, events = load_cast()
    bounds = section_bounds(events)
    print(f"{len(bounds)} sections in the cast")

    parts = []
    for number, start, end in bounds:
        audio = ROOT / "audio" / f"{number:02d}.mp3"
        if not audio.exists():
            print(f"  section {number}: no audio, skipped")
            continue
        want = duration(audio)

        cast_slice = WORK / f"{number:02d}.cast"
        natural = write_slice(header, events, start, end, cast_slice)

        gif = WORK / f"{number:02d}.gif"
        run("agg", "--idle-time-limit", str(IDLE_CAP), "--font-size", "16",
            "--theme", "asciinema", str(cast_slice), str(gif))

        silent = WORK / f"{number:02d}_v.mp4"
        # Play the section at its own pace, then hold the last frame for as long
        # as the narration keeps talking. Stretching a two-tenths-of-a-second
        # slice across twenty seconds loses frames; freezing does not.
        run("ffmpeg", "-y", "-i", str(gif),
            "-vf", "tpad=stop_mode=clone:stop_duration=90,"
                   "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=12",
            "-t", f"{want:.3f}", "-pix_fmt", "yuv420p", "-an", str(silent))

        part = WORK / f"{number:02d}.mp4"
        run("ffmpeg", "-y", "-i", str(silent), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(part))
        parts.append(part)
        print(f"  section {number}: screen {natural:5.1f}s -> narration {want:5.1f}s")

    # The demo prints seven headings; the narration has an eighth that lands the
    # point. Give it the closing frame to sit on.
    closing_audio = ROOT / "audio" / "08.mp3"
    if closing_audio.exists() and parts:
        want = duration(closing_audio)
        last_gif = WORK / f"{bounds[-1][0]:02d}.gif"
        # Seeking to the end of a gif does not work; pull the final frame out as
        # a picture and hold that instead.
        frame = WORK / "08.png"
        run("ffmpeg", "-y", "-i", str(last_gif), "-vf", "reverse,select=eq(n\\,0)",
            "-frames:v", "1", "-update", "1", str(frame))
        still = WORK / "08_v.mp4"
        run("ffmpeg", "-y", "-loop", "1", "-i", str(frame),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=12",
            "-t", f"{want:.3f}", "-pix_fmt", "yuv420p", "-an", str(still))
        closing = WORK / "08.mp4"
        run("ffmpeg", "-y", "-i", str(still), "-i", str(closing_audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(closing))
        parts.append(closing)
        print(f"  section 8: closing frame held for {want:.1f}s")

    listing = WORK / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    final = ROOT / "demo.mp4"
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(final))
    print(f"\nwrote {final.relative_to(ROOT.parent)}  "
          f"{final.stat().st_size // 1024} kB  {duration(final):.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
