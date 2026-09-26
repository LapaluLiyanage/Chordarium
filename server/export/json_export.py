"""JSON export: the stored chord timeline, unchanged."""
import json

from server.export.grid import ExportOptions


def to_json(timeline: dict, opts: ExportOptions) -> str:
    return json.dumps(timeline, indent=2)
