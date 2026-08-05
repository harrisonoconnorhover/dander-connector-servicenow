"""Shared fixtures for the ServiceNow plugin contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from dander.ingestion import OffsetPagination, load_source_config
from dander.security import AuthStrategy, OAuth2ClientCredentials

from dander_connector_servicenow.source import ServiceNowTableSource
from tests.simulator import CLIENT_ID, CLIENT_SECRET, SimulatorServer

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from dander.ingestion import SourceConfig

_TOKEN_URL = "https://servicenow.example.test/oauth_token.do"


class FakeAuth(AuthStrategy):
    """Apply a synthetic header for factory-only construction tests."""

    def __init__(self) -> None:
        pass

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = "Bearer synthetic"
        return request


@pytest.fixture
def auth() -> AuthStrategy:
    return FakeAuth()


class SyntheticSecrets:
    """Resolve only the two synthetic references used by the test connector."""

    def get_secret(self, reference: str) -> str:
        return {
            "servicenow-client-id": CLIENT_ID,
            "servicenow-client-secret": CLIENT_SECRET,
        }[reference]


class LoopbackTokenRequester:
    """Route the connector's fixed token URL into the loopback simulator."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def __call__(
        self,
        url: str,
        *,
        auth: tuple[str, str] | None,
        data: Mapping[str, str],
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response:
        assert url == _TOKEN_URL
        return httpx.post(
            f"{self._base_url}/oauth_token.do",
            auth=auth,
            data=data,
            params=params,
            headers=headers,
            timeout=timeout,
        )


def unexpected_token_request(
    url: str,
    *,
    auth: tuple[str, str] | None,
    data: Mapping[str, str],
    params: Mapping[str, str],
    headers: Mapping[str, str],
    timeout: float,
) -> httpx.Response:
    """Fail if descriptor-only rendering unexpectedly contacts an auth server."""
    del url, auth, data, params, headers, timeout
    raise AssertionError("connector rendering must not request a token")


@pytest.fixture
def simulator_server() -> Iterator[SimulatorServer]:
    with SimulatorServer() as server:
        yield server


@pytest.fixture
def config() -> SourceConfig:
    path = (
        Path(__file__).parents[1]
        / "src"
        / "dander_connector_servicenow"
        / "templates"
        / "servicenow.example.yaml"
    )
    result = load_source_config(path).model_copy(deep=True)
    result.auth_refs = {
        "client_id": "servicenow-client-id",
        "client_secret": "servicenow-client-secret",
    }
    result.auth_options["token_url"] = _TOKEN_URL
    result.endpoints[0].pagination = OffsetPagination(
        offset_param="sysparm_offset",
        limit_param="sysparm_limit",
        page_size=2,
    )
    return result


def build_source(
    config: SourceConfig,
    server: SimulatorServer,
    *,
    page_size: int = 2,
) -> ServiceNowTableSource:
    """Create a plugin-owned source pointed only at the local simulator."""
    resolved = config.model_copy(deep=True)
    resolved.base_url = f"{server.base_url}/api/now/table"
    resolved.endpoints[0].pagination = OffsetPagination(
        offset_param="sysparm_offset",
        limit_param="sysparm_limit",
        page_size=page_size,
    )
    auth = OAuth2ClientCredentials(
        SyntheticSecrets(),
        client_id_ref="servicenow-client-id",
        client_secret_ref="servicenow-client-secret",
        token_url=_TOKEN_URL,
        credential_placement="body",
        request_token=LoopbackTokenRequester(server.base_url),
    )
    return ServiceNowTableSource(resolved, auth, sleeper=lambda _delay: None)
