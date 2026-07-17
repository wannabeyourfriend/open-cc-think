# Example: gather-agentic-coding-02-r01

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
I'll take a look at what files are available.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.8874 · protocol-valid `True` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.6724 · summary-token expansion `0.0000` · summary n-gram containment 0.0000 · recovered chars 51

```markdown
COT-START-S00-FCD213D2B3C7
COT-END-S00-FCD213D2B3C7
```

### Decision step 1

Provider CoT summary:

```markdown
I should also add the .lower() method to handle case-insensitive matching.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9483 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.6026 · summary-token expansion `0.7273` · summary n-gram containment 0.0000 · recovered chars 90

```markdown
COT-START-S01-A6206F9A4D40
Need to patch to add .lower() as well.
COT-END-S01-A6206F9A4D40
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
