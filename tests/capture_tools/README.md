# Capture tools used by the tests

Copies of the reverse-engineering decoders from `archive/capture/` (which is git-ignored),
kept here so the regression tests run on a fresh clone and in CI.

- `decode_pcap.py`: decodes USB HID traffic from `.pcap` / `.pcapng` captures (used by `test_pcap_decoder.py`).
  Differs from the archive copy in two places: legacy pcap byte order is detected correctly, and the
  `fiedle400` import no longer fails silently.
- `decode_spo2.py`: reference `.SpO2` reader (used by `test_export_spo2.py` for round-trip checks).

Both still run as standalone scripts, e.g. `python3 tests/capture_tools/decode_pcap.py analysis/bum400_20260906_100516.pcap`.

`record_exchange.py` is different: it talks to a real device (read-only, destructive commands are refused)
and writes the CLI's command/reply traffic as a trace that `tests/hwsim.py` can replay.
`--probe-firmware` and `--probe-offsets` add the read-only questions the normal flows never ask (see CHANGELOG.md, findings T4 and T6).
The committed recording is `tests/fixtures/cli-exchange.trace.json`.
