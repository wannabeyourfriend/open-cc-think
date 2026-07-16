# H1b instance and environment management

This collection borrows management conventions from the official
[Terminal-Bench 2](https://github.com/harbor-framework/terminal-bench-2) and
[SWE-bench](https://github.com/swe-bench/SWE-bench) repositories without using their evaluation
tasks as gathering data.

## Adopted conventions

- A stable task ID identifies the problem; a separate instance ID appends the fresh replicate.
- One run ID names the entire collection and owns its progress, logs, and results.
- Task instructions, environment state, oracle repair, and tests are logically separate.
- Every environment has a content fingerprint and is reset before each instance.
- The oracle repair is validated before live model collection.
- Agent and verifier outcomes remain separate: `apply_patch` is the terminal prediction action, and
  the deterministic verifier runs outside any subsequent model decision. Visible text does not
  override test results.
- Environment capabilities are explicit. The H1b coding environment has zero GPUs, no internet,
  no host filesystem, no shell, and a bounded eight-step agent loop.
- Build/run logs and final evaluation records are stored separately and remain restartable.

## Deliberate differences

Terminal-Bench 2 uses container images and SWE-bench uses Docker evaluation images because their
tasks execute arbitrary repository code. H1b's first gathering pass uses a smaller exact-repair
environment implemented as an in-memory file map with deterministic verifier predicates. This keeps
the task loop reproducible on macOS and ensures the model cannot execute arbitrary code.

The manifest records both reference URLs, but `terminal_bench_included` remains false. Terminal-Bench
2 stays reserved for held-out production evaluation.

Sonnet 5 adaptive thinking may legitimately omit a reasoning block on a low-complexity decision.
Such a turn is retained as an unsigned, censored observation. Only signed steps are replayed; the
full trajectory remains quarantined in ATIF when any original decision lacks a strong recovery.
