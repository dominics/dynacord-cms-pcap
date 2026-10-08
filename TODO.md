# TODO

Goal: Linux and macOS drivers for the old (Ploytec-based) Dynacord CMS 600-3, built on a fork of [mischa85/Ozzy](https://github.com/mischa85/Ozzy). Findings so far: [FINDINGS.md](FINDINGS.md).

## Reverse engineering

- [x] Decode descriptors and the control sequence in `dynacord.pcap`
- [x] Compare input/output stream framing against Ozzy's Xone implementation
- [ ] Capture known test signals on sword (Windows driver 2.9.95.2 + USBPcap are already installed)
  - [ ] Per-channel impulses or ramps on output, one channel at a time, at 96 kHz
  - [ ] The same at 44.1 / 48 kHz, plus a rate change while running
  - [ ] Stream start/stop, and plug-in from cold (SET_INTERFACE, init order)
  - [ ] A known signal into the mixer's inputs, to confirm the input channel mapping
- [ ] Work out the output encoding (12 bytes/frame) and channel count
- [ ] Decode the feedback packet format on 0x81
- [ ] Identify `0xce` at input bytes 0x1b / 0x3b
- [ ] Find out whether 0x83 / 0x04 are MIDI

## Fork

- [ ] Decide what to do with the existing `dominics/snd-xonedb4` fork (unrelated history to current upstream)

## Drivers

- [ ] Brainstorm, spec and plan (after the RE above)
