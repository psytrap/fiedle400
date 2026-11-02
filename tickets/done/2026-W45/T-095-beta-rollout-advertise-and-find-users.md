# T-095: Beta rollout -- advertise `fiedle400` and find users

- **Status:** Done
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:** A forum post (`forum-schlafapnoe.de`)

---

## Description & Context

Now that `v0.5.0` is shipped ([T-079](../done/2026-W44/T-079-final-beta-testing-before-phase-2.md)
closed the beta-testing phase), psytrap wants to start advertising
`fiedle400` and finding real users beyond this one device/household.
Details (where to post, what the pitch is, what "success" looks like,
whether this needs anything code-side like a landing page or demo) are
not defined yet -- this ticket is a placeholder to hold the intent until
psytrap fleshes it out.

## Criteria

- [x] Scope defined (what "advertise" means concretely -- forum post?
      README polish? a release announcement? GitHub topics/description?)
- [x] Posted; asks for feedback/bug reports and names what is/isn't tested

## Execution Notes

Done 2026-11-02 (local; the post itself is from 2026-10-28, found and verified against this
ticket afterward).

Scope became: a forum post. psytrap (forum handle "Teebeutel") posted ["Neues PO-400 Download
Tool"](https://forum-schlafapnoe.de/threads/neues-po-400-download-tool.22812/) on
forum-schlafapnoe.de, 2026-10-28 -- verified by fetching the thread directly (it sits behind a
Cloudflare check that a direct `WebFetch` 403s on but the browser pane clears passively).

The post: names the motivation (hates SpO2 Assistant's UI, is a Linux user with only an old
Windows laptop), what the tool does (reads the PO-400, shows the night as a chart), the
download formats (HTML or `.spo2`), platform support (Windows and Linux; macOS built but not
tested), an offer of a debug build to anyone with a PO-250/PO-300 to find out whether that
works, the GitHub link (`github.com/psytrap/fiedle400`), and an explicit ask for feedback and
bug reports. One reaction (user "TBM") by the time this was checked.

This covers the ticket's intent (advertise, find users beyond one household) without any
further code-side work (no landing page or demo was needed). Left open for the project, not
this ticket: watching the thread for replies, and following up if a PO-250/PO-300 owner takes
the offered debug build (that would feed T-102).
