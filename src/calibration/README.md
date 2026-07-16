# Fixed prompt-calibration set

`fixed-36.json` is generated from official HumanEval, GSM8K-train, and MT-Bench source files by:

```bash
python3 scripts/prepare_calibration_manifest.py
```

The manifest contains prompts and source IDs but no HumanEval canonical solutions or GSM8K worked
solutions. It is calibration data for signature extraction prompts, not a model-capability benchmark.
Do not add Terminal-Bench tasks here: the Terminal-Bench 2.0 run is the held-out production target.

