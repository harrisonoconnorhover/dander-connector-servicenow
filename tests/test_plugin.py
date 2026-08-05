"""Dander plugin API and package registration checks."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

from dander.plugins import PLUGIN_API_VERSION

from dander_connector_servicenow import ServiceNowTableSource, create_plugin

if TYPE_CHECKING:
    from dander.ingestion import SourceConfig
    from dander.security import AuthStrategy


def test_plugin_contract_and_descriptor_are_api_v1_compatible() -> None:
    plugin = create_plugin()

    assert plugin.plugin_id == "servicenow"
    assert plugin.api_version == PLUGIN_API_VERSION
    assert plugin.engine == "servicenow_table"
    assert plugin.connectors[0].connector_id == "servicenow"
    assert plugin.connectors[0].endpoints[0].endpoint_id == "incidents"
    assert {field.name for field in plugin.connectors[0].endpoints[0].fields} >= {
        "sys_id",
        "number",
        "sys_updated_on",
    }


def test_distribution_registers_exact_dander_entry_point() -> None:
    distribution = importlib.metadata.distribution("dander-connector-servicenow")
    entry_points = [
        point
        for point in distribution.entry_points
        if point.group == "dander.connectors" and point.name == "servicenow"
    ]

    assert len(entry_points) == 1
    assert entry_points[0].load() is create_plugin


def test_factory_returns_plugin_owned_source(
    config: SourceConfig,
    auth: AuthStrategy,
) -> None:
    source = create_plugin().source_factory(config, auth)

    assert isinstance(source, ServiceNowTableSource)
    assert source.__class__.__module__ == "dander_connector_servicenow.source"
