# Morning Handoff

## Finished

- Published compatibility-only candidate `dander-connector-servicenow==0.2.1rc1`.
- Verified it installs with public `dander-platform==0.6.0rc1` in a source-free shared image.
- Deployed that image only to the isolated proof project with the ServiceNow schedule paused.
- Completed one live hosted ServiceNow smoke run without changing connector runtime behavior.
- Left the retained project unchanged.

## Try It

Run `uv sync --extra dev && uv run pytest`; the lock resolves public Dander `0.6.0rc1`.

## Checks

- Candidate lint, format, strict mypy, package build, external installation, and all 23 tests passed.
- Hosted execution `dander-servicenow-incidents-hwhl2` completed successfully.
- Run `1f28fcd398194b92b987e949ed243b3e` succeeded with 67 extracted/affected rows, one model, and four assertions.
- Its lease released, no staging tables remained, and the final shared-platform plan reported `No changes.`

## Decisions

- Keep plugin API v1 and the read-only `servicenow_table` engine unchanged.
- Use `0.2.1rc1` only to widen the supported Dander range; it contains no connector runtime change.
- Keep the isolated schedules paused after acceptance.

## Remaining

- Promote the compatibility candidate only when a stable shared-image release needs it.
- Do not alter the retained project without its separately reviewed upgrade plan.

## Review First

- `pyproject.toml`
- `CHANGELOG.md`
- `src/dander_connector_servicenow/plugin.py`
