# T-059: A "coffee/beer" license + funding note -- money for additional test devices

- **Status:** Open (deferred)
- **Priority:** Low
- **Owner:** Either
- **Scope & Relevant Files:**
  - `LICENSE` (does not exist yet -- the repo is public on GitHub with no
    license file at all, found while scoping this ticket)
  - `README.md` (a funding/support section)

---

## Description & Context

psytrap request: "Coffee - Beer license - need money to buy and support
additional devices" -- add a lightweight funding ask (coffee/beer-style),
motivated by wanting to buy and support more PO-400 (and related Contec
device family) hardware for broader testing.

Likely points at the informal **"Beerware" license** convention (Poul-Henning
Kamp's original: do what you want with this, buy the author a beer if you
think it's worth it and you meet in person) or a similar lightweight
permissive license with a funding note attached, rather than a strict
commercial license.

**Found while scoping this:** the repo currently has **no `LICENSE` file at
all**, despite being public (`RELEASE_PLAN.md`'s Ring 3.1, repo made public
2026-W43). That's a separate, pre-existing gap this ticket's work would
also close, not something newly introduced.

**Why more devices matter (ties this to real project gaps, not just a
"support me" ask):** several open tickets are blocked or limited by only
ever having tested against one PO-400 unit -- e.g. `PROTOCOL.md`'s open
question on whether any PO-400 ever reports more than one user/entry
(§3.2, T-039), and T-021's broader `.spo2` decode coverage needing more
real-world sample variety. A second device (or a different Contec model in
the same family) would let some of those actually get resolved instead of
staying "not yet known."

---

## Criteria

- [ ] License decided and a `LICENSE` file added (Beerware-style or
      another permissive license psytrap picks)
- [ ] `README.md` gets a short funding/support section (coffee/beer-style
      ask, with a link -- GitHub Sponsors, Ko-fi, or similar, psytrap's
      choice), explaining the "why" (more hardware -> more decode coverage,
      linking to the specific blocked tickets above where it helps)
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

---

## Execution Notes

<!-- Filled in on completion -->
