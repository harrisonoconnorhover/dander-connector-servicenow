# Morning Handoff

## Finished

- Prepared stable `dander-connector-servicenow==0.2.2` from the accepted candidate.
- Kept plugin API v1, the read-only engine, and connector runtime behavior unchanged.
- Updated only release metadata, the stable example pin, changelog, lockfile, and handoff.

## Try It

Install the built package outside the checkout and pin `0.2.2` in `dander.yaml`.

## Checks

- Isolated Dander `0.7.0rc2` live acceptance passed with 67 incidents and governed output.
- All 23 tests, Ruff lint/format, strict mypy, and package build passed locally.

## Decisions

- Promote the accepted candidate without a functional connector change.
- Preserve plugin API v1 and the Dander `>=0.4,<0.8` compatibility range.

## Remaining

- Merge through protected main, tag `v0.2.2`, and publish through the protected environment.
- Verify the public package resolves with stable Dander `0.7.0` after its publication.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `README.md`
