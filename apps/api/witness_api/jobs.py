"""Single-process bounded jobs, deduplicated by incident ID; no durable queue."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Protocol
from witness_contracts import AnalysisStatus, Incident, IncidentReport
from .interfaces import Storage


class AnalysisRunner(Protocol):
    def analyze(self, incident: Incident) -> IncidentReport: ...


class QueueFull(RuntimeError):
    pass


class Jobs:
    def __init__(self, runner: AnalysisRunner, store: Storage, capacity: int = 4, history: int = 128):
        self.runner, self.store = runner, store
        self.capacity, self.history = capacity, history
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='witness-analysis')
        self.lock = Lock()
        self.states: OrderedDict[str, AnalysisStatus] = OrderedDict()
        self.closed = False

    def get(self, incident_id: str) -> AnalysisStatus | None:
        with self.lock:
            return self.states.get(incident_id)

    def submit(self, incident: Incident) -> AnalysisStatus:
        with self.lock:
            existing = self.states.get(incident.id)
            if existing:
                return existing
            if self.closed or sum(s.state in ('pending', 'running') for s in self.states.values()) >= self.capacity:
                raise QueueFull('Analysis queue is full; retry later')
            status = AnalysisStatus(incident_id=incident.id, state='pending', is_mock=incident.is_mock,
                                    detail='Queued; GET /incidents/{incident_id}/status to poll until completed or failed.')
            # Terminal states are sticky until process restart, so repeated POST is safe polling.
            self.states[incident.id] = status
            while len(self.states) > self.history:
                terminal = next((key for key, value in self.states.items()
                                 if value.state in ('completed', 'failed')), None)
                if terminal is None:
                    break
                del self.states[terminal]
            try:
                self.executor.submit(self._run, incident)
            except RuntimeError:
                del self.states[incident.id]
                raise QueueFull('Analysis worker is unavailable') from None
            return status

    def _run(self, incident: Incident) -> None:
        self._state(incident, 'running', 'Analysis in progress; GET /incidents/{incident_id}/status to poll.')
        try:
            self.store.save_report(self.runner.analyze(incident))
        except Exception as error:
            # Only our sanitized provider messages can cross the API boundary.
            from .provider_io import ProviderError
            detail = str(error) if isinstance(error, ProviderError) else 'Analysis or storage failed'
            self._state(incident, 'failed', detail + '; no new report committed.')
        else:
            self._state(incident, 'completed', 'Analysis complete; retrieve /results. Human review required.')

    def _state(self, incident: Incident, state: str, detail: str) -> None:
        with self.lock:
            self.states[incident.id] = AnalysisStatus(incident_id=incident.id, state=state,
                                                     is_mock=incident.is_mock, detail=detail)

    def close(self) -> None:
        with self.lock:
            self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
