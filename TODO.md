# TODO

Goal: Linux and macOS drivers for the old (Ploytec-based) Dynacord CMS 600-3, built on a fork of [mischa85/Ozzy](https://github.com/mischa85/Ozzy). Findings so far: [FINDINGS.md](FINDINGS.md).

## Reverse engineering

- [x] Decode descriptors and the control sequence in `dynacord.pcap`
- [x] Compare input/output stream framing against Ozzy's Xone implementation
- [x] Capture known test signals on sword (`tools/sword/sword-capture`)
  - [x] Walking bit on output at 96 kHz
  - [x] Counter pattern at 44.1 / 48 / 96 kHz (also captures the rate-change sequence)
  - [ ] Plug-in from cold
  - [ ] A known signal into the mixer's inputs, to confirm the input channel mapping
  - [ ] Ask ASIO which other sample rates it supports (88.2 kHz?)
- [x] Work out the output encoding: plain S24_3LE, 4 channels
- [x] Decode the feedback packet format on 0x81: sliding window of per-ms frame counts
- [ ] Identify `0xce` at input bytes 0x1b / 0x3b
- [ ] Capture MIDI in/out and "SystemCtrl" traffic on 0x83 / 0x04
- [ ] Find out whether the CMS can route USB playback back into USB record (a loopback for automated driver tests); otherwise patch a cable from an output to a channel input

## Fork

- [x] Rename fork `dominics/snd-xonedb4` to [`dominics/Ozzy`](https://github.com/dominics/Ozzy) and reset `main` to upstream. The 2024 work is on `dynacord-cms`, and the old `main` is on `archive/snd-xonedb4-main`.

## Drivers

- [ ] Brainstorm, spec and plan (after the RE above)
