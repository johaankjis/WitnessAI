import os
import re
import tempfile
from pathlib import Path
from witness_contracts import Incident, IncidentReport

class JsonStorage:
    def __init__(self, demo_path: Path, output_dir: Path):
        self.demo_path = demo_path
        self.output_dir = output_dir

    def get_incident(self, incident_id: str) -> Incident | None:
        incident = Incident.model_validate_json(self.demo_path.read_text())
        return incident if incident.id == incident_id else None

    def _path(self, incident_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", incident_id):
            raise ValueError("invalid incident ID")
        return self.output_dir / f"{incident_id}.json"

    def get_report(self, incident_id: str) -> IncidentReport | None:
        path = self._path(incident_id)
        return IncidentReport.model_validate_json(path.read_text()) if path.exists() else None

    def save_report(self, report: IncidentReport) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self._path(report.incident_id)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.output_dir, delete=False) as handle:
                temporary = handle.name
                handle.write(report.model_dump_json(indent=2))
            os.replace(temporary, destination)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
