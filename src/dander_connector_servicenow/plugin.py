"""Dander plugin entry point and presentation-safe ServiceNow descriptor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.plugins import (
    PLUGIN_API_VERSION,
    ConnectorDescriptor,
    ConnectorEndpointDescriptor,
    ConnectorFieldDescriptor,
    ConnectorPlugin,
)

from dander_connector_servicenow.source import ServiceNowTableSource

if TYPE_CHECKING:
    from dander.ingestion import Source, SourceConfig
    from dander.security import AuthStrategy

_INCIDENT_FIELDS = (
    ("sys_id", "System ID", "STRING", True),
    ("number", "Number", "STRING", True),
    ("short_description", "Short description", "STRING", False),
    ("description", "Description", "STRING", False),
    ("state", "State", "STRING", False),
    ("priority", "Priority", "STRING", False),
    ("active", "Active", "STRING", False),
    ("opened_at", "Opened at", "STRING", False),
    ("resolved_at", "Resolved at", "STRING", False),
    ("closed_at", "Closed at", "STRING", False),
    ("sys_created_on", "Created on", "STRING", True),
    ("sys_updated_on", "Updated on", "STRING", True),
    ("sys_updated_by", "Updated by", "STRING", False),
)


def _source_factory(config: SourceConfig, auth: AuthStrategy) -> Source:
    return ServiceNowTableSource(config, auth)


def create_plugin() -> ConnectorPlugin:
    """Return the API-v1 plugin declaration consumed by Dander."""
    endpoint = ConnectorEndpointDescriptor(
        endpoint_id="incidents",
        display_name="Incidents",
        fields=tuple(
            ConnectorFieldDescriptor(
                name=name,
                display_name=display_name,
                data_type=data_type,
                required=required,
            )
            for name, display_name, data_type, required in _INCIDENT_FIELDS
        ),
    )
    connector = ConnectorDescriptor(
        connector_id="servicenow",
        display_name="ServiceNow",
        engine="servicenow_table",
        description="Read ServiceNow incidents through stable bounded Table API pages.",
        endpoints=(endpoint,),
    )
    return ConnectorPlugin(
        plugin_id="servicenow",
        api_version=PLUGIN_API_VERSION,
        engine="servicenow_table",
        display_name="ServiceNow",
        description="First-party ServiceNow Table API connector.",
        source_factory=_source_factory,
        connectors=(connector,),
    )
