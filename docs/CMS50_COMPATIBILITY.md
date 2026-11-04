# CMS50 family: download compatibility (T-103)

**Scope (psytrap, 2026-10-29):** fiedle400 supports the PO-400, PO-250 and PO-300 only. The CMS50
protocols below are documented for reference and not implemented, except protocol B for the
PO-250 (T-105, v0.5.9: download only, untested on a real PO-250; every device naming itself
CMS50… is still refused). The PO-400's own protocol is in [`PROTOCOL.md`](PROTOCOL.md).

Desk research, 2026-10-29; no device on the project was used. Only stored-recording download is covered (no live
mode, no file formats). Each claim carries its evidence:

- **Src**: OSCAR source, `oscar/SleepLib/loader_plugins/cms50_loader.cpp`, `cms50f37_loader.cpp` and
  `oscar/SleepLib/serialoximeter.cpp` (gitlab.com/CrimsonNape/OSCAR-code, master, fetched 2026-10-29)
- **RE**: static analysis of `archive/bruteforce/SpO2.exe` (SpO2 Assistant, file version 3.1.0.4)
- **Cap**: PO-400 captures and traces in this repo (`analysis/`, `archive/`, `tests/fixtures/`)
- **Wire**: two third-party serial captures of a CMS50F with firmware 3.7, one with SpO2 Assistant
  2.x and one with SpO2 Review (SleepyHead bug #207, 2014; copies and a decoder in
  `archive/capture/cms50f37-2014/`, not in git)
- **Forum**: a forum or blog report (links in §7), not checked by anyone on the project
- **Inferred**: concluded from the above, not seen directly

## 1. Three protocols

| | **A: CMS50 legacy** (OSCAR `cms50_loader`) | **B: CMS50F v3.7** (OSCAR `cms50f37_loader`) | **C: PO-400 / SpO2 Assistant** (`PROTOCOL.md` §1-§5) |
| :--- | :--- | :--- | :--- |
| Link | USB-serial, CP210x `10C4:EA60` in the cable (Src default ID; Forum) | USB-serial `10C4:EA60` in the device, or Bluetooth (`rfcomm` port) (Src) | HID `28E9:028A` (Cap); `SpO2.exe` also scans serial IDs (`PROTOCOL.md` §5, RE) |
| Line | 19200 baud, 8 data bits, odd parity, 1 stop (Src; Wire: SpO2 Review sets exactly this) | 115200 8N1 (Src; Wire) | 64-byte HID reports; 115200 on serial (RE) |
| Request | `F5 F5` = send the recording (Src; Wire: SpO2 Review's only write), `F6 F6 F6` = back to live (Src). The user also has to start "upload" on the device (Src: OSCAR's error text and the comment "Newer CMS50 devices transmit from user input") | 9 bytes: `7D 81 [op] [arg\|80]…`, padded with `80`, **no checksum**, every argument byte has bit 7 **set** (Src `sendCommand`; Wire) | `7D 81 op args` or bare, 7-bit arguments, mod-128 checksum (`PROTOCOL.md` §1) |
| Reply | Byte stream; sync on bytes with bit 7 set (Src `processBytes`) | `[code 00..1F] [high bits] [data\|80]…`, length from a per-code table, no checksum (Src) | `[header ≥ 80] [7-bit data…] [checksum]` (`PROTOCOL.md` §1, §2.2), the opposite bit-7 convention to B |
| Model query | None. OSCAR guesses "CMS50D+" when the recording's start clock is 00:00 (Src) | `A8` → code `02`, two segments, e.g. `CMS50F`, `CMS50I`, `CMS50H` (Src; Wire: `02 80 80 C3 CD D3 B5 B0 C6` = `"CMS50F"` with bit 7 set; `A9` → `03 …` = `"Contec"`) | `81 01` → `F1` `"50F"` (Cap) |
| Hello | `F6 F6 F6` (Src) | `A7`, `A2` → `0C 80` (Src; Wire) | `A7`, `A2` → `F0 70` (Cap) |
| List recordings | None: the device pushes its one recording (Src) | `A3` count (code `0A`), `A4 n` duration (code `08`), `A5 n` start date and time (codes `07`, `12`) (Src; Wire) | `9C 01` → `EC` headers (`PROTOCOL.md` §3.2) |
| Download | Three header trios `F2 hh mm`, then one trio `F0\|x pulse SpO2` per sample until the device goes quiet (Src) | `A6 n` → code `0F` frames with 3 samples each (CMS50F) or code `09` with one sample plus PI (CMS50I) (Src; Wire: about 2700 code-`0F` frames for CMS50F) | `9D 04 01/02` → `ED` subframes (`PROTOCOL.md` §3.5); Manual mode `A0`/`A2`/`A3`/`A6`/`A7` (`PROTOCOL.md` §3.14) |
| Erase | None (Src) | `AE user session` (Src) | `9D 7F` (`PROTOCOL.md` §3.13) |
| Duration unit | One record per trio (Src) | `A4` reports half seconds (CMS50F) or quarter seconds (CMS50I, CMS50H) (Src `duration_divisor`) | Seconds (`PROTOCOL.md` §1 rule 4) |

## 2. Findings

1. **B and C are different protocols** (corrects `PROTOCOL.md` §5 as written for T-101). They share the `7D 81`
   prefix, the `80` padding and the `A7`/`A2` hello, nothing else.
   - *RE*: every call of `SpO2.exe`'s send helper (`0x4bc385`) with a constant opcode sends one of
     `80 81 82 83 8E 8F 90..98 9A 9B 9C 9D 9F A0 A1 A2 A3 A6 A7 BE`. None of B's `A4 A5 A8 A9 AA
     AB AD AE B0 B1 B2` is sent. Its `A2`, `A3` and `A6` share one argument handler (`0x4bc437`,
     `[00|7F] [lo] [hi]`), the Manual-mode block request of `PROTOCOL.md` §3.14, not B's commands. So **SpO2
     Assistant 3.1.0.4 cannot download a protocol-B device** (inferred from the call sites).
     *Wire*: the **older SpO2 Assistant 2.x** (`SpO2.exe` too) does speak B: it downloads a
     CMS50F 3.7 with exactly OSCAR's command sequence (`A7 A2 A8 A9 AA B0`, then `A7 A2 A0 B0 AC
     B3 AD A3 AB A4 A5 AF A7 A2 A6`), and switches the port to 19200 8O1 for a moment on the way,
     without writing anything there. So B was dropped from SpO2 Assistant somewhere between 2.x and
     3.1.0.4.
   - *Src vs Cap*: B expects `0C 80` after the hello and reply codes with bit 7 clear; the PO-400
     answers `F0 70` and every reply header has bit 7 set.
2. **`PROTOCOL.md` §3.12's `A5`/`A6` "serial-stream" commands are B's** "get session start time" and "get session
   data" (Src). `SpO2.exe` never sends `A5`; the PO-400 does not answer either (sweep,
   `archive/bruteforce/sweep_results.dump`).
3. **Whether the PO-400 firmware also understands B is unknown.** The sweep sent only `81 8E 94 9B 9C
   9E A5 A6 A7 AD` with the `7D 81` prefix. A local read-only check on a PO-400 would be `7D 81 A8`
   (model) and `7D 81 A9` (vendor). Never send B's `AE` (erase) or `AA` (listed as
   `FLASH_CLEAR` in `PROTOCOL.md` §2.1).
4. **`fiedle400` cannot misdetect an A or B device as a PO-x00** (inferred from the probe in `PROTOCOL.md` §5): it
   needs a valid `F1` frame after `81 01`. A B device gets C's unlock, which is also B's hello, then
   an opcode B does not list; an A device runs at 19200 8O1 and cannot decode 115200 bytes. Both
   end as "no oximeter found".
5. **OSCAR only opens serial ports** (`QSerialPort`, Src `serialoximeter.cpp`), so it cannot
   download a HID device such as psytrap's PO-400 (inferred from the source).
6. **Two direct PO-300 owner reports contradict each other on protocol.** Neither is checked by
   anyone on the project (Forum):
   - forum-schlafapnoe.de, 2017 (a device owner, "Schnarchlappen"): *"Bei mir ist es ja das
     Contec CMS 50 EW (baugleich Pulox PO-300)"* ("Mine is the Contec CMS 50 EW, structurally
     identical to the Pulox PO-300"). They read it with **SpO2 Assistant**, which would fit
     protocol C -- or an undocumented CMS50EW variant that happens to speak it. CMS50EW is a
     separate, later FCC filing (`2ABOGCMS50EW`) from plain CMS-50E and is not otherwise in
     this matrix.
   - apneaboard.com forum, 2023 (a device owner, "Expat31", bought via Amazon): *"Just the
     Smart device assistant detects the oxymeter, not the SP02 Assistant which is the
     important one."* A second forum member (Jeff8356) explains Smart Device Assistant "was
     released with the newer CMS50F oximeters and also works with the older versions" --
     i.e. protocol B, not C. For this unit, **SpO2 Assistant (protocol C) did not detect the
     device at all.**

   These cannot both be protocol C. Pulox may have shipped more than one OEM hardware revision
   under the "PO-300" name over the years (2017 vs. 2023 units) -- not confirmed, and not
   resolvable without an owner (T-102).
7. **The commonly-cited Pulox/CMS50 model mapping is not actually stated by its sources.** The
   Apnea Board wiki's `Contec_file_import` page (Wiki) lists "Pulox PO-200/300/400/500" as its
   own bullet, parallel to but not mapped onto, its Contec CMS-50 list (which separately includes
   **CMS-50EA**, a model this matrix does not otherwise track). The luke.lol pinout page, often
   cited for a PO-200/300/400 = CMS50D+/E/F/I mapping, makes no such explicit claim when read
   directly -- it covers only the shared USB-serial chip and Mini-USB pinout. **Treat any
   "PO-300 = CMS50E" (or similar) claim as unconfirmed**, including finding 6's CMS50EW lead.
8a. **A PO-300 eBay listing photo shows SpO2 Assistant connected over `COM3` with device name
   `50E(A)`** (eBay.de item 155214698697, "B-WARE Pulsoximeter PULOX PO-300 schwarz", seller
   Novidion -- Pulox's own German distributor, not a third-party reseller; item specifics list
   Brand: CONTEC, corroborating the manufacturer finding below; checked 2026-11-04). Novidion
   being the listing's own seller raises this above an ordinary reused-stock-photo risk, but it
   is still a seller photo, not a device-side observation on this project, so treat it as strong
   but unconfirmed. If accurate, two things follow: (a) **serial, not HID** -- contradicts the
   PO-400-is-HID assumption behind finding 1's "family 1, the PO-400's own" guess for the PO-300,
   consistent instead with protocol A or B's USB-serial link, or protocol C over `SpO2.exe`'s
   serial fallback (`PROTOCOL.md` §5); (b) the device name `50E(A)` lines up with **CMS-50EA**,
   the model finding 7 already flagged as listed separately on the Apnea Board wiki's CMS-50 list
   but untracked in this matrix -- the first piece of evidence anywhere in this project's research
   connecting that specific model to the PO-300.

   **Checked against `SpO2.exe` directly (2026-11-04):** no `"50E"`, `"50EA"`, `"CMS50"` or
   `"CMS-50"` string anywhere in the binary (`strings`, 8-bit and UTF-16LE); the only
   Contec-related strings are the manufacturer name and its email templates. Consistent with
   finding 1's existing conclusion that the model string is the device's own raw `0xF1` reply,
   printed verbatim, not looked up from a client-side table (as `"50F"` is for the PO-400). Does
   not confirm the screenshot, but rules out one way it could be wrong: there is no generic
   placeholder label the software could have shown instead, so a genuine `50E(A)` would have to
   come from an actual session with an actual device.

   **Also checked against the two 2014 serial captures (finding 1's `Wire` source,
   2026-11-04):** no `CMS50E`/`CMS50EA`/`50E` string (bit-7-set encoding, matching how
   `CMS50F` is actually stored there) in either `.spm` file. Expected, not a contradiction --
   those captures are from a CMS50F unit, not any PO-300, so there was never a `50E` reply to
   find; this only confirms the search method works (it does find `CMS50F` and `Contec` exactly
   where finding 1 says), not anything about the PO-300.

   **Web check on "CMS50EA" as its own model, 2026-11-04:** thin, and undermines rather than
   confirms it as a distinct product. No official Contec page, no FCC filing, and no independent
   manual found for `CMS50EA` specifically -- only `CMS50E` (base model) and `CMS50EW` (the
   wireless variant, with its own FCC ID `2ABOGCMS50EW`) have real documentation. The two retail
   listings found under the `CMS50EA` name (an eBay listing, an ibspot.com listing) are both
   dead -- the eBay one now redirects to an unrelated, sold-out CMS50I listing. The only place
   `CMS50EA` is documented as a distinct name at all is the Apnea Board wiki bullet already cited
   in finding 7, with no spec sheet behind it. Best current read: **`CMS50EA` is a minor
   retail/regional SKU suffix of the base `CMS50E` line**, not an independently-specified model
   -- parallel to how `CMS50EW` is `CMS50E` + wireless. That reframes 8a's `50E(A)` screenshot:
   the `(A)` may be a software-shown sub-variant marker on a `CMS50E` base string, not
   necessarily the device naming itself after a separately-documented "CMS50EA" product. Not
   confirmed either way.
8. **"Smart Device Assistant" is a separate, newer program from "SpO2 Assistant"** (Wiki, Forum):
   version 3.1.0.1, index code `01GS4016`, released for post-v3.7 CMS50F/H/I hardware (protocol
   B) that OSCAR cannot import directly. Not the same software RE analysed `archive/bruteforce/SpO2.exe`
   (SpO2 Assistant 3.1.0.4) above; not obtained or analysed by this project.
9. **Protocol B is now vendor-documented, not just reverse-engineered** (2026-11-04). Contec's own
   "Communication Protocol of Pulse Oximeter V7.0" (dated 2010-07-08) is published in a GitHub
   repo named `Contec-CMS50EW`:
   https://github.com/vats28/Contec-CMS50EW/blob/master/Communication%20protocol%20of%20pulse%20oximeter%20V7.0.pdf
   -- its text is garbled by a shifted custom font encoding (every character code +29), not
   corruption; decodes cleanly once accounted for. Every protocol-B fact this matrix had
   previously only inferred from static analysis (`RE`) or a 2014 third-party wire capture
   (`Wire`) matches the document exactly: 115200 8N1; `A3`/`A4`/`A5`/`A6` as segment
   amount/length/start-time/data; `AE` as delete storage; the 9-byte control-command package
   with the unused byte `0x00` adjusted to `0x80` after packing. It adds what wasn't previously
   known: the full reason-code table (`0x00` completed, `0x01` shutdown, `0x02` exchange users,
   `0x03` recording, `0x04` failed delete, `0x05` unsupported, `0xFF` unknown), the real-time
   data package's exact bit layout (signal strength, searching flags, probe-error bit, PI
   validity bit), and device-notice/time-sync semantics.

   **Transport, confirming finding 6's `rfcomm` note:** the document states communication "uses
   the COM port or virtual COM or wireless mode" and that "wireless transmission ignores COM
   port transmission parameters" -- i.e. Bluetooth is presented to the host as a virtual serial
   port (SPP), the same protocol B command set over a different transport, not a separate
   protocol. This is consistent with (a) finding 8a's eBay screenshot, where SpO2 Assistant's
   connection dialog has `USB`/`Bluetooth` checkboxes feeding into the same `Auto`/`Manual COM`
   selector; (b) the PO-300 manual's symbol legend noting Bluetooth support on some units only
   (session note, 2026-11-04); and (c) finding 6's CMS50F-with-Bluetooth protocol-B entry above.

   **Repo name itself is circumstantial evidence for the PO-300.** `Contec-CMS50EW` matches
   finding 6's 2017 forum owner, who identified their PO-300 specifically as a "Contec CMS 50
   EW." Combined with finding 1's existing point that **SpO2 Assistant 2.x speaks protocol B but
   3.1.0.4 does not**, finding 6's two "contradicting" owner reports no longer need two different
   hardware revisions to explain: the 2017 owner (SpO2 Assistant worked) and the 2023 owner
   (SpO2 Assistant failed, needed Smart Device Assistant) could both have the same protocol-B
   hardware, just tested with different app versions years apart. This doesn't retract this
   session's separate Bluetooth-manual-variant or missing-reset-hole findings (T-102) -- those
   remain real, independent evidence of hardware variance -- it just removes them as the *only*
   possible explanation for finding 6.

   Not yet saved into the repo; the GitHub link is the only copy referenced so far.
10. **A real, working implementation confirms V7.0 is what a PULOX device actually speaks --
   specifically the PO-250** (2026-11-04). `kaivol/pulox` (GitHub, archived 2025-03-12; MIT
   licensed) is a Rust CLI, `pulox.exe`, "to interact with pulox pulse oximeters" over a serial
   port (default `COM3`). Its `contec-protocol` crate's own top-level doc comment reads
   "Implements the communication protocol of Contec pulse oximeters (V7.0)" -- naming the exact
   same spec version as finding 9's PDF -- and its `outgoing_package.rs` opcode table matches
   finding 9's command table byte-for-byte (`0x7D` wrapper; `0xA1`.."`0xB2`). The README names a
   real device directly: **"Not supported by PULOX PO-250"** for the `clear-storage` and
   `sync-time` subcommands -- meaning the author built and exercised this against an actual
   PULOX PO-250, not just the spec. This is markedly stronger evidence for the PO-250 than
   finding 1's single secondhand forum report: a working open-source implementation, tested by
   its own author against a named PULOX model, speaking exactly protocol B/V7.0 over serial.
   Does not by itself confirm the PO-300 (the only PULOX model the README names is the PO-250),
   but the project is named generically for "pulox pulse oximeters," not PO-250 specifically,
   consistent with the whole PULOX line sharing this protocol family.
   https://github.com/kaivol/pulox ;
   https://kaivol.github.io/pulox/contec_protocol/index.html
11. **Decision (psytrap, 2026-11-04): working assumption for the PO-300 is protocol B.** Not a
   device confirmation -- psytrap's own words were "I guess Protocol B" -- but a deliberate call
   to make given where the evidence has converged, drawn from three independent sources found in
   this session:
   - The **`Contec-CMS50EW` vendor protocol doc** (finding 9): Contec's own V7.0 spec, hosted in
     a repo named for the model a 2017 forum owner identified their PO-300 as.
   - The **`kaivol/pulox` Rust implementation** (finding 10): working code speaking the same
     V7.0 protocol, confirmed against a real PULOX PO-250 -- not the PO-300 directly, but the
     same PULOX line and the same vendor spec.
   - The **`.spm` serial captures and their originating forum report** (finding 1's `Wire`
     source, SleepyHead bug #207, and finding 6's two PO-300 owner reports): the 2014 capture
     that first let this project reverse-engineer protocol B byte-for-byte, and the forum
     evidence that a real PO-300 owner needed protocol-B software (Smart Device Assistant) to
     connect at all.
   Still open: no PO-300 has been read from directly by anyone on this project. Psytrap's own
   PO-300 (T-102) is the first opportunity to actually confirm this rather than infer it.
## 3. Compatibility matrix

| Model | Pulox name | USB link | Vendor software | Protocol | OSCAR downloads it? | What `fiedle400` would need |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| CMS50D+ | PO-200 (Forum: luke.lol) | Serial cable with CP210x, `10C4:EA60` (Src default ID; Forum) | SpO2 Review (Forum: cpaptalk) | A (Src) | Yes, "CMS50" loader (Src; Forum) | Protocol A: line settings 19200 8O1, a push-style receiver, user starts the upload on the device. No clock in the device (Forum: Pugsy), so no real start time |
| CMS50E | PO-300 (Forum: luke.lol; conflicts with T-098, see PO-300) | Serial cable with CP210x (Forum) | SpO2 Review (inferred: same generation as the D+) | A (Src: "CMS50E/F" label) | Yes, "CMS50" loader (Src) | Protocol A |
| CMS50F, older firmware | unknown | Serial cable, CP210x (inferred) | SpO2 Review or the CD's software (Forum: cpaptalk) | A (Src: "CMS50E/F" label) | Yes, "CMS50" loader (Src) | Protocol A |
| CMS50F, firmware 3.7; CMS50FW | unknown | Plain USB cable, CP210x in the device, `10C4:EA60` (Src; Forum); FW also Bluetooth (Src) | SpO2 Assistant 2.x (Wire; the forum names V2.6.0), not 3.1.0.4 (finding 1). SpO2 Review hangs on it (Wire; Forum) | B (Src; Wire) | Yes, "CMS50F3.7" loader (Src; Forum) | Protocol B: new command set and reply parser over the existing serial backend (its 115200 8N1 already matches) |
| CMS50I, CMS50IW | PO-400 (Forum: luke.lol; does not fit psytrap's PO-400, which is HID and reports `"50F"`, Cap) | As CMS50F 3.7 (Src; Forum) | unknown | B with PI, code `09` (Src) | Yes (Src; Forum) | Protocol B |
| CMS50H | unknown | unknown | unknown | B (Src: model-string check) | Yes (Src) | Protocol B |
| PO-400 (psytrap's) | -- | HID `28E9:028A` (Cap) | SpO2 Assistant 3.1.0.4 (Cap) | C (Cap) | No, HID (finding 5) | Nothing, supported |
| PO-250 | -- | serial, `COM` port, per a working open-source implementation (finding 10) | SpO2 Assistant (T-098: manual, forum); a third-party Rust CLI also exists (finding 10) | **leaning protocol B**: a real, working open-source implementation (`kaivol/pulox`, finding 10) was built and used against a named PULOX PO-250 over serial, speaking protocol B/V7.0 -- stronger evidence than finding 1's single secondhand forum report for protocol C. Not device-confirmed by this project | unknown | Nothing beyond 0036 if protocol C with a scanned USB ID (T-101); B support is T-105, done for download in v0.5.9 (untested on a real PO-250), now vendor-documented (finding 9) and independently implemented (finding 10) |
| PO-300 | CMS50EW, per a 2017 forum owner report (finding 6) and the name of the repo hosting the vendor protocol doc (finding 9); CMS-50EA per an eBay listing photo, unconfirmed (finding 8a) | unknown; non-standard cable (T-098); one eBay listing photo shows `COM3` (finding 8a); Bluetooth as a virtual COM port on some units, per the vendor protocol doc and the PO-300 manual (finding 9) | unknown; conflicting direct reports name both SpO2 Assistant and Smart Device Assistant (finding 6) | **leaning protocol B**: finding 9's vendor protocol doc (hosted in a `Contec-CMS50EW` repo) matches finding 1's protocol B exactly, and resolves finding 6's two "contradicting" owner reports without needing different hardware (SpO2 Assistant 2.x speaks B, 3.1.0.4 doesn't -- finding 1). Still not device-confirmed for any specific PO-300 unit. The PO-300=CMS50E mapping some forums cite is itself unconfirmed (finding 7), though finding 8a's `50E(A)` device name is a lead connecting the PO-300 to the specific CMS-50EA model finding 7 flagged as otherwise untracked | unknown | C: nothing beyond 0036; B: on hold (T-105), now vendor-documented (finding 9); A: not implemented |
| PO-200 | CMS50D+ (Forum: luke.lol) | as CMS50D+ (inferred) | SpO2 Review (inferred) | A (inferred) | Yes if it is a CMS50D+ (inferred) | Protocol A |

## 4. SpO2 Review

Contec's older PC program for protocol-A devices (Forum: cpaptalk, apneaboard wiki).

- **Installer not obtained.** Version 1.2, `spo2setup_gen_1.2.zip` (5.2 MB, 2012, contains
  `SpO2 Review.exe`; Software Informer), was linked from luke.lol (rehmann.co, dead link,
  2026-10-29); version 1.0, `SpO2Setup_Gen_1.0.zip`, from pulseoxstore.com (Forum: cpaptalk;
  the host is gone). No static analysis.
- **Its request is on the wire** (Wire, `COM3_SPo2Review.spm`): `SpO2
  Review.exe` opens the port at 19200 baud, 8 data bits, odd parity, 1 stop bit, writes `F5 F5`
  once and then only waits. That is OSCAR's protocol A request (§1). The CMS50F 3.7 in that
  capture speaks B and never answers, which is the "waiting for data" hang the reporter saw. The
  reply side of A is therefore known from OSCAR only.
- **What is known without it** (Forum: cpaptalk): the user selects the COM port and the model
  ("CMS 50D+") in a pull-down, which fits protocol A having no model query; it needs the CP210x
  driver.

## 5. What adding the other protocols would take

Not planned (scope above). For the record:

- **Protocol B** (CMS50F 3.7, CMS50I, CMS50H, likely PO-300): built for the PO-250 only
  (T-105, v0.5.9, `PROTOCOL_B.md` §7): command module and reply parser, a discovery probe after
  the PO-x00 probe, and a read-only engine that replays the capture in §6. The CMS50 models are
  refused by their `A8` model string; the PO-300 question is T-108.
- **Protocol A** (CMS50D+, CMS50E, older CMS50F): different line settings, no listing (one pushed
  recording), no clock.
- **Protocol C on other models**: the PO-250 and PO-300, built in 0036 (T-101, T-104); waiting for
  an owner (T-102).

## 6. Protocol B on the wire (CMS50F 3.7, 2014 capture)

Decoded from `COM3_SPo2Assistant.spm` (Wire; `archive/capture/cms50f37-2014/`). Every request is
`7D 81 [op] 80 80 80 80 80 80` (user and session index 0). Replies are shown as code, then the data
bytes with bit 7 already restored from the second byte.

| Request | Reply code | Data (bit 7 restored) | Meaning |
| :---: | :---: | :--- | :--- |
| `A7`, `A2` | `0C` | (none) | Hello acknowledged |
| `A8` | `02`, `02` | `00 "CMS50F"`, then `FF 00 20 20 20 20 20` | Model `CMS50F`; the second frame (data[0] ≠ 0) adds only blanks |
| `A9` | `03` | `"Contec" 00` | Vendor |
| `AA` | `04` | `"    DLy"` | User-set device ID (the reporter's name). On the PO-400 `AA` is listed as `FLASH_CLEAR` (`PROTOCOL.md` §2.1): never send it to one |
| `A0` | `06` | `00 07` | Protocol/firmware version, meaning unconfirmed (OSCAR: "get version") |
| `B0` | `11` | `01 01 00 00 00 00 00` | Device info, fields unknown |
| `AC` | `0E` | `01` | OSCAR: "perfusion index available", 0 = yes |
| `B3` | `13`, `14` | blanks; zeros | Unknown |
| `AD` | `10` | `01` | User count: 1 |
| `A3` | `0A` | `00 01` | User 0 has 1 recording |
| `AB` | `05` | `00 "user"` | User 0's name |
| `A4` (session 0) | `08` | `00 00 50 A3 00 00` | Duration `0xA350` = 41,808 half seconds = 20,904 s (5 h 48 min 24 s) |
| `A5` (session 0) | `07`, `12` | `00 00 14 0E 08 03`; `00 00 03 12 30 00` | Start date `20`·`14` = 2014, month 8, day 3; time 03:18:48 |
| `AF` | (none) | | Unknown; no reply |
| `A6` (session 0) | `0F` × 2,734 | e.g. `63 41 63 41 63 41` | Three samples per frame as (SpO2, pulse): 99 %, 65 bpm. The capture ends after 8,202 of the 20,904 samples (280 s into the transfer, about 29 samples/s), so the end-of-download behaviour is not on the wire |

SpO2 Assistant sets 115200 8N1 before the first request, switches to 19200 8O1 and back once in
between without writing anything, and sends `A7` `A2` again right before `A6`, as OSCAR's
`resetDevice()` does.

## 7. Sources (Forum)

- cpaptalk, "CMS 50D+ oximeter on XP": https://www.cpaptalk.com/viewtopic.php?p=669848
- cpaptalk, "CMS-50F and CMS-50i use with SleepyHead": https://www.cpaptalk.com/viewtopic.php?p=998263
- cpaptalk, "how does an oximeter (Contec) hook up to Oscar": https://www.cpaptalk.com/viewtopic/t179448/how-does-an-oximeter-Contec-hook-up-to-Oscarmachine.html
- cpaptalk, "OSCAR doesn't recognize my oxymeter" (PO-250, 2026): https://www.cpaptalk.com/viewtopic.php?t=177946
- luke.lol, "Drivers for Pulox / Contec CMS50D+, CMS50E, CMS50F and CMS50I": https://luke.lol/blog/tech/drivers-pulox-contec-cms50d-cms50e-cms50f-and-cms50i
- luke.lol, "Pinout for CMS50D+, CMS50E, CMS50F and CMS50I (Pulox PO-200, PO-300, PO-400)" (no explicit model mapping, finding 7): https://luke.lol/blog/tech/pinout-for-cms50d-cms50e-cms50f-and-cms50i-pulox-po-200-po-300-po-400/
- Apnea Board wiki, "SpO2 software": https://www.apneaboard.com/wiki/index.php/SpO2_software
- Apnea Board wiki, "Contec file import" (Smart Device Assistant, CMS-50EA, finding 7): https://www.apneaboard.com/wiki/index.php/Contec_file_import
- Apnea Board forum, "Pulox PO-300 oxymètre software" (PO-300 owner, 2023, finding 6): https://www.apneaboard.com/forums/Thread-Pulox-PO-300-oxym%C3%A8tre-software
- forum-schlafapnoe.de, "Fragen zum SpO2 Assistant (Pulox/Contec)" (PO-300/CMS50EW owner, 2017, finding 6): https://forum-schlafapnoe.de/threads/fragen-zum-spo2-assistant-pulox-contec.8989/
- Software Informer, SpO2 1.2: https://spo2.software.informer.com/download/
- SleepyHead bug #207, "New Contec CMS" (CMS50F 3.7; the two serial captures): https://sourceforge.net/p/sleepyhead/bugs/207/
- eBay.de, Novidion listing 155214698697, "B-WARE Pulsoximeter PULOX PO-300 schwarz" (`50E(A)`/`COM3` screenshot, finding 8a): https://www.ebay.de/itm/155214698697
- GitHub, vats28/Contec-CMS50EW, "Communication protocol of pulse oximeter V7.0" (Contec's own spec, 2010-07-08; text uses a shifted custom font encoding, decodes with +29 per character code; finding 9): https://github.com/vats28/Contec-CMS50EW/blob/master/Communication%20protocol%20of%20pulse%20oximeter%20V7.0.pdf
- GitHub, kaivol/pulox (archived), a Rust CLI for PULOX oximeters implementing protocol V7.0, built and used against a named PULOX PO-250 (finding 10): https://github.com/kaivol/pulox ; crate docs: https://kaivol.github.io/pulox/contec_protocol/index.html
