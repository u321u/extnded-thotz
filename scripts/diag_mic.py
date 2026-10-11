"""Diagnose which input devices carry real signal (run while speaking).

Uses the callback API: PortAudio's blocking read() is unsupported on the
WDM-KS host, which is where the working Windows mics usually live.
"""
import time

import numpy as np
import sounddevice as sd

DURATION = 2.5


def capture(device, info):
    rate = int(info["default_samplerate"] or 48000)
    chunks = []

    def cb(indata, frames, time_info, status):
        chunks.append(indata.copy())

    with sd.InputStream(device=device, samplerate=rate, channels=1,
                        dtype="float32", callback=cb):
        time.sleep(DURATION)
    if not chunks:
        return None
    return np.concatenate(chunks)[:, 0]


def main():
    print("default input:", sd.default.device[0])
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d["max_input_channels"] == 0:
            continue
        try:
            x = capture(i, d)
        except Exception as exc:
            print(f"{i:>3} {sd.query_hostapis(d['hostapi'])['name']:<20} {d['name'][:45]:<45} OPEN FAILED: {exc}")
            continue
        if x is None or x.size == 0:
            print(f"{i:>3} {sd.query_hostapis(d['hostapi'])['name']:<20} {d['name'][:45]:<45} no frames")
            continue
        peak = float(np.max(np.abs(x)))
        rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
        dbfs = 20 * np.log10(peak) if peak > 0 else -999
        verdict = "SILENT" if peak < 1e-3 else ("LOUD/OK" if peak > 0.02 else "quiet")
        print(f"{i:>3} {sd.query_hostapis(d['hostapi'])['name']:<20} {d['name'][:45]:<45} peak={peak:.5f} ({dbfs:6.1f} dBFS) rms={rms:.5f} -> {verdict}")


if __name__ == "__main__":
    main()
