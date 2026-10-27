# T-091: Make "flush before command" an actual synchronization point, not a racy snapshot

- **Status:** Open
- **Priority:** Normal
- **Owner:** Local
- **Scope & Relevant Files:**
  - `fiedle400/engine/device.py` (`_flush_before_command()`, done in
    [T-090](../done/2026-W44/T-090-unify-flush-before-command-helper.md);
    the T-088 background reader thread/queue machinery: `_reader_loop`,
    `_report_queue`, `_dequeue_report`)
- **Depends on:** [T-090](../done/2026-W44/T-090-unify-flush-before-command-helper.md)
  (unify the call sites first, then fix the one helper, not nine copies --
  done 2026-10-27)

---

## Description & Context

Identified during T-089: the flush idiom (`while self._dequeue_report():
pass`) is a **snapshot-and-drain**, not a true synchronization point. Before
T-088's background reader thread existed, the caller was the fd's only
reader, so "I drained it until empty" really meant "nothing more is coming
unless I write a new command" -- draining was safe because nothing else
could enqueue anything concurrently.

With the T-088 background reader thread now continuously filling
`_report_queue` from a second thread, the flush loop can observe "empty" at
the exact instant the reader thread is mid-`put()`: whatever it enqueues
right after that observation survives the flush and sits in the queue when
the new command's reply starts arriving, where it can be misread as part of
that reply.

This ticket is the harder half T-090 explicitly does not attempt: make the
flush step actually correct against a concurrently-filling queue, not just
textually unified. psytrap asked for the implementation options to be
weighed here rather than committing to the first idea (a watermark) before
comparing it to the alternatives.

## Implementation options to evaluate

1. **Watermark / generation counter.** Before writing the new command,
   record the queue's current size (or a monotonically increasing counter
   bumped once per `put()` in `_reader_loop`). Anything already queued at
   that mark is stale; only reports enqueued *after* the mark belong to the
   new transaction. Needs the reader thread to tag each queued item (or the
   queue to expose a cheap, race-free "count enqueued so far") rather than
   relying on `Queue.qsize()`, which is a snapshot with its own race.
2. **Pause-drain-resume.** Briefly stop the background reader thread (the
   stop/join machinery already exists for `close()`) around the
   flush-then-write window, so nothing can enqueue until the new command is
   already in flight. Simple to reason about, but adds thread start/stop
   latency to every command and reintroduces a tiny window where reports
   arriving at the fd queue up ungathered until the thread restarts (not
   lost, just delayed -- needs checking that this delay is harmless).
3. **Quiet-period drain (what `_erase_status()` now does, T-089).** Keep
   draining until a short quiet period passes with nothing new, rather than
   stopping at the first empty check. Cheaper than a true watermark, but
   not airtight: a report that happens to arrive just inside the quiet
   window from the *previous* transaction is still indistinguishable from
   one from the new transaction with this approach alone.
4. **Per-transaction reply tagging**, if the protocol supports it reliably:
   have `wait_for_packet()` (or a successor) filter not just by
   `packet_type` but by some transaction marker reflected in the reply,
   making stale-vs-fresh unambiguous without needing to flush perfectly at
   all. Likely blocked on whether the PO-400's reply frames carry anything
   suitable for this (needs protocol review, may not exist).

Pick one (or a combination), document why the others were rejected for this
protocol/hardware, implement it in the one place T-090 leaves behind, and
validate it actually closes the race rather than just moving it.

## Criteria

- [ ] Compare the options above against this protocol's real constraints
      and pick one, with reasoning recorded here
- [ ] Implement it in `_flush_before_command()` (post-T-090)
- [ ] Some evidence the race is actually closed, not just less likely --
      e.g. a stress test that writes commands back-to-back while the
      background reader thread is active and checks replies never cross
      transactions
- [ ] Real-hardware validation (`sessions`, `read-time`, `info`, a full
      download, a wizard erase) after the change
- [ ] Tests pass (`python3 -m unittest discover -s tests -t .`)

## Execution Notes

<!-- Filled in on completion -->
