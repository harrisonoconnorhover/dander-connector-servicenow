# Morning Handoff

## Finished

- Published and live-validated the `0.1.0rc1` ServiceNow plugin candidate.
- Registered the unique `servicenow_table` engine and presentation-safe incident descriptor.
- Packaged the existing read-only connector declaration and raw schema.
- Proved two duplicate-free hosted runs with released leases and a clean Terraform plan.
- Prepared the runtime-identical stable `0.1.0` release metadata.

## Try It

```bash
uv sync --extra dev
uv run pytest
```

## Checks

- `ruff check src tests` and `ruff format --check src tests`: passed.
- `mypy src tests`: passed in strict mode across 8 source files.
- `pytest`: 11 passed.
- Dependency audit: no known vulnerabilities.
- Wheel and source distribution built with the expected contract, workflow, license, and template files.
- Outside-checkout wheel install: stable Dander 0.4.0, entry point, plugin API v1, engine, and template passed.
- Live proof: 67 incidents, 4 assertions, 1 catalog asset, duplicate-free replay, and no drift.

## Decisions

- Reuse Dander's generic REST runtime through a plugin-owned source type.
- Preserve Dander's existing `engine: dlt` ServiceNow path as the compatibility fallback.
- Keep full ordered reads; do not add unsafe timestamp-watermark offset paging.

## Remaining

- Merge the version-only stable release through protected `main` after CI passes.
- Tag and publish `0.1.0` through the trusted release workflow.
- Verify a clean public installation with Dander `0.4.0`.

## Review First

- `src/dander_connector_servicenow/plugin.py`
- `src/dander_connector_servicenow/source.py`
- `src/dander_connector_servicenow/templates/servicenow.example.yaml`
