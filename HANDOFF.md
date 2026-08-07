# Morning Handoff

## Finished

- Prepared ServiceNow connector `0.2.1rc1` as a compatibility-only candidate.
- Extended the existing Dander dependency range from `0.5.x` through `0.6.x`.
- Preserved every connector runtime, endpoint, authentication, and manifest contract.
- Updated public release copy and the exact manifest pin example.

## Try It

Run `uv sync --extra dev && uv run pytest`. The locked environment installs public Dander
`0.6.0rc1`; no ServiceNow tenant is required for the simulator-backed suite.

## Checks

- Ruff lint/format, strict mypy, and all `23` simulator-backed tests passed.
- Wheel and sdist built successfully.
- The wheel installed with public Dander `0.6.0rc1` outside both repositories.
- `git diff --check` passed.

## Decisions

- Keep plugin API v1 and the read-only `servicenow_table` engine unchanged.
- Use one compatibility candidate instead of weakening or bypassing the shared image resolver.

## Remaining

- Merge through protected CI and publish the approved candidate.
- Pin it only in the isolated Salesforce acceptance project.
- Do not alter the retained project from this compatibility patch.

## Review First

- `pyproject.toml`
- `uv.lock`
- `CHANGELOG.md`
