# Dander ServiceNow Connector

First-party ServiceNow Table API connector plugin for
[Dander](https://github.com/harrisonoconnorhover/dander).

> **Alpha:** pin Dander and this plugin exactly. The connector is read-only and supports one
> stably ordered, full-read incident pipeline. It does not propagate source deletions.
> The connector is simulator- and live-validated against a disposable ServiceNow tenant.

## Install

Declare the exact plugin version in `dander.yaml`:

```yaml
plugins:
  servicenow:
    distribution: dander-connector-servicenow
    version: 0.2.1
```

Then install exactly what the manifest declares:

```console
dander plugins install
```

Copy
[`servicenow.example.yaml`](src/dander_connector_servicenow/templates/servicenow.example.yaml)
into the project's `connectors/` directory, replace `INSTANCE`, and keep the OAuth client ID and
secret in Dander's configured secret store.

## Runtime contract

- Engine: `servicenow_table`
- Authentication: Dander core's `oauth2_client_credentials` strategy
- API: ServiceNow Table API
- Endpoint: read-only `incident`
- Publication: Dander's existing SCD1 writer
- Pagination: stable full reads ordered by `(sys_updated_on, sys_id)` with bounded offset pages
- Memory: each response page is consumed through Dander's generic dlt REST runtime
- Optional reads: exact Aggregate API count and one incident lookup by validated `sys_id`
- Connection check: authenticated Aggregate API probe that returns no incident records

With Dander `0.5.x` or `0.6.x`, inspect and check an installed pipeline without running ingestion:

```console
dander connector inspect PIPELINE_ID
dander connector check PIPELINE_ID
```

The ServiceNow OAuth user must have read access to both the incident Table API and its Aggregate
API. Targeted lookups request only the fields declared in the connector schema.

The existing Dander `engine: dlt` ServiceNow configuration remains a compatibility fallback. An
explicitly pinned plugin uses the plugin-owned `servicenow_table` engine without duplicating the
generic REST transport in a system-specific package.

## Development

```console
uv sync --extra dev
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Apache-2.0 licensed.
