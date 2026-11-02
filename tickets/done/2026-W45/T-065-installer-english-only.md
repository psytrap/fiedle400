# T-065: Installer should only offer English, not German

- **Status:** Done
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

- [x] `[Languages]` reduced to just the `english` entry (or the section
      removed entirely, if Inno Setup defaults to English with none
      specified -- check which reads cleaner).
- [ ] Installer still builds and the existing CI smoke test
      (`build-release.yml`'s `installer-windows` job) still passes.
- [x] Tests pass (`python3 -m unittest discover -s tests -t .`).

---

## Execution Notes

Done 2026-11-02 (cloud, patch 0039). `[Languages]` keeps only the `english` entry, with a
comment. The entry is kept explicit instead of removing the section: Inno Setup would fall back
to English anyway, but the explicit line says it was chosen. Not built here (no Inno Setup in the
cloud): the next `build-release.yml` run (tag or manual "Run workflow") builds and smoke-tests the
installer; with one language Inno Setup skips the language prompt. Full suite OK.
