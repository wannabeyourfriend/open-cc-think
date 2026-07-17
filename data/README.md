# Research data

Released datasets and frozen manifests. Small, sanitized, and versioned; raw run outputs stay in
`experiments/` as the source of record.

## Datasets

- [`cot-recovery/`](cot-recovery/README.md) — signature-backed CoT recovery attempts with exact
  denominators, built from `experiments/h1b-scenario-gathering/`. Start with its
  [datasheet](cot-recovery/DATASHEET.md). Current release: `cot-recovery/v1` (226 decisions, 135
  instances, 8 synthetic controls).

Each dataset is a directory holding one versioned release per subdirectory. Releases are immutable:
a rerun or a metric change gets a new version rather than an edit in place, and every release pins
its contents with `metadata.json` and `CHECKSUMS.sha256`. Builders live in `scripts/` and must be
deterministic, so a rebuild on unchanged inputs reproduces identical checksums.

## Conventions

- `<dataset>/<version>/`: released records as JSONL, one record per line, with a JSON Schema under
  `schema/` that every row validates against.
- `results/`: public metric rows, experiment trajectories, and aggregate tables.
- `manifests/`: immutable experiment inputs after protocol freeze.
- `private/` and any `.checkpoints/`: raw replayable signatures and restart state; ignored by git.

## Hard rules

Never copy raw signatures into a tracked CSV, JSON, Markdown, notebook, or progress report. Public
rows may include only signature length and SHA-256.

Never pool evidence tiers collected under different protocols — pre-blinding artifacts in
`src/artifacts/`, blind live rows, synthetic controls, and curated success sets are separate
populations. Never label a recovered span as ground-truth CoT.
