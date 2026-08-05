"""Plugin-owned ServiceNow source built on Dander's generic REST runtime."""

from dander.ingestion import DltRestSource


class ServiceNowTableSource(DltRestSource):
    """Read ServiceNow Table API declarations through Dander's bounded REST adapter."""
