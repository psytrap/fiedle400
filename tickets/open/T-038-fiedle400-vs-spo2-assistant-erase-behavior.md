# T-038: fiedle400 and the vendor SpO2 Assistant differ on auto-erase after download

- **Status:** Open
- **Priority:** Normal
- **Owner:** Either
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`download`)
  - `PROTOCOL.md` §3.13 (`FLASH_CLEAR`)
  - `analysis/bum400_20260906_100516.md` §A.6 (disassembly showing the vendor's auto-erase)

---

## Description & Context

Per `PROTOCOL.md` §3.13 (disassembly `analysis/bum400_20260906_100516.md`
§A.6), the unmodified vendor `SpO2.exe` automatically sends `0x91`..`0x96`
(per-user erase) **after every download**. The vendor capture in this repo
was made with a patched copy of `SpO2.exe` that drops those commands, which
is why no real recording shows them.

`fiedle400 download` does not do this: per `AGENTS.md`'s invariants,
`download` is read-only on the device, and `fiedle400` never erases flash on
its own. So the two tools behave differently after a download: the vendor
app clears the device's stored sessions, `fiedle400` leaves them in place.

This is a known, deliberate divergence, not a bug -- it is recorded here
because nobody had written down *why* fiedle400 and the vendor differ here,
or whether that's the wanted behavior going forward.

What is NOT known:
- Whether any user relies on the vendor's auto-erase to free device storage,
  and whether `fiedle400` not doing that is ever a problem in practice
  (e.g. device fills up because sessions are never cleared automatically).

---

## Criteria

- [ ] A written decision: keep `fiedle400 download` read-only with no
      auto-erase (status quo), or evaluate adding an explicit, opt-in
      erase-after-download flag -- with a reason either way.
- [ ] If an opt-in flag is recommended, file it as its own follow-up ticket
      rather than implementing it here.
- [ ] `README.md` or `PROTOCOL.md` notes the deliberate divergence from the
      vendor tool, if not already clear from §3.13.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
