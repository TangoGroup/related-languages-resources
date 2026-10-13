# Contributing

Thanks for looking. RLR is a research prototype from the Open QA Initiative,
and contributions are welcome: bug reports, data-source loaders, better
similarity measures, UI fixes, and documentation all count.

## Before you start

- Open an issue first for anything larger than a small fix, so we can agree on
  the shape before you spend time on it.
- The non-negotiables in [BRIEF.md](BRIEF.md) section 3 apply to every change:
  every text carries its provenance and license, and absence is reported with
  a reason rather than returned as an empty result.

## Setup

```bash
git clone https://github.com/TangoGroup/related-languages-resources.git
cd related-languages-resources
uv sync --extra dev --extra demo
uv run pre-commit install
```

`./run check` (or `just check`) runs the same lint, typecheck, and test gate
as CI: `ruff check`, `ruff format --check`, `mypy` (strict), and `pytest`.

## Working agreements

- Tests never touch the network. Fixtures live under `tests/fixtures`; add to
  them rather than reaching for live data.
- A stage that cannot deliver returns `Unavailable` with a reason. Do not
  return plausible fake data.
- Keep license data flowing through the pipeline; it is filtered on and
  displayed, never discarded after filtering.
- New verse-indexed datasets implement `rlr.resources.VerseIndexedResource`
  (see `src/rlr/resources/__init__.py`); new MT backends implement
  `rlr.mt.Translator`. Either can be added without touching the pipeline.

## Pull requests

- One topic per pull request, with tests for behaviour changes.
- Describe what changed and why; link the issue if there is one.
- CI must be green. The pre-commit hooks catch most of it locally.

## Licensing of contributions

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE). Data you add must be redistributable under
its own license and credited in [NOTICE](NOTICE).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
