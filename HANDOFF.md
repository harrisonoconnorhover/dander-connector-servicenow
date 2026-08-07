# Morning Handoff

## Finished

- Prepared `dander-connector-servicenow==0.2.2rc1` for Dander `0.7.x` compatibility.
- Kept plugin API v1, the read-only engine, and connector runtime behavior unchanged.
- Updated the lockfile to exercise the candidate against public Dander `0.7.0rc1`.

## Try It

Install the built package outside the checkout, pin `0.2.2rc1`, and run
`dander connector check servicenow` from a generated project with secret references configured.

## Checks

- All 23 tests, Ruff lint/format, strict mypy, and package build passed.
- The lock resolves `dander-platform==0.7.0rc1` with this candidate.

## Decisions

- Widen only the package compatibility boundary from Dander `<0.7` to `<0.8`.
- Preserve plugin API v1 and all connector behavior.

## Remaining

- Run protected checks, publish the candidate, and use it in the isolated portability proof.
- Promote a stable patch only after that proof succeeds.
- Leave the retained project unchanged until its separately reviewed upgrade.

## Review First

- `pyproject.toml`
- `CHANGELOG.md`
- `uv.lock`
