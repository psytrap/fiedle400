# T-065: Installer should only offer English, not German

- **Status:** Open (deferred; psytrap, 2026-10-21)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `packaging/windows/fiedle400.iss` (`[Languages]`)

---

## Description & Context

`fiedle400.iss`'s `[Languages]` section currently offers two installer
UI languages:

```
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
```

psytrap wants the installer to be English-only; German should be
dropped. Noticed in passing while testing the T-064 installer-text
fixes (2026-10-21) -- not implemented now, parked for later.

What is NOT known:
- Whether any user actually relies on the German installer UI today
  (no reports either way).

---

## Criteria

- [ ] `[Languages]` reduced to just the `english` entry (or the section
      removed entirely, if Inno Setup defaults to English with none
      specified -- check which reads cleaner).
- [ ] Installer still builds and the existing CI smoke test
      (`build-release.yml`'s `installer-windows` job) still passes.
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

<!-- Filled in on completion -->
