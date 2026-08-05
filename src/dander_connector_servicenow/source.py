"""Plugin-owned ServiceNow source with bounded extraction and targeted read capabilities."""

from __future__ import annotations

import re
from time import sleep
from typing import TYPE_CHECKING, Any

import httpx
from dander.ingestion import (
    RECORD_NOT_FOUND,
    ConnectionStatus,
    CountResult,
    DltRestSource,
    RecordNotFound,
)
from dander.security import OAuthTokenError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from dander.ingestion import Endpoint, SourceConfig
    from dander.security import AuthStrategy

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_SYS_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class ServiceNowSourceError(ValueError):
    """Raised when a targeted ServiceNow read violates the connector contract."""


class ServiceNowTableSource(DltRestSource):
    """Read ServiceNow tables through Dander and expose cheap provider-native lookups."""

    def __init__(
        self,
        config: SourceConfig,
        auth: AuthStrategy,
        *,
        requester: Callable[[httpx.Request], httpx.Response] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        super().__init__(config, auth, sleeper=sleeper)
        self._requester = requester or _send_request
        self._sleep_capability = sleeper

    def get_single_object(
        self,
        endpoint: str,
        identity: Mapping[str, str],
    ) -> Mapping[str, Any] | RecordNotFound:
        """Fetch one record by its declared ServiceNow ``sys_id``."""
        declaration = self._get_endpoint(endpoint)
        table = _table_name(declaration)
        if declaration.primary_key != ["sys_id"] or set(identity) != {"sys_id"}:
            raise ServiceNowSourceError(
                f"ServiceNow endpoint {endpoint!r} targeted lookup requires identity field 'sys_id'"
            )
        sys_id = identity["sys_id"]
        if not _SYS_ID.fullmatch(sys_id):
            raise ServiceNowSourceError(
                f"ServiceNow endpoint {endpoint!r} targeted lookup received an invalid sys_id"
            )
        payload = self._request_json(
            f"{self.config.base_url.rstrip('/')}/{table}/{sys_id}",
            endpoint=endpoint,
            params=_record_params(declaration),
            allow_not_found=True,
        )
        if payload is RECORD_NOT_FOUND:
            return RECORD_NOT_FOUND
        return _record_payload(payload, declaration, expected_sys_id=sys_id)

    def count(self, endpoint: str, *, since: str | None = None) -> CountResult:
        """Return ServiceNow's exact Aggregate API count without materializing records."""
        declaration = self._get_endpoint(endpoint)
        table = _table_name(declaration)
        if since is not None:
            raise ServiceNowSourceError(
                f"ServiceNow endpoint {endpoint!r} does not support cursor-bounded counts"
            )
        payload = self._request_json(
            f"{_stats_base_url(self.config.base_url)}/{table}",
            endpoint=endpoint,
            params={"sysparm_count": "true"},
        )
        return CountResult.exact(_count_payload(payload, endpoint))

    def test_connection(self) -> ConnectionStatus:
        """Probe OAuth, ACL, and Aggregate API access without returning business records."""
        if not self.config.endpoints:
            raise ServiceNowSourceError("ServiceNow connector has no declared endpoints")
        endpoint = self.config.endpoints[0].name
        try:
            self.count(endpoint)
        except ServiceNowSourceError as error:
            message = str(error)
            for detail in ("authentication failed", "permission denied"):
                if detail in message:
                    return ConnectionStatus(ok=False, detail=detail)
            raise
        return ConnectionStatus(ok=True)

    def _request_json(
        self,
        url: str,
        *,
        endpoint: str,
        params: Mapping[str, str | bool],
        allow_not_found: bool = False,
    ) -> object | RecordNotFound:
        policy = self.config.rate_limit
        max_retries = policy.max_retries if policy is not None else 0
        retry_error: httpx.HTTPError | None = None
        for attempt in range(max_retries + 1):
            response: httpx.Response | None = None
            try:
                request = httpx.Request(
                    "GET",
                    url,
                    params=params,
                    headers={"Accept": "application/json"},
                )
                response = self._requester(self._auth.apply(request))
                response.raise_for_status()
                payload: object = response.json()
                return payload
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                if allow_not_found and status == 404:
                    return RECORD_NOT_FOUND
                if status in {401, 403}:
                    reason = "authentication failed" if status == 401 else "permission denied"
                    raise ServiceNowSourceError(
                        f"ServiceNow endpoint {endpoint!r} {reason} (HTTP {status})"
                    ) from error
                if status not in _RETRYABLE_STATUSES:
                    raise ServiceNowSourceError(
                        f"ServiceNow endpoint {endpoint!r} request was rejected (HTTP {status})"
                    ) from error
                retry_error = error
            except OAuthTokenError as error:
                raise ServiceNowSourceError(
                    f"ServiceNow endpoint {endpoint!r} authentication failed"
                ) from error
            except httpx.HTTPError as error:
                retry_error = error
            if attempt == max_retries:
                break
            assert policy is not None
            multiplier = 2**attempt if policy.backoff.value == "exponential" else 1
            self._sleep_capability(multiplier / policy.requests_per_second)
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint!r} request failed after bounded retries"
        ) from retry_error


def _send_request(request: httpx.Request) -> httpx.Response:
    with httpx.Client(timeout=30) as client:
        response = client.send(request)
        response.read()
        return response


def _table_name(endpoint: Endpoint) -> str:
    table = endpoint.path.strip("/")
    if not _TABLE_NAME.fullmatch(table):
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint.name!r} must declare one Table API table name"
        )
    return table


def _stats_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if not normalized.endswith("/table"):
        raise ServiceNowSourceError("ServiceNow base_url must end with '/api/now/table'")
    return f"{normalized.removesuffix('/table')}/stats"


def _record_params(endpoint: Endpoint) -> dict[str, str | bool]:
    fields = ",".join(field.name for field in endpoint.raw_schema)
    if not fields:
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint.name!r} targeted lookup requires a declared schema"
        )
    return {
        "sysparm_display_value": False,
        "sysparm_exclude_reference_link": True,
        "sysparm_fields": fields,
    }


def _record_payload(
    payload: object,
    endpoint: Endpoint,
    *,
    expected_sys_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint.name!r} targeted record response was invalid"
        )
    record = payload["result"]
    declared = {field.name for field in endpoint.raw_schema}
    if set(record) != declared or record.get("sys_id") != expected_sys_id:
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint.name!r} targeted record fields were invalid"
        )
    if any(isinstance(value, (dict, list)) for value in record.values()):
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint.name!r} targeted record contained structured data"
        )
    return dict(record)


def _count_payload(payload: object | RecordNotFound, endpoint: str) -> int:
    if not isinstance(payload, dict):
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint!r} aggregate response was invalid"
        )
    result = payload.get("result")
    if isinstance(result, dict):
        aggregate = result
    elif isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        aggregate = result[0]
    else:
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint!r} aggregate response was invalid"
        )
    stats = aggregate.get("stats")
    count = stats.get("count") if isinstance(stats, dict) else None
    if isinstance(count, bool) or not isinstance(count, (int, str)):
        raise ServiceNowSourceError(f"ServiceNow endpoint {endpoint!r} aggregate count was invalid")
    try:
        parsed = int(count)
    except ValueError as error:
        raise ServiceNowSourceError(
            f"ServiceNow endpoint {endpoint!r} aggregate count was invalid"
        ) from error
    if parsed < 0 or str(parsed) != str(count):
        raise ServiceNowSourceError(f"ServiceNow endpoint {endpoint!r} aggregate count was invalid")
    return parsed
