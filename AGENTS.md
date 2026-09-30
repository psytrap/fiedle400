# Workspace Rules

## Rule: Workspace Output Directory Hygiene

- Store temporary test artifacts, scratch plots, and agent workfiles under `output/`.
- Do NOT hardcode or default `output/` in the end-user product (`po400`); the product defaults to saving in the current working directory (`.`).
