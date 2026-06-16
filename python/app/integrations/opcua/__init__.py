"""OPC UA protocol adapter for industrial equipment data acquisition.

This package implements an OPC UA client that subscribes to data nodes
from OPC UA servers and persists the collected samples into the project's
TDengine time-series database.

The public surface is intentionally small:

* :class:`OPCUAAdapter` – the high-level subscription / storage orchestrator.
* :class:`Sample` – typed view over a single polling cycle's data items.
* :func:`parse_opcua_data` – pure-function OPC UA data → ``Sample`` converter.

The CLI entry point is available via::

    python -m app.integrations.opcua.cli --endpoint opc.tcp://localhost:4840
"""

from app.integrations.opcua.adapter import OPCUAAdapter
from app.integrations.opcua.parser import Sample, parse_opcua_data

__all__ = ["OPCUAAdapter", "Sample", "parse_opcua_data"]
