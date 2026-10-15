# Workspace Rules

## Rule: Workspace Output Directory Hygiene

- Store temporary test artifacts, scratch plots, and agent workfiles under `output/`.
- Do NOT hardcode or default `output/` in the end-user product (`fiedle400`); the product defaults to saving in the current working directory (`.`).

## Rule: Division of Labour — Cloud vs Local

Work on this project is split between two environments. The split is not a
preference; it follows from where the hardware is.

- **Cloud** has read-only access to this folder. It can read all code, but the
  Pulsox PO-400 is physically attached to the local machine only, so the cloud
  can neither run the hardware tests nor observe device behaviour.
- **Local** has the device attached and is the only place hardware work can
  happen.

Therefore:

| Area | Owner | Action |
|---|---|---|
| Product/test code fixes | Cloud | Develops the fix, delivers a numbered patch |
| Hardware layer | Local | Diagnoses **and** fixes directly |
| Applying patches | Local | Inspect, dry-run, apply, verify, commit, report |

"Hardware layer" means device access and permissions (udev rules), running the
hardware suite, driver/backend behaviour, and test-harness problems caused by
real-device quirks — e.g. the libusb backend detaching the kernel usbhid driver,
fixed locally in commit 69bb1bb.

Local does not author product-code fixes: they would diverge from the cloud copy
and conflict on the next patch. Local still diagnoses, reports the mechanism and
recommends a fix — it just does not implement it.

## Rule: Delegation Path

Delegate investigations to the cloud by writing a brief to `handoff/`, then
telling the cloud it is there. Do not spawn local subagents for this.

`handoff/` is tracked in git on purpose. Do NOT use `output/` for anything the
cloud must read — it is gitignored and therefore invisible to a git-based sync.

A brief must carry what the cloud cannot observe for itself:

- the symptom, with the exact command and the observed numbers;
- hardware facts and any measurements taken locally;
- current repo state, including applied-but-uncommitted patches;
- an explicit statement of what is NOT yet known, so the cloud does not
  mistake a hypothesis for a finding;
- what the local side can run on request, and any safety constraints
  (never erase device flash — stored sessions are real data).
