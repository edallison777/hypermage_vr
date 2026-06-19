#!/usr/bin/env python3
"""
Generate placeholder SFX for the Godot VR build (F1 — sound + haptics).

Writes small 16-bit mono WAVs to GodotProject/assets/audio/sfx/ using only the
Python standard library (no numpy). These are deliberately simple synthesized
cues so the audio SYSTEM (audio_manager.gd) can be built and felt now; swap them
for real Phase-8 pipeline assets later by dropping files with the same names.

Names map to audio_manager.gd's library keys:
  ui_click, grab, throw, lever_tick, door_rumble (loop), ambient (loop)

Run:  python tools/gen_placeholder_sfx.py
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100          # Hz — match Godot's default audio mix rate, so looping streams
                      # aren't per-stream-resampled (resampling glitches at loop wraps,
                      # producing a click every loop even when the WAV is seamless).
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio" / "sfx"


def _write(name: str, samples: list[float]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.wav"
    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32767)
        frames += struct.pack("<h", v)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    print(f"  wrote {path.relative_to(OUT.parent.parent)}  ({len(samples)} samples, {len(frames)} bytes)")


def _n(seconds: float) -> int:
    return int(seconds * RATE)


def _sine(freq: float, t: float) -> float:
    return math.sin(2.0 * math.pi * freq * t)


def tone(freq: float, dur: float, decay: float = 30.0, amp: float = 0.6) -> list[float]:
    """A single decaying sine — clicks/ticks."""
    out = []
    for i in range(_n(dur)):
        t = i / RATE
        out.append(amp * _sine(freq, t) * math.exp(-decay * t))
    return out


def thunk(dur: float = 0.10) -> list[float]:
    """Low body + a little noise — grabbing/landing."""
    out = []
    for i in range(_n(dur)):
        t = i / RATE
        env = math.exp(-28.0 * t)
        body = 0.7 * _sine(190.0, t) + 0.3 * _sine(95.0, t)
        noise = 0.25 * (random.random() * 2 - 1)
        out.append((body + noise) * env * 0.7)
    return out


def whoosh(dur: float = 0.28) -> list[float]:
    """Band-ish filtered noise with a swell then fade — throwing."""
    out = []
    prev = 0.0
    for i in range(_n(dur)):
        t = i / RATE
        x = (i / _n(dur))
        env = math.sin(math.pi * x)               # swell up then down
        white = random.random() * 2 - 1
        prev = prev * 0.85 + white * 0.15          # crude low-pass -> airy
        out.append(prev * env * 0.8)
    return out


def loop_drone(freqs: list[float], dur: float, amp: float = 0.35,
               tremolo: float = 0.0, fade_out: float = 0.0) -> list[float]:
    """Sum of sines. For a seamless LOOP leave fade_out=0 and pick freqs whose
    sample-period divides the buffer (see ambient). For a ONE-SHOT (door rumble)
    pass fade_out>0 so the tail ramps to zero — otherwise it ends mid-waveform on a
    non-zero sample and clicks."""
    out = []
    total = _n(dur)
    fade_n = _n(fade_out)
    for i in range(total):
        t = i / RATE
        s = sum(_sine(f, t) for f in freqs) / len(freqs)
        if tremolo > 0.0:
            s *= 0.75 + 0.25 * _sine(tremolo, t)
        if fade_n > 0 and i >= total - fade_n:
            s *= (total - i) / fade_n
        out.append(s * amp)
    return out


def arpeggio(freqs: list[float], note: float = 0.09) -> list[float]:
    """Concatenated decaying tones — a little ascending chime for success cues."""
    out: list[float] = []
    for f in freqs:
        out += tone(f, note, decay=16.0, amp=0.5)
    return out


def main() -> None:
    random.seed(1)
    print("Generating placeholder SFX ->", OUT)
    _write("ui_click", tone(1200.0, 0.05, decay=45.0, amp=0.5))
    _write("success", arpeggio([659.25, 830.61, 987.77, 1318.51]))   # E5 G#5 B5 E6
    _write("lever_tick", tone(2000.0, 0.02, decay=120.0, amp=0.45))
    _write("grab", thunk(0.10))
    _write("throw", whoosh(0.28))
    # Loop seamlessly: each freq's period must be a WHOLE number of samples that
    # divides the buffer length exactly (freq = RATE / P, P | total_samples), so the
    # discrete waveform repeats with no step at the wrap point (no periodic click).
    # door_rumble is a one-shot (not looped by audio_manager), so it needn't be exact.
    _write("door_rumble", loop_drone([55.0, 82.0, 110.0], 1.0, amp=0.5, tremolo=7.0, fade_out=0.08))
    # 2.0 s @ 44100 = 88200 samples. Periods (441/294/196/147 samples) divide 88200
    # exactly -> sample-perfect loop. Pitched into a warm, audible pad (pure sub-bass
    # rolls off on PC speakers).
    _write("ambient", loop_drone([100.0, 150.0, 225.0, 300.0], 2.0, amp=0.25))
    print("Done.")


if __name__ == "__main__":
    main()
