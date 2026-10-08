# Protocol findings

What we know about the old (Ploytec-based) Dynacord CMS 600-3 USB interface, compared against [mischa85/Ozzy](https://github.com/mischa85/Ozzy) `main` as of 2026-04-04 (Xone:DB4 support).

Sources:

- `dynacord.pcap`: the original 12.6 s capture, Windows driver at 96 kHz, playing silence.
- `captures/*.pcap.xz` (2026-10-08): captures from sword (Windows driver 2.9.95.2, ASIO) playing bit-exact test patterns from `tools/sword/play.py`:
  - `cms-walk-96000`: a single walking bit through all 96 bits of a 4-channel frame, 25 ms per bit.
  - `cms-counter-{44100,48000,96000}`: each channel carries `(frame << 2 | channel) & 0xFFFFFF` for 2 s.

Reproduce with the tools in `tools/`.

## Summary

- **It is the Ploytec vendor protocol.** Same 'V' / 'I' / GET_CUR / SET_CUR sequence as the Xone devices.
- **4 in / 4 out** over ASIO. The WDM driver exposes only the first stereo pair in each direction.
- **Output (host to device) is plain interleaved S24_3LE, 4 channels, 12 bytes per frame**, on an isochronous endpoint. No bit slicing, no embedded MIDI, no padding. Verified bit-exact at 44.1, 48 and 96 kHz.
- **Output rate is driven by an explicit feedback endpoint**: each packet carries the samples consumed in each of the last 3 ms.
- **Input (device to host) uses Ozzy's Xone frame format** (bulk, 64-byte bit-sliced frames). Only bits 0-1 of each slice byte carry data (4 channels); bits 2-7 read as 1.
- **The CMS has USB MIDI** (Windows shows "DYNACORD USB-MIDI" and "DYNACORD SystemCtrl"), presumably on bulk 0x83 IN / 0x04 OUT. Not yet examined.

The manufacturer's spec sheet agrees: "4-in/4-out USB 2.0 interface up to 96 kHz" and "MIDI interface for FX control". The mixer also has physical MIDI in/out DIN sockets. Windows shows two USB-MIDI ports and a SystemCtrl port. A plausible split: one port bridges the DIN sockets, one controls the two internal FX processors (100 factory + 20 user presets), and SystemCtrl does something else. Unconfirmed.

Ozzy today has no isochronous transport and no feedback handling, so output is the main new work. Input looks like a small variation on what Ozzy already does.

## Descriptors

- VID `0x0562`, PID `0x03eb`, bcdDevice `0x0200`, USB 2.0 high speed, device class `0xff`
- Strings: "DYNACORD" / "DYNACORD Audio Interface" / "no serial number"
- VID `0x0562` does not appear in the Ploytec macOS driver's device table (Ozzy `.claude/re/ploytec_device_table.md`), so that driver never supported this board.

| Interface | Alt | Endpoint | Type | wMaxPacketSize | bInterval | Use |
|---|---|---|---|---|---|---|
| 0 | 1 | 0x02 OUT | iso, async | 156 | 1 (every microframe) | PCM out |
| 0 | 1 | 0x83 IN | bulk | 512 | 4 | MIDI in (presumed); always polled, never completed in our captures |
| 0 | 1 | 0x04 OUT | bulk | 512 | 4 | MIDI out (presumed); unused |
| 1 | 1 | 0x81 IN | iso, async | 64 | 4 (1 ms) | Rate feedback for 0x02 |
| 1 | 1 | 0x86 IN | bulk | 512 | 1 | PCM in |

Xone for comparison: PCM out on 0x05 (bulk or interrupt depending on firmware), PCM in on 0x86, MIDI in on 0x83, MIDI out embedded in the PCM out stream.

## Control sequence

When ASIO opens a stream, the Windows driver deconfigures and re-enumerates the device, then sets the rate:

| Setup | Response | Meaning |
|---|---|---|
| `00 09 0000` | - | SET_CONFIGURATION 0 |
| `80 06 ...` | descriptors | GET_DESCRIPTOR device / strings / configuration |
| `c0 56 0000 0000 000f` | `31 01 02` | 'V' firmware version (between the descriptor reads) |
| `00 09 0001` | - | SET_CONFIGURATION 1 |
| `c0 49 0000 0000 0001` | `32` | 'I' status, wIndex 0 |
| `a2 81 0100 0000 0003` | current rate | GET_CUR rate (wIndex 0) |
| `22 01 0100 {0086,0002} 0003` + rate | - | SET_CUR rate x5, alternating ep 0x86 / 0x02, about 10-15 ms apart. The driver also slips a GET_DESCRIPTOR device in after the second one. |
| `a2 81 0100 0086 0003` | new rate | GET_CUR rate on ep 0x86 |
| `c0 49 0000 0000 0001` | `32` | 'I' status again |
| `40 49 0032 0000 0000` | - | 'I' write-back of `0x32` |

- Rates are 3-byte little-endian: `44 ac 00` = 44100, `80 bb 00` = 48000, `00 77 01` = 96000. This matches Ozzy's `ploytec_encode_rate()`.
- No SET_INTERFACE appears in USBPcap captures. Windows selects alternate settings as part of SELECT_CONFIGURATION, and USBPcap doesn't show the resulting requests. A Linux driver must select alt 1 on both interfaces explicitly, as Ozzy already does.
- Differences from Ozzy: the OUT rate endpoint is 0x02 instead of 0x05. The status write-back is `0x32` unchanged; Ozzy's `ploytec_confirm_wvalue()` ORs in bit 5, which is already set, so it produces the same value.

## PCM out: iso 0x02

- **Format: S24_3LE, 4 channels interleaved, 12 bytes per frame.** The walking-bit capture places bit `b` of channel `c` at byte `3c + b / 8`, bit `b % 8`, for all 96 bits, each for exactly 2400 frames (25 ms at 96 kHz).
- The counter captures show every frame, in order, with no insertions or drops: 88200 frames at 44.1 kHz, 96000 at 48 kHz, 192000 at 96 kHz, 0 mismatches.
- Each URB has 24 iso packets, one per microframe (3 ms). Each packet holds a whole number of frames:

| Rate | Frames per microframe | Packet sizes |
|---|---|---|
| 44.1 kHz | 5 or 6 | 60 / 72 bytes |
| 48 kHz | 6 | 72 bytes, with occasional 60 |
| 96 kHz | 12 | 144 bytes, with occasional 132 |

After the final rate change, the number of short packets exactly matches the number of feedback readings below nominal: 18 short packets and 18 readings of 47 at 48 kHz, 31 and 31 readings of 95 at 96 kHz. The host sends one frame fewer each time the device reports a short millisecond. Both rates imply the mixer's clock runs about 90 ppm slow.

- `wMaxPacketSize` 156 = 13 frames, which leaves headroom for the feedback loop to ask for one extra frame at 96 kHz.
- **The firmware halts all streaming when its OUT buffer runs dry.** Feedback packets go empty and bulk PCM in stops, while EP0 keeps answering. The host gets no error, because iso OUT has no handshake. Re-running the init sequence recovers it. On macOS, libusb needed 32 URBs (96 ms) queued to survive completion stalls of 10-36 ms; 4 and 16 both halted.
- Listening test on the headphone monitor (2026-10-09, `ploytec-play` at 48 kHz): channels 1 and 3 come out on the left, 2 and 4 on the right, all clean and stable. So both output pairs reach the same stereo return.

## Feedback: iso 0x81

- 5 iso packets per URB, each 3 bytes, one packet per ms.
- **Each packet is a sliding window of the number of frames the device consumed in each of the last 3 ms, newest first.** Byte 0 of each packet reappears as byte 1 of the next packet and byte 2 of the one after (3741 of 3741 consecutive pairs at 44.1 kHz).
- Typical values: 44.1 kHz gives 44 (`0x2c`) with a 45 roughly every 10 ms (mean of byte 0 = 44.097); 48 kHz gives 48 (`0x30`); 96 kHz gives 96 (`0x60`) with an occasional 95.
- The host matches it one-for-one (see PCM out above). An implementation can sum byte 0 over time and compare it with frames sent.
- This is not the standard USB Audio Class feedback format (10.14 or 16.16 fixed point), so `snd-usb-audio`'s implicit or explicit feedback code can't be reused as-is, though its endpoint scheduling is still useful prior art.

## PCM in: bulk 0x86

- 64-byte frames with the Xone layout: bit slices MSB-first in bytes 0x00-0x17 (first half) and 0x20-0x37 (second half).
- Only **bits 0 and 1** of each slice byte carry data; bits 2-7 always read as 1. That gives 2 channels per half, 4 in total, which fits ASIO's 4 inputs. Ozzy's `ploytec_decode_frame()` already reads bit 0 of each half as channels 1 and 2 and bit 1 as channels 3 and 4, so its channels 1-4 should be correct and channels 5-8 will read as -1.
- Bytes 0x18-0x1f and 0x38-0x3f are zero except bytes **0x1b and 0x3b, always `0xce`**. Meaning unknown.
- URB size scales with rate, always 3 ms worth: 8192 bytes (128 frames) at 44.1 kHz, 9216 (144) at 48 kHz, 18432 (288) at 96 kHz.
- With nothing plugged in, the input is a noise floor around 0 / -1.
- **The 4 USB inputs are mixer buses, not physical inputs** ([owner's manual](https://products.dynacord.com/download/979323), items 33, 36, 48-49 and section 4.6, confirmed on hardware 2026-10-09 with `ploytec-play`'s input meter):

| USB in | Signal | Level set by |
|---|---|---|
| 1-2 | Master L/R, pre master fader (same as the REC SEND RCA outputs) | REC SEND & USB OUT |
| 3 | AUX bus | AUX fader |
| 4 | MON bus | MON fader |

  A mic on channel 1, with the output silent, moved all 4 inputs together: in 1 and 2 equal (centre pan), in 4 1.5 dB lower and in 3 14 dB lower, matching the fader settings. What gets recorded on 3 and 4 is chosen with the channel AUX / MON sends, so a driver just exposes 4 inputs.
- **USB playback loops back into USB record.** USB out 1-2 feeds stereo input 5-6 and out 3-4 feeds stereo input 7-8, which reach the master and so USB in 1-2. A tone on out 1 only read -34 dBFS on in 1 and -51 on in 2. This gives automated driver tests a loopback without patching a cable.

## Windows driver

- On sword: DYNACORD driver 2.9.95.2 (`dyncrd_m.inf`), with ASIO "ASIO for DYNACORD USB-AUDIO" (4 in / 4 out), WDM stereo endpoints, "DYNACORD USB-MIDI" and "DYNACORD SystemCtrl".
- The USB card only enumerated after the mixer was power-cycled with the USB cable already connected. Before that, Windows reported "Device Descriptor Request Failed" (`VID_0000&PID_0002`) on several ports, including after rebooting sword.

## Open questions

1. ~~How do the physical inputs map to the 4 USB input channels?~~ Answered above: master L/R, AUX, MON.
2. What is `0xce` at input bytes 0x1b / 0x3b?
3. MIDI and "SystemCtrl" on 0x83 / 0x04: format, and what SystemCtrl controls.
4. Does the device need the full 5-call SET_CUR dance and the re-enumeration, or is less enough? (Ozzy found 2 calls suffice for the Xone.)
5. How does the device behave when the host underruns or sends a packet of the wrong size?
6. Are 88.2 kHz or other rates supported? ASIO hasn't been asked yet.
