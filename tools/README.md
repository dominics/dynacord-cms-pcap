# Tools

- `usbpcap.py`: minimal reader for USBPcap captures (`LINKTYPE_USBPCAP`), including iso packet descriptors.
- `analyse.py CAPTURE...`: summarises a capture: control requests, iso OUT packet sizes, a frame-by-frame check of the `counter` pattern, feedback values and bulk IN sizes. Takes `.pcap` files; decompress the `.xz` files in `captures/` first.
- `sword/play.py RATE PATTERN`: runs on sword (Windows, with the DYNACORD driver) and plays bit-exact 24-bit test patterns over ASIO. Needs `py -m pip install --user sounddevice numpy`.
- `sword/sword-capture RATE PATTERN`: runs from a Mac or Linux host. Starts USBPcap on sword, runs `play.py`, and fetches the capture into `captures/`.
- `sword/sword-ps SCRIPT.ps1`: runs a local PowerShell script on sword over SSH.

Sword's sshd has no SFTP subsystem, so `scp` needs `-O` (legacy protocol).
