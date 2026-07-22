# recover-cot

The repository contains one Python implementation, one configuration file per experiment, and one prompt file per experiment.

```bash
uv sync
uv run python recover_cot.py --config config/probe.yaml
uv run python recover_cot.py --config config/reproduce.yaml
uv run python recover_cot.py --config config/optimize.yaml
uv run python recover_cot.py --config config/agentic.yaml
uv run python recover_cot.py --config config/calibrate_corpus.yaml
uv run python recover_cot.py --config config/gather_scenarios.yaml
uv run python recover_cot.py --config config/h1c_long_cot.yaml
```

Copy `.env.example` to `.env.aws` before a provider run. Dataset, artifact, and experiment-result directories are local-only and ignored by Git. Raw signatures remain under ignored `.checkpoints/` or `private/` directories.
