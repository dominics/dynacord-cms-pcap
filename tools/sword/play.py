"""Play bit-exact 24-bit test patterns to the Dynacord over ASIO.

Usage: py play.py RATE PATTERN

Patterns (4 output channels, 24-bit samples):
  walk     96 phases of PHASE_MS each. In phase p, channel p // 24 carries
           the single bit 1 << (p % 24); every other channel is 0.
  counter  channel c carries ((frame << 2) | c) & 0xFFFFFF, so the sample
           order and channel interleave can be checked frame by frame.

Half a second of silence is played before and after each pattern.
"""
import os
import sys

os.environ["SD_ENABLE_ASIO"] = "1"

import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402

CHANNELS = 4
PHASE_MS = 25


def walk(rate):
    phase_len = rate * PHASE_MS // 1000
    out = np.zeros((CHANNELS * 24 * phase_len, CHANNELS), dtype=np.int64)
    for p in range(CHANNELS * 24):
        out[p * phase_len:(p + 1) * phase_len, p // 24] = 1 << (p % 24)
    return out


def counter(rate):
    n = rate * 2
    frames = np.arange(n, dtype=np.int64)[:, None]
    chans = np.arange(CHANNELS, dtype=np.int64)[None, :]
    return ((frames << 2) | chans) & 0xFFFFFF


def main():
    rate, pattern = int(sys.argv[1]), sys.argv[2]
    body = {"walk": walk, "counter": counter}[pattern](rate)
    # Sign-extend 24-bit values, then left-justify into int32 so PortAudio's
    # int32 -> int24 conversion keeps exactly these 24 bits.
    body = np.where(body & 0x800000, body - 0x1000000, body)
    pad = np.zeros((rate // 2, CHANNELS), dtype=np.int64)
    data = (np.concatenate([pad, body, pad]) << 8).astype(np.int32)

    dev = next(i for i, d in enumerate(sd.query_devices())
               if sd.query_hostapis(d["hostapi"])["name"] == "ASIO" and "DYNACORD" in d["name"].upper())
    print(f"device {dev}: {sd.query_devices(dev)['name']} rate={rate} pattern={pattern} frames={len(data)}")
    sd.play(data, samplerate=rate, device=dev, blocking=True, dither_off=True)
    print("done")


if __name__ == "__main__":
    main()
