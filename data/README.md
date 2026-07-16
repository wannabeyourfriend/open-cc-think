# Research data

Store small, sanitized result tables and frozen manifests here.

- `results/`: public metric rows, experiment trajectories, and aggregate tables.
- `manifests/`: immutable experiment inputs after protocol freeze.
- `private/` and any `.checkpoints/`: raw replayable signatures and restart state; ignored by git.

Never copy raw signatures into a tracked CSV, JSON, Markdown, notebook, or progress report. Public
rows may include only signature length and SHA-256.
