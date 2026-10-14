# CTIT Results

This repository is the public archive of results produced by the
[Clang-Tidy Integration Tester](https://github.com/clang-tidy-infra/CTIT).

Each completed CTIT run writes one JSON file under:

```text
runs/YYYY/MM/pr-<number>-<github-run-id>-<attempt>-<architecture>.json
```

The files are generated automatically by CTIT and contain run metadata,
per-project results, diagnostics, TP/FP verdicts, and optional baseline results.
Newer runs also keep the wall time of each check per project from clang-tidy's
check profile (`project_runs[i].check_profile`), which the run page compares
with the latest daily check timings.

The daily check timings run writes one JSON file under:

```text
timings/YYYY/MM/<YYYY-MM-DD>-<github-run-id>-<attempt>-<architecture>.json
```

These files contain run metadata, the analysis time of each project, and the
wall time of every clang-tidy check, both summed over all test projects
(`checks`) and per project. The per-project times are stored by column: `project_checks[<project>][i]` is the time of `check_names[i]`, or `null` if that check did not run on the project.

The results are published as a static website at
<https://clang-tidy-infra.github.io/CTIT-results/>.

To use CTIT to validate your clang-tidy changes, follow the instructions in the
[CTIT repository](https://github.com/clang-tidy-infra/CTIT).
