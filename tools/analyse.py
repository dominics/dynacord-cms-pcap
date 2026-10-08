"""Summarise a Dynacord capture: control requests, iso OUT sizing, counter check, feedback, bulk IN."""
import sys
from collections import Counter

from usbpcap import read


def s24(b):
    v = b[0] | b[1] << 8 | b[2] << 16
    return v - (1 << 24) if v & 0x800000 else v


def main(path):
    urbs = list(read(path))
    t0 = urbs[0].ts
    print(f"== {path.rsplit('/', 1)[-1]}: {len(urbs)} records, {urbs[-1].ts - t0:.2f}s")

    print("-- control (setup / response)")
    pending = {}
    for u in urbs:
        if u.transfer != 2:
            continue
        if not u.completion:
            pending[u.irp_id] = (u.ts - t0, u.data[:8].hex(" "), u.data[8:].hex(" "))
        elif u.irp_id in pending:
            t, setup, out = pending.pop(u.irp_id)
            print(f"   {t:7.3f}  {setup}  {out or u.data.hex(' ')}")

    out_pk = [(u, u.data[o:o + n]) for u in urbs if u.endpoint == 0x02 and not u.completion and u.transfer == 0
              for o, n, _ in u.iso]
    sizes = Counter(len(p) for _, p in out_pk)
    print(f"-- iso OUT 0x02: {len(out_pk)} packets, sizes {dict(sizes)}, packets/URB "
          f"{Counter(len(u.iso) for u in urbs if u.endpoint == 0x02 and not u.completion and u.transfer == 0)}")

    frames = [p[i:i + 12] for _, p in out_pk for i in range(0, len(p), 12)]
    start = next((i for i, f in enumerate(frames) if any(f)), None)
    if start is not None:
        bad = 0
        for i in range(start, len(frames)):
            f = frames[i]
            vals = [s24(f[3 * c:3 * c + 3]) & 0xFFFFFF for c in range(4)]
            if not any(vals):
                break
            n = i - start
            exp = [((n << 2) | c) & 0xFFFFFF for c in range(4)]
            if vals != exp:
                bad += 1
                if bad < 4:
                    print(f"   mismatch at frame {i}: {[hex(v) for v in vals]} expected {[hex(v) for v in exp]}")
        print(f"   counter run from frame {start}: {i - start} frames, {bad} mismatches")

    fb = [u for u in urbs if u.endpoint == 0x81 and u.completion]
    fbp = Counter(u.data[o:o + n].hex() for u in fb for o, n, _ in u.iso)
    print(f"-- iso IN 0x81 feedback: {len(fb)} URBs, iso pkts/URB {Counter(len(u.iso) for u in fb)}, "
          f"packet values {fbp.most_common(5)}")

    bi = [u for u in urbs if u.endpoint == 0x86 and u.completion and u.data]
    if bi:
        print(f"-- bulk IN 0x86: {len(bi)} completions, sizes {Counter(len(u.data) for u in bi).most_common(3)}")
        d = bi[len(bi) // 2].data
        print("   mid-capture first 64B:", d[:64].hex(" "))
    other = Counter((hex(u.endpoint), u.transfer) for u in urbs if u.endpoint not in (0x02, 0x81, 0x86, 0x00, 0x80))
    print("-- other endpoints:", dict(other))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
