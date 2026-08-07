# Morning Handoff

## Finished

- Prepared stable `dander-connector-servicenow==0.2.1` from the accepted compatibility candidate.
- Verified it runs with public `dander-platform==0.6.0rc2` in a source-free shared image.
- Completed a fresh live hosted ServiceNow smoke with the schedule paused.
- Kept plugin API v1, the read-only engine, and connector source unchanged.
- Left the retained project unchanged.

## Try It

Install the built package outside the checkout, pin `0.2.1`, and run
`dander connector check servicenow` from a generated project with secret references configured.

## Checks

- Candidate lint, format, strict mypy, package build, external installation, and all 23 tests passed.
- Fresh hosted run `a6c34f0be2ac482dbb10aac68b9a7b28` succeeded on Dander `0.6.0rc2`.
- The run completed ingestion, its governed model/tests, catalog publication, and lease release.
- Ruff, formatting, strict typing, all 23 tests, package build, and external wheel discovery passed.

## Decisions

- Keep plugin API v1 and the read-only `servicenow_table` engine unchanged.
- Stable `0.2.1` widens the supported Dander range without a connector runtime change.
- Keep the isolated schedules paused after acceptance.

## Remaining

- Run protected checks, merge, tag, and publish `0.2.1`.
- Pin the stable connector in Dander `0.6.0`.
- Do not alter the retained project without its separately reviewed upgrade plan.

## Review First

- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
