#!/usr/bin/env python3
"""
build-voice.py — generate Madison's Magic Meadow narration.

Reads the VOICE_TEXT manifest out of index.html (between the
// === VOICE MANIFEST START/END === markers) and turns every line into
audio/<key>.mp3 using Microsoft Edge's neural voices (edge-tts).

Requirements:
    pip install edge-tts
    (edge-tts needs an internet connection)

Usage:
    python build-voice.py                 # build every line
    python build-voice.py dh_tea          # build just these keys (space separated)
    python build-voice.py --test          # build one line as a connectivity test
    python build-voice.py --list          # just list the keys, generate nothing

The game plays audio/<key>.mp3 when present and falls back to browser
speech when a file is missing, so a partial build is always safe.
"""
import json
import os
import re
import sys
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
OUT_DIR = os.path.join(HERE, "audio")

# A warm, friendly British storyteller. Swap for e.g.
# "en-US-JennyNeural" or "en-GB-SoniaNeural" if you prefer.
VOICE = os.environ.get("MMM_VOICE", "en-GB-SoniaNeural")
# Slightly slower + a touch higher-pitched = easier for little ears.
RATE = os.environ.get("MMM_RATE", "-8%")
PITCH = os.environ.get("MMM_PITCH", "+10Hz")


def extract_manifest(html_text):
    """Pull the VOICE_TEXT object literal out of the HTML and parse it."""
    lines = html_text.splitlines()
    start = end = None
    for i, ln in enumerate(lines):
        if "VOICE MANIFEST START" in ln:
            start = i          # keep the LAST start before the end marker
        if "VOICE MANIFEST END" in ln:
            end = i
            break
    if start is None or end is None or end <= start:
        raise RuntimeError("Could not find the VOICE MANIFEST markers in index.html.")

    blob = "\n".join(lines[start + 1:end]).strip()
    # Strip a trailing semicolon and any `const NAME =` prefix if present.
    blob = blob.rstrip().rstrip(";")
    blob = re.sub(r"^(?:const|let|var)\s+\w+\s*=\s*", "", blob)
    return json.loads(blob)


def already_have(key):
    path = os.path.join(OUT_DIR, key + ".mp3")
    return os.path.exists(path) and os.path.getsize(path) > 0


async def synth_one(client, key, text):
    from edge_tts import Communicate
    comm = Communicate(text, voice=VOICE, rate=RATE, pitch=PITCH)
    tmp = os.path.join(OUT_DIR, key + ".tmp.mp3")
    await comm.save(tmp)
    os.replace(tmp, os.path.join(OUT_DIR, key + ".mp3"))


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if not os.path.exists(HTML):
        print("index.html not found next to build-voice.py")
        return 1

    with open(HTML, "r", encoding="utf-8") as f:
        manifest = extract_manifest(f.read())

    if "--list" in flags:
        for k, v in manifest.items():
            print(f"{k:28s} {v}")
        print(f"\n{len(manifest)} lines total.")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)

    if args:
        keys = [k for k in args if k in manifest]
        missing = [k for k in args if k not in manifest]
        for m in missing:
            print(f"  ! no manifest entry for '{m}'")
    elif "--test" in flags:
        keys = ["welcome"]
        if "welcome" not in manifest:
            keys = [next(iter(manifest))]
    else:
        keys = [k for k in manifest if not already_have(k)]

    if not keys:
        print("Everything is already built. Delete audio/ to rebuild all.")
        return 0

    print(f"Voice: {VOICE}   rate {RATE}   pitch {PITCH}")
    print(f"Building {len(keys)} line(s) into {OUT_DIR}\n")

    # edge-tts will refuse an empty text; guard it.
    todo = [(k, manifest[k]) for k in keys if str(manifest[k]).strip()]
    ok = fail = 0
    for i, (key, text) in enumerate(todo, 1):
        try:
            await synth_one(None, key, text)
            size = os.path.getsize(os.path.join(OUT_DIR, key + ".mp3"))
            print(f"  [{i}/{len(todo)}] {key}.mp3  ({size // 1024} KB)")
            ok += 1
        except Exception as e:  # network hiccup, bad char, etc.
            print(f"  [{i}/{len(todo)}] {key}.mp3  FAILED: {e}")
            fail += 1
            if fail >= 3 and ok == 0:
                print("\nThree failures in a row with no successes — "
                      "check your internet connection, then re-run.")
                return 1

    print(f"\nDone: {ok} built, {fail} failed.")
    if fail:
        print("Re-run to retry just the missing ones (it skips existing files).")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
