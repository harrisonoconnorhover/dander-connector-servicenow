"""Stateful loopback ServiceNow Table API simulator for plugin contract tests."""

from __future__ import annotations

import json
import socket
from collections import Counter
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from secrets import compare_digest
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Annotated, Any, cast
from urllib.parse import parse_qs
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi import Path as ApiPath
from pydantic import BaseModel

CLIENT_ID = "dander-servicenow-client"
CLIENT_SECRET = "dander-servicenow-secret"
ACCESS_TOKEN = "dander-servicenow-token"
ORDER_QUERY = "ORDERBYsys_updated_on^ORDERBYsys_id"


class Scenario(StrEnum):
    """Named deterministic simulator behavior."""

    NORMAL = "normal"
    EXPIRED_CREDENTIALS = "expired_credentials"
    THROTTLING = "throttling"
    MISSING_PERMISSIONS = "missing_permissions"
    MALFORMED_RECORD = "malformed_record"


class ScenarioRequest(BaseModel):
    """Select one simulator behavior."""

    scenario: Scenario


class IncidentCreate(BaseModel):
    """Narrow writable fields used only to prepare test state."""

    short_description: str
    description: str = ""
    state: str = "1"
    priority: str = "4"
    active: str = "true"


class IncidentUpdate(BaseModel):
    """Narrow patch fields used only to prepare test state."""

    short_description: str | None = None
    description: str | None = None
    state: str | None = None
    priority: str | None = None
    active: str | None = None


class SimulatorState:
    """Lock-protected synthetic incident store and request ledger."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._lock = Lock()
        self._initial = [dict(row) for row in rows]
        self._rows = {str(row["sys_id"]): dict(row) for row in rows}
        self._scenario = Scenario.NORMAL
        self._requests: Counter[str] = Counter()
        self._throttle_consumed = False
        self._clock = datetime(2026, 8, 3, 15, 0, 0)
        self._next_number = 9_000_001

    def reset(self) -> None:
        with self._lock:
            self._rows = {str(row["sys_id"]): dict(row) for row in self._initial}
            self._scenario = Scenario.NORMAL
            self._requests.clear()
            self._throttle_consumed = False
            self._clock = datetime(2026, 8, 3, 15, 0, 0)
            self._next_number = 9_000_001

    def set_scenario(self, scenario: Scenario) -> None:
        with self._lock:
            self._scenario = scenario
            self._requests.clear()
            self._throttle_consumed = False

    def scenario(self) -> Scenario:
        with self._lock:
            return self._scenario

    def record_request(self, key: str) -> None:
        with self._lock:
            self._requests[key] += 1

    def consume_throttle(self) -> bool:
        with self._lock:
            if self._throttle_consumed:
                return False
            self._throttle_consumed = True
            return True

    def list_rows(self) -> list[dict[str, object]]:
        with self._lock:
            return [dict(row) for row in self._rows.values()]

    def create(self, payload: IncidentCreate) -> dict[str, object]:
        with self._lock:
            timestamp = self._tick()
            sys_id = uuid4().hex
            row: dict[str, object] = {
                "sys_id": sys_id,
                "number": f"INC{self._next_number:07d}",
                "short_description": payload.short_description,
                "description": payload.description,
                "state": payload.state,
                "priority": payload.priority,
                "active": payload.active,
                "opened_at": timestamp,
                "resolved_at": "",
                "closed_at": "",
                "sys_created_on": timestamp,
                "sys_updated_on": timestamp,
                "sys_updated_by": "dander.integration",
            }
            self._next_number += 1
            self._rows[sys_id] = row
            return dict(row)

    def update(self, sys_id: str, payload: IncidentUpdate) -> dict[str, object]:
        with self._lock:
            row = self._rows.get(sys_id)
            if row is None:
                raise HTTPException(status_code=404, detail={"error": "record_not_found"})
            row.update(payload.model_dump(exclude_none=True))
            row["sys_updated_on"] = self._tick()
            row["sys_updated_by"] = "dander.integration"
            return dict(row)

    def delete(self, sys_id: str) -> None:
        with self._lock:
            if self._rows.pop(sys_id, None) is None:
                raise HTTPException(status_code=404, detail={"error": "record_not_found"})

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "scenario": self._scenario.value,
                "records": len(self._rows),
                "requests": dict(self._requests),
            }

    def _tick(self) -> str:
        self._clock += timedelta(seconds=1)
        return self._clock.strftime("%Y-%m-%d %H:%M:%S")


def create_simulator() -> FastAPI:
    """Build a fresh simulator application with isolated mutable state."""
    state = SimulatorState(_load_rows())
    app = FastAPI(title="Dander ServiceNow Table API simulator", version="1.0.0")
    app.state.simulator = state

    @app.post("/oauth_token.do", operation_id="issueAccessToken")
    async def issue_access_token(request: Request) -> dict[str, object]:
        body = parse_qs((await request.body()).decode("utf-8"))
        state.record_request("token")
        if (
            state.scenario() is Scenario.EXPIRED_CREDENTIALS
            or body.get("grant_type") != ["client_credentials"]
            or not _valid_client(body)
        ):
            raise HTTPException(status_code=401, detail={"error": "invalid_client"})
        return {"access_token": ACCESS_TOKEN, "token_type": "Bearer", "expires_in": 1800}

    @app.get("/api/now/table/incident", operation_id="listIncidents")
    def list_incidents(
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(alias="sysparm_limit", ge=1)] = 100,
        offset: Annotated[int, Query(alias="sysparm_offset", ge=0)] = 0,
        fields: Annotated[str | None, Query(alias="sysparm_fields")] = None,
        query: Annotated[str | None, Query(alias="sysparm_query")] = None,
        display_value: Annotated[bool, Query(alias="sysparm_display_value")] = False,
        exclude_reference_link: Annotated[
            bool, Query(alias="sysparm_exclude_reference_link")
        ] = True,
    ) -> dict[str, list[dict[str, object]]]:
        _require_access(authorization)
        state.record_request(f"incidents:{offset}")
        if state.scenario() is Scenario.MISSING_PERMISSIONS:
            raise HTTPException(status_code=403, detail={"error": "insufficient_roles"})
        if state.scenario() is Scenario.THROTTLING and state.consume_throttle():
            raise HTTPException(status_code=429, detail={"error": "rate_limit"})
        if query != ORDER_QUERY or display_value or not exclude_reference_link:
            raise HTTPException(status_code=400, detail={"error": "invalid_query_contract"})

        selected = None if fields is None else tuple(item for item in fields.split(",") if item)
        rows = sorted(
            state.list_rows(),
            key=lambda row: (str(row["sys_updated_on"]), str(row["sys_id"])),
        )[offset : offset + limit]
        page = [
            row if selected is None else {name: row.get(name) for name in selected} for row in rows
        ]
        if state.scenario() is Scenario.MALFORMED_RECORD and page:
            page[0]["short_description"] = {"value": page[0].get("short_description")}
        return {"result": page}

    @app.post("/api/now/table/incident", operation_id="createIncident")
    def create_incident(
        payload: IncidentCreate,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, dict[str, object]]:
        _require_access(authorization)
        state.record_request("create")
        return {"result": state.create(payload)}

    @app.patch("/api/now/table/incident/{sys_id}", operation_id="updateIncident")
    def update_incident(
        payload: IncidentUpdate,
        sys_id: Annotated[str, ApiPath(pattern=r"^[0-9a-f]{32}$")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, dict[str, object]]:
        _require_access(authorization)
        state.record_request("update")
        return {"result": state.update(sys_id, payload)}

    @app.delete("/api/now/table/incident/{sys_id}", operation_id="deleteIncident", status_code=204)
    def delete_incident(
        sys_id: Annotated[str, ApiPath(pattern=r"^[0-9a-f]{32}$")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        _require_access(authorization)
        state.record_request("delete")
        state.delete(sys_id)
        return Response(status_code=204)

    @app.put("/_dander/scenario", operation_id="setScenario")
    def set_scenario(request: ScenarioRequest) -> dict[str, str]:
        state.set_scenario(request.scenario)
        return {"scenario": request.scenario.value}

    @app.post("/_dander/reset", operation_id="resetSimulator")
    def reset_simulator() -> dict[str, str]:
        state.reset()
        return {"status": "reset"}

    return app


def _load_rows() -> list[dict[str, object]]:
    payload: Any = json.loads(
        (Path(__file__).parent / "fixtures" / "incidents.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError("Invalid packaged ServiceNow incident fixture")
    return [dict(cast("dict[str, object]", row)) for row in payload]


def _valid_client(body: dict[str, list[str]]) -> bool:
    client_ids = body.get("client_id", [])
    client_secrets = body.get("client_secret", [])
    return (
        len(client_ids) == 1
        and len(client_secrets) == 1
        and compare_digest(client_ids[0], CLIENT_ID)
        and compare_digest(client_secrets[0], CLIENT_SECRET)
    )


def _require_access(authorization: str | None) -> None:
    if authorization != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})


class SimulatorServer(AbstractContextManager["SimulatorServer"]):
    """Own a background simulator service bound to loopback."""

    def __init__(self) -> None:
        self.app = create_simulator()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        host, port = cast("tuple[str, int]", self._socket.getsockname())
        self.base_url = f"http://{host}:{port}"
        self._server = uvicorn.Server(
            uvicorn.Config(self.app, log_level="critical", access_log=False, lifespan="off")
        )
        self._thread: Thread | None = None

    def start(self) -> SimulatorServer:
        """Start serving and wait until the loopback socket accepts requests."""
        if self._thread is not None:
            return self
        self._thread = Thread(target=self._serve, name="servicenow-simulator", daemon=True)
        self._thread.start()
        deadline = monotonic() + 5
        while not self._server.started:
            if not self._thread.is_alive() or monotonic() >= deadline:
                raise RuntimeError("ServiceNow simulator did not start")
            sleep(0.01)
        return self

    def _serve(self) -> None:
        self._server.run(sockets=[self._socket])

    def snapshot(self) -> dict[str, object]:
        """Return synthetic state and request counters."""
        return cast("SimulatorState", self.app.state.simulator).snapshot()

    def close(self) -> None:
        """Stop the service and release the socket."""
        if self._thread is not None:
            self._server.should_exit = True
            self._thread.join(timeout=5)
            self._thread = None
        if self._socket.fileno() != -1:
            self._socket.close()

    def __enter__(self) -> SimulatorServer:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        del exc_info
        self.close()
