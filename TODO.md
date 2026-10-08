# TODO

Goal: Linux and macOS drivers for the old (Ploytec-based) Dynacord CMS 600-3, built on a fork of [mischa85/Ozzy](https://github.com/mischa85/Ozzy). Findings so far: [FINDINGS.md](FINDINGS.md).

## Reverse engineering

- [x] Decode descriptors and the control sequence in `dynacord.pcap`
- [x] Compare input/output stream framing against Ozzy's Xone implementation
- [x] Capture known test signals on sword (`tools/sword/sword-capture`)
  - [x] Walking bit on output at 96 kHz
  - [x] Counter pattern at 44.1 / 48 / 96 kHz (also captures the rate-change sequence)
  - [ ] Plug-in from cold
  - [x] A known signal into the mixer's inputs, to confirm the input channel mapping. Done on dominic-macbook with `ploytec-play`'s input meter instead: USB in 1-2 = master L/R, 3 = AUX, 4 = MON (see FINDINGS)
  - [ ] Ask ASIO which other sample rates it supports (88.2 kHz?)
- [x] Work out the output encoding: plain S24_3LE, 4 channels
- [x] Decode the feedback packet format on 0x81: sliding window of per-ms frame counts
- [ ] Identify `0xce` at input bytes 0x1b / 0x3b
- [ ] Capture MIDI in/out and "SystemCtrl" traffic on 0x83 / 0x04
- [x] Find out whether the CMS can route USB playback back into USB record (a loopback for automated driver tests): yes, USB out -> stereo inputs 5-6 / 7-8 -> master -> USB in 1-2

## Fork

- [x] Rename fork `dominics/snd-xonedb4` to [`dominics/Ozzy`](https://github.com/dominics/Ozzy) and reset `main` to upstream. The 2024 work is on `dynacord-cms`, and the old `main` is on `archive/snd-xonedb4-main`.

## Drivers

- [x] Spec and plan for a userspace libusb output prototype
- [x] `ploytec-play` written on [dominics/Ozzy `dynacord-cms600`](https://github.com/dominics/Ozzy/tree/dynacord-cms600) (`userspace/ploytec-play/`): tone/WAV to the 4 USB outputs, feedback-paced iso output. Unit tests pass, and its packet pacing matches the Windows driver's captures frame for frame.
- [x] Hardware run on dominic-macbook (mixer moved from sword, power-cycled with the cable in):
  - [x] `ploytec-play --rate R --seconds 5` at 44100 / 48000 / 96000 (init and streaming start). Enumerates and streams without any reset or re-enumeration.
  - [x] 5 min per rate on all channels: underruns=0, iso_err=0, no halts (with 32 OUT transfers, see below)
  - [x] Ctrl-C exits cleanly and a re-run works
  - [x] Pulling the cable exits with the "unplugged?" message, and shuts down without stuck transfers
  - [x] Listen: a tone on each channel comes out of the USB return, clean and stable. Channels 1 and 3 are left, 2 and 4 are right.
  - [x] Find out whether the mixer can route USB 3-4 separately from 1-2: yes, they arrive on their own channel strips (stereo inputs 5-6 and 7-8), which is why both pairs reached the same master/headphone mix
- Finding: **the firmware halts all streaming (feedback and PCM in included) when its OUT buffer runs dry**, and the host sees no error. macOS libusb completions stall for 10-36 ms at a time. 4 OUT transfers (12 ms) halted within seconds, and 16 (48 ms) halted twice in 15 min. 32 (96 ms) ran 15 min clean. `ploytec-play` now exits when feedback goes silent for 1 s.
- [x] Input meter in `ploytec-play` ([2c5a67d](https://github.com/dominics/Ozzy/commit/2c5a67d)): decodes bulk IN with Ozzy's `ploytec_decode_frame()` and prints per-second peaks in dBFS; no misaligned frames on hardware
- [x] A low-latency driver can't use a 96 ms queue: find where the stalls come from ([cfb66c6](https://github.com/dominics/Ozzy/commit/cfb66c6)). They are process-wide scheduling stalls of up to 25 ms, not USB. A time-constraint policy on libusb's darwin thread and our event thread brings the worst gap to 4.5 ms. 12 ms ran clean on all rates, and the default is now 8 transfers (24 ms). A HAL driver's IO thread will already have this policy from Core Audio.
- [ ] Deferred review minors: stale replay after an iso ERROR; count empty/short feedback packets; check the 'I' reply length; check allocations
- [ ] Port output to Ozzy's Linux ALSA module
- [ ] Input (0x86), macOS HAL backend, MIDI / SystemCtrl
