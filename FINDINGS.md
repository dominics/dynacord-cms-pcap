# Capture analysis: `dynacord.pcap`

12.6 s USBPcap capture of the Windows DYNACORD driver (2.9.95.2) driving a CMS 600-3 (old, Ploytec-based) at 96 kHz. Compared against [mischa85/Ozzy](https://github.com/mischa85/Ozzy) `main` as of 2026-04-04 (Xone:DB4 support).

Reproduce with `tools/usbpcap.py`.

## Summary

- **It is the Ploytec vendor protocol.** Same 'V' / 'I' / GET_CUR / SET_CUR sequence as the Xone devices.
- **Input (device to host) matches Ozzy's Xone format**: bulk, 64-byte bit-sliced frames.
- **Output (host to device) is different**: isochronous with an explicit feedback endpoint, 12 bytes per frame. Ozzy has no isochronous transport. The capture only contains silence, so the output sample encoding is still unknown.

## Descriptors

- VID `0x0562`, PID `0x03eb`, bcdDevice `0x0200`, USB 2.0 high speed
- Strings: "DYNACORD" / "DYNACORD Audio Interface" / "no serial number"
- VID `0x0562` does not appear in the Ploytec macOS driver's device table (Ozzy `.claude/re/ploytec_device_table.md`), so that driver never supported this board.

| Interface | Alt | Endpoint | Type | wMaxPacketSize | bInterval | Use (inferred) |
|---|---|---|---|---|---|---|
| 0 | 1 | 0x02 OUT | iso, async | 156 | 1 (every microframe) | PCM out |
| 0 | 1 | 0x83 IN | bulk | 512 | 4 | MIDI/control in? polled, never completed |
| 0 | 1 | 0x04 OUT | bulk | 512 | 4 | MIDI/control out? unused |
| 1 | 1 | 0x81 IN | iso, async | 64 | 4 (1 ms) | Rate feedback for 0x02 |
| 1 | 1 | 0x86 IN | bulk | 512 | 1 | PCM in |

Xone for comparison: PCM out on 0x05 (bulk or interrupt depending on firmware), PCM in on 0x86, MIDI in on 0x83, MIDI out embedded in the PCM out stream.

## Control sequence (frames 3-38)

| Frames | Setup | Response | Meaning |
|---|---|---|---|
| 3-4 | `c0 56 0000 0000 000f` | `31 01 02` | 'V' firmware version |
| 17-18 | `c0 49 0000 0000 0001` | `32` | 'I' status, wIndex 0 |
| 19-20 | `a2 81 0100 0000 0003` | `00 77 01` | GET_CUR rate = 96000 |
| 23-32 | `22 01 0100 {0086,0002} 0003` + `00 77 01` | - | SET_CUR 96000 x5, alternating ep 0x86 / 0x02 |
| 33-34 | `a2 81 0100 0086 0003` | `00 77 01` | GET_CUR rate on ep 0x86 |
| 35-36 | `c0 49 0000 0000 0001` | `32` | 'I' status again |
| 37-38 | `40 49 0032 0000 0000` | - | 'I' write-back of `0x32` |

Differences from Ozzy: the OUT rate endpoint is 0x02 rather than 0x05, and the write-back value is `0x32` unchanged. Ozzy's `ploytec_confirm_wvalue()` ORs in bit 5, which is already set in `0x32`, so it would produce the same value here.

## PCM in: bulk 0x86

- Completions of 18432 bytes = 288 frames x 64 bytes = 3 ms at 96 kHz.
- Frame layout matches Ozzy's `ploytec_decode_frame()`: data bits in the low nibble of bytes 0x00-0x17 (odd channels) and 0x20-0x37 (even channels). Observed values `fc`-`ff` are consistent with a noise floor around 0 / -1.
- Upper nibbles are always `f` in the data bytes.
- Bytes 0x18-0x1f and 0x38-0x3f are padding except byte **0x1b and 0x3b = `0xce`** in every frame. Meaning unknown (sync marker? MIDI idle?).
- No gaps at 512-byte boundaries: 512 bytes = exactly 8 frames, as with the Xone.

## PCM out: iso 0x02

- Each URB has 24 iso packets (3 ms). Packets are 144 bytes (12 frames, one microframe at 96 kHz), and occasionally **132 bytes (11 frames)**: 95,511 vs 105 packets.
- That gives **12 bytes per frame**. Xone-style bit slicing needs at least one byte per bit of sample depth (24 for 24-bit), so this is a different encoding: maybe packed 4 ch x 24-bit, 6 ch x 16-bit, or something else.
- **Every byte is zero**: the host was playing silence. Working out the encoding needs a capture of a known signal.

## Feedback: iso 0x81

- 5 iso packets per URB, 3 bytes each.
- Bytes are almost always `0x60` (96 = samples per ms at 96 kHz), and occasionally `0x5f` (95).
- The 95s line up with the device's clock running slightly slow compared with the host. The host responds by sending an 11-frame packet now and then. This is the classic async iso rate-feedback loop. Linux `snd-usb-audio` (`sound/usb/endpoint.c`) has prior art.

## Open questions

1. Output sample encoding and channel count (needs a known-signal capture).
2. How is each 3-byte feedback packet laid out? One count per byte (per-ms or per-subframe), or a single packed value?
3. What is `0xce` at input byte 0x1b / 0x3b?
4. Behaviour at 44.1 / 48 / 88.2 kHz: packet sizes, feedback values, the SET_CUR sequence.
5. Do 0x83 / 0x04 carry MIDI or control? The CMS may not expose MIDI at all.
6. Stream start and stop: the capture begins with streaming already set up (SET_INTERFACE is not visible).
