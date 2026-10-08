"""Minimal USBPcap (LINKTYPE_USBPCAP) reader for poking at the Dynacord capture."""
import lzma
import struct
import sys
from dataclasses import dataclass, field


@dataclass
class Urb:
    n: int
    ts: float
    irp_id: int
    info: int  # bit0: 1 = completion (device->host direction of the IRP)
    function: int
    endpoint: int
    transfer: int  # 0 iso, 1 int, 2 ctrl, 3 bulk
    data: bytes
    iso: list = field(default_factory=list)  # (offset, length, status)

    @property
    def completion(self):
        return bool(self.info & 1)


def read(path):
    opener = lzma.open if path.endswith(".xz") else open
    with opener(path, "rb") as f:
        magic = f.read(24)
        n = 0
        while True:
            h = f.read(16)
            if len(h) < 16:
                return
            sec, usec, incl, _ = struct.unpack("<IIII", h)
            d = f.read(incl)
            n += 1
            hl, irp, _status, func, info, _bus, _dev, ep, tt, dlen = struct.unpack("<HQIHBHHBBI", d[:27])
            iso = []
            if tt == 0 and hl > 27:
                _start, npk, _err = struct.unpack("<III", d[27:39])
                for i in range(npk):
                    iso.append(struct.unpack("<III", d[39 + 12 * i:51 + 12 * i]))
            yield Urb(n, sec + usec / 1e6, irp, info, func, ep, tt, d[hl:], iso)


if __name__ == "__main__":
    for u in read(sys.argv[1]):
        if u.n > 60:
            break
        print(u.n, hex(u.endpoint), u.transfer, u.completion, len(u.data), u.iso[:3])
