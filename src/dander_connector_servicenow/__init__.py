"""ServiceNow Table API connector plugin for Dander."""

from dander_connector_servicenow.plugin import create_plugin
from dander_connector_servicenow.source import ServiceNowTableSource

__all__ = ["ServiceNowTableSource", "create_plugin"]
