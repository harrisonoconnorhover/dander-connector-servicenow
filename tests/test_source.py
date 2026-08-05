"""ServiceNow Table API contract and stateful connector tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
import yaml
from dander.ingestion import load_source_config
from dander.runtime import PipelineRunner, RawSchemaError
from dander.security import OAuth2ClientCredentials, OAuthTokenError
from dander.state import SqliteWatermarkStore
from dander.writer import WriteMode, WritePattern, WriteTarget
from dlt.extract.exceptions import ResourceExtractionError
from dlt.sources.helpers.rest_client.paginators import OffsetPaginator

from dander_connector_servicenow.source import ServiceNowTableSource
from tests.conftest import (
    SyntheticSecrets,
    build_source,
    unexpected_token_request,
)
from tests.simulator import ACCESS_TOKEN, SimulatorServer, create_simulator

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from dander.ingestion import SourceConfig

_CONTRACT = Path(__file__).parents[1] / "contracts" / "servicenow-table-simulator.openapi.yaml"
_CONNECTOR = (
    Path(__file__).parents[1]
    / "src"
    / "dander_connector_servicenow"
    / "templates"
    / "servicenow.example.yaml"
)
_TOKEN_URL = "https://servicenow.example.test/oauth_token.do"
_AUTHORIZATION = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


class CapturingWriter(WritePattern):
    """Capture normalized rows without introducing an external destination."""

    mode = WriteMode.SCD1
    supports_batched_writes = True

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        assert target.table == "servicenow_incidents"
        batch = [dict(record) for record in records]
        for row in batch:
            self.rows[str(row["sys_id"])] = row
        return len(batch)


def _set_scenario(server: SimulatorServer, scenario: str) -> None:
    response = httpx.put(
        f"{server.base_url}/_dander/scenario",
        json={"scenario": scenario},
    )
    response.raise_for_status()


def test_tracked_openapi_contract_matches_fastapi_operations() -> None:
    contract = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))
    generated = create_simulator().openapi()
    expected = {
        (path, method, operation["operationId"])
        for path, methods in contract["paths"].items()
        for method, operation in methods.items()
        if method != "parameters"
    }
    operation_ids = {item[2] for item in expected}
    actual = {
        (path, method, operation["operationId"])
        for path, methods in generated["paths"].items()
        for method, operation in methods.items()
        if method != "parameters" and operation["operationId"] in operation_ids
    }

    assert actual == expected
    assert operation_ids == {
        "issueAccessToken",
        "listIncidents",
        "createIncident",
        "updateIncident",
        "deleteIncident",
        "setScenario",
        "resetSimulator",
    }


def test_example_connector_is_read_only_stable_and_primitive() -> None:
    config = load_source_config(_CONNECTOR)

    assert config.engine == "servicenow_table"
    assert config.auth_strategy == "oauth2_client_credentials"
    assert config.auth_options["credential_placement"] == "body"
    endpoint = config.endpoints[0]
    assert endpoint.name == "incidents"
    assert endpoint.incremental_cursor is None
    assert endpoint.primary_key == ["sys_id"]
    assert endpoint.data_selector == "result"
    assert endpoint.query_params == {
        "sysparm_display_value": False,
        "sysparm_exclude_reference_link": True,
        "sysparm_fields": (
            "sys_id,number,short_description,description,state,priority,active,opened_at,"
            "resolved_at,closed_at,sys_created_on,sys_updated_on,sys_updated_by"
        ),
        "sysparm_query": "ORDERBYsys_updated_on^ORDERBYsys_id",
    }
    assert all(field.data_type == "STRING" for field in endpoint.raw_schema)

    rest_config = ServiceNowTableSource(
        config,
        OAuth2ClientCredentials(
            SyntheticSecrets(),
            client_id_ref="servicenow-client-id",
            client_secret_ref="servicenow-client-secret",
            token_url=_TOKEN_URL,
            credential_placement="body",
            request_token=unexpected_token_request,
        ),
    ).build_rest_config("incidents")
    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    dlt_endpoint = resource["endpoint"]
    assert isinstance(dlt_endpoint, dict)
    assert isinstance(dlt_endpoint["paginator"], OffsetPaginator)
    assert dlt_endpoint["params"] == endpoint.query_params


def test_reads_multiple_pages_and_replays_stateful_updates(
    simulator_server: SimulatorServer,
    config: SourceConfig,
) -> None:
    source = build_source(config, simulator_server)

    initial = list(source.extract("incidents"))
    created_response = httpx.post(
        f"{simulator_server.base_url}/api/now/table/incident",
        headers=_AUTHORIZATION,
        json={"short_description": "Dander plugin incident", "priority": "2"},
    )
    created_response.raise_for_status()
    created = cast("dict[str, object]", created_response.json()["result"])
    update_response = httpx.patch(
        f"{simulator_server.base_url}/api/now/table/incident/{created['sys_id']}",
        headers=_AUTHORIZATION,
        json={"short_description": "Dander plugin incident updated", "state": "2"},
    )
    update_response.raise_for_status()

    updated = list(source.extract("incidents"))
    replay = list(source.extract("incidents"))
    delete_response = httpx.delete(
        f"{simulator_server.base_url}/api/now/table/incident/{created['sys_id']}",
        headers=_AUTHORIZATION,
    )
    delete_response.raise_for_status()

    assert [row["number"] for row in initial] == [
        "INC0010001",
        "INC0010002",
        "INC0010003",
        "INC0010004",
        "INC0010005",
    ]
    assert len(updated) == 6
    updated_proof = next(row for row in updated if row["sys_id"] == created["sys_id"])
    assert updated_proof["short_description"] == "Dander plugin incident updated"
    assert replay == updated
    snapshot = simulator_server.snapshot()
    assert snapshot["records"] == 5
    assert cast("dict[str, int]", snapshot["requests"])["incidents:0"] == 3


def test_throttling_retries_the_same_page_once(
    simulator_server: SimulatorServer,
    config: SourceConfig,
) -> None:
    _set_scenario(simulator_server, "throttling")

    rows = list(build_source(config, simulator_server).extract("incidents"))

    assert len(rows) == 5
    snapshot = simulator_server.snapshot()
    assert cast("dict[str, int]", snapshot["requests"])["incidents:0"] == 2


def test_expired_credentials_fail_without_exposing_secret(
    simulator_server: SimulatorServer,
    config: SourceConfig,
) -> None:
    _set_scenario(simulator_server, "expired_credentials")

    with pytest.raises(ResourceExtractionError, match="OAuth token request failed") as raised:
        list(build_source(config, simulator_server).extract("incidents"))

    assert "dander-servicenow-secret" not in str(raised.value)
    assert isinstance(raised.value.__cause__, OAuthTokenError)


def test_missing_permissions_fail_before_rows_are_returned(
    simulator_server: SimulatorServer,
    config: SourceConfig,
) -> None:
    _set_scenario(simulator_server, "missing_permissions")

    with pytest.raises(ResourceExtractionError, match="403"):
        list(build_source(config, simulator_server).extract("incidents"))


def test_malformed_record_fails_declared_raw_schema(
    simulator_server: SimulatorServer,
    config: SourceConfig,
    tmp_path: Path,
) -> None:
    _set_scenario(simulator_server, "malformed_record")
    runner = PipelineRunner(
        source=build_source(config, simulator_server, page_size=100),
        writer=CapturingWriter(),
        watermarks=SqliteWatermarkStore(tmp_path / "state.db"),
        project="synthetic-project",
        dataset="raw",
    )

    with pytest.raises(RawSchemaError, match="Scalar field has a structured value"):
        runner.run()


def test_declared_discovery_has_no_network(
    config: SourceConfig,
) -> None:
    source = ServiceNowTableSource(
        config,
        OAuth2ClientCredentials(
            SyntheticSecrets(),
            client_id_ref="servicenow-client-id",
            client_secret_ref="servicenow-client-secret",
            token_url=_TOKEN_URL,
            credential_placement="body",
            request_token=unexpected_token_request,
        ),
    )

    discovered = source.discover()

    assert discovered["incidents"]["incremental_cursor"] is None
