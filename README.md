# CTIT Results

This repository is the public archive of results produced by the
[Clang-Tidy Integration Tester](https://github.com/clang-tidy-infra/CTIT).

Each completed CTIT run writes one JSON file under:

```text
runs/YYYY/MM/pr-<number>-<github-run-id>-<attempt>-<architecture>.json
```

The files are generated automatically by CTIT and contain run metadata,
per-project results, diagnostics, TP/FP verdicts, and optional baseline results.

To use CTIT to validate your clang-tidy changes, follow the instructions in the
[CTIT repository](https://github.com/clang-tidy-infra/CTIT).
