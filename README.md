# CTIT Results

This repository stores the results of the
[Clang-Tidy Integration Tester](https://github.com/clang-tidy-infra/CTIT)
(CTIT) and builds the website that shows them:
<https://clang-tidy-infra.github.io/CTIT-results/>.

CTIT commits the files under `runs/` and `timings/` automatically. To test
your own clang-tidy change, follow the instructions in the
[CTIT repository](https://github.com/clang-tidy-infra/CTIT).

## Runs

Each CTIT run writes one JSON file:

```text
runs/YYYY/MM/pr-<number>-<github-run-id>-<attempt>-<architecture>.json
runs/YYYY/MM/main-<check>-<github-run-id>-<attempt>-<architecture>.json
```

The `main-` form is for runs without a pull request, which test a check on
unpatched LLVM. A run file has the run metadata, the status and warnings of
each project, the TP/FP verdicts, and the baseline results if the run had
any. Newer runs also have the wall time of each check per project from
clang-tidy's check profile (`project_runs[i].check_profile`). The run page
compares it with the latest daily check timings.

## Daily check timings

The daily check timings run writes one JSON file:

```text
timings/YYYY/MM/<YYYY-MM-DD>-<github-run-id>-<attempt>-<architecture>.json
```

It has the run metadata, the analysis time of each project, and the wall time
of every clang-tidy check, summed over all test projects (`checks`) and per
project. The per-project times are stored by column:
`project_checks[<project>][i]` is the time of `check_names[i]`, or `null` if
that check did not run on the project.

## Building the site

The site is built by `site/build.py`, which needs only Python. GitHub Pages
rebuilds it on every push to `main` that changes `runs/`, `timings/`, or
`site/`. To build it locally:

```bash
python3 site/build.py --results . --out _site
```

Pass `--ctit <path to a CTIT clone>` to link warnings to the project sources.
The build reads the clone's history of `testers/projects.json`, so it needs
`git` and the full commit history.
