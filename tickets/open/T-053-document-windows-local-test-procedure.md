# T-053: Document the local Windows test-execution procedure

- **Status:** Open (deferred)
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `RELEASE_PLAN.md` (§6 runbook, G5/G6 gates)
  - `README.md` / a new `WINDOWS_TESTING.md`
  - `~/.ssh/fiedle400_win_ed25519` (+ `.pub`), `~/.ssh/config`
  - `tickets/open/T-047-release-v0-4.md` (consumer of this procedure)

---

## Description & Context

T-047's Windows leg (G5/G6) needs to be run on a separate physical Windows
machine, reached from this Linux machine over SSH. Setting this up from
scratch this session (2026-10-21) surfaced enough undocumented steps and
machine quirks that it's worth writing down once, rather than
rediscovering it on every future release cycle:

- **Access:** Windows host `192.168.2.165`, user `mik`, OpenSSH server
  already running there. Key: `~/.ssh/fiedle400_win_ed25519` (renamed this
  session from `po400_win_ed25519`; its pub-key comment is still the old
  `po400-windows-temp` and hasn't been updated). No `~/.ssh/config` entry
  exists for this host yet -- connections so far specify `-i` by hand.
- **Shell quirks:** the SSH session lands in `cmd.exe` (German locale --
  error text comes back in German), not PowerShell or a POSIX shell.
  Command chaining needs `&`/`&&` (cmd syntax), not `;`. Invoking
  PowerShell needs `powershell -Command "..."` explicitly.
- **Machine is old/minimal:** no `git`, no `winget`, no Chocolatey. Only
  Python 3.5-32 and 3.8-32 installed (via the `py` launcher), both
  32-bit, on a 64-bit OS. `Invoke-WebRequest` fails outright
  (`SSL/TLS-Kanal`) unless `[Net.ServicePointManager]::SecurityProtocol`
  is forced to `Tls12` first -- the machine's default .NET doesn't
  negotiate TLS 1.2 on its own.
- **Git was installed this session** (2026-10-21, psytrap approved):
  downloaded `Git-2.47.1-64-bit.exe` from the official
  `git-for-windows/git` GitHub releases (with the TLS1.2 workaround
  above) and ran `/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS
  /RESTARTAPPLICATIONS`. `where git` confirms it's now on `PATH` for new
  SSH sessions (`C:\Program Files\Git\cmd\git.exe`).
- **The project checkout is NOT a git repository.** `C:\Users\mik\po400`
  exists (found via `where /r C:\Users\mik fiedle400.spec`) and contains
  `fiedle400.spec` plus two real `.spo2` recordings from 2026-09-30, but
  `git status` there fails with `fatal: not a git repository` -- it's a
  loose file copy, not a clone. This still needs to be turned into (or
  replaced by) a real clone of `https://github.com/psytrap/fiedle400.git`
  before G5/G6 can run against current `HEAD` -- not done yet as of this
  ticket's creation.
- **Not yet known:** which Python (3.5-32 vs 3.8-32) the project actually
  needs/uses on this machine, whether either has `pip`/a working `venv`,
  whether PyInstaller is installable here at all (no internet proxy
  issues beyond the TLS one encountered so far), and whether the two
  existing `.spo2` files there are worth keeping or are stale scratch
  output.

## Why this ticket exists

So that T-047 (and every future release cycle) can skip straight to
"clone, build, run tests" on Windows instead of re-deriving SSH access,
shell quirks, and a missing-toolchain workaround from nothing each time.

---

## Criteria

- [ ] `~/.ssh/config` gets a `Host` entry for the Windows machine (alias,
      `IdentityFile fiedle400_win_ed25519`, the right `User`) so future
      sessions can just `ssh <alias>`
- [ ] Pub-key comment updated from `po400-windows-temp` to something
      matching the renamed key (cosmetic, but misleading as-is)
- [ ] `C:\Users\mik\po400` turned into a real clone of `origin` (or
      clearly documented as intentionally not one, with the loose files'
      disposition decided)
- [ ] A short runbook written down (in `RELEASE_PLAN.md` or a new
      `WINDOWS_TESTING.md`) covering: SSH access, shell quirks (cmd vs
      PowerShell, chaining), which Python/venv to use, the TLS1.2
      workaround for any future `Invoke-WebRequest`, and the build +
      `FIEDLE400_LIVE=1` test commands for the `hid` backend
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
