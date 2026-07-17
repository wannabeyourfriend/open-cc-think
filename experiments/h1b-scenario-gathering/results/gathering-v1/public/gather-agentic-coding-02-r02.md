# Example: gather-agentic-coding-02-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Normalize a user handle by trimming surrounding whitespace and comparing case-insensitively. Inspect, patch, run tests, and report PASS or FAIL.
```

## Visible answer

```markdown
{"applied": true, "patch_count": 1, "path": "src/handles.py", "verifier": {"checks": {"target_behavior": false, "unrelated_files_unchanged": true}, "passed": false, "tests_run": 1}}
```

Expected: `PASS`

Task success: `False`

## Tool trajectory

- Step 0: `read_file` input `{"path": "src/handles.py"}` → `{"content": "def canonical_handle(value):\n    return value.strip()\n", "path": "src/handles.py"}` (success)
- Step 0: `read_file` input `{"path": "tests/test_handles.py"}` → `{"content": "# canonical_handle('  Alice ') == 'alice'\n# canonical_handle('BOB') == 'bob'\n", "path": "tests/test_handles.py"}` (success)
- Step 1: `apply_patch` input `{"new": "def canonical_handle(value):\n    return value.strip().lower()", "old": "def canonical_handle(value):\n    return value.strip()", "path": "src/handles.py"}` → `{"applied": true, "patch_count": 1, "path": "src/handles.py", "verifier": {"checks": {"target_behavior": false, "unrelated_files_unchanged": true}, "passed": false, "tests_run": 1}}` (success)

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
Let me start by looking at what files we're working with.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9667 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.7436 · summary-token expansion `0.5000` · summary n-gram containment 0.0000 · recovered chars 82

```markdown
COT-START-S00-B21AC080E6BE
Let's inspect the files first.
COT-END-S00-B21AC080E6BE
```

### Decision step 1

Provider CoT summary:

```markdown
I need to modify handles.py to apply lowercase conversion after stripping whitespace.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9405 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.5419 · summary-token expansion `0.6667` · summary n-gram containment 0.0000 · recovered chars 102

```markdown
COT-START-S01-F1837C3E7094
Need to patch handles.py to lowercase after strip.
COT-END-S01-F1837C3E7094
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
