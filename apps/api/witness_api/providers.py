"""Provider adapters with private schemas; public v1 contracts remain unchanged."""
from typing import Annotated, Literal
from witness_vision.adapter import VisionObserver
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from witness_contracts import (AtomicClaim, EvidenceWindow, ClaimVerdict, IncidentReport, Provenance,
                               Incident, DetectorObservation)
from .provider_io import ChatTransport, ProviderError
from .media import VideoAsset, LocalMedia
from .pipeline import Pipeline
from .interfaces import YoloObserver

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Structured(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class ExtractedClaim(Structured):
    statement_id: Text
    source_quote: Text
    text: Text
    subject: Text
    category: Literal['lane_change', 'braking', 'traffic_signal', 'other']


class Extraction(Structured):
    claims: list[ExtractedClaim] = Field(min_length=1, max_length=32)


class LocatedWindow(Structured):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    visibility: Literal['visible', 'not_visible']
    observation: Text

    @model_validator(mode='after')
    def ordered(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError('unordered window')
        return self


class Localization(Structured):
    windows: list[LocatedWindow] = Field(min_length=1, max_length=4)


class Verification(Structured):
    verdict: Literal['supported', 'contradicted', 'not_visible']
    establishes_claim: bool
    observation: Text
    inference: Text
    uncertainty: Text
    confidence: float | None = Field(default=None, ge=0, le=1)


class ReportOutline(Structured):
    claim_order: list[Text] = Field(min_length=1, max_length=32)
    review_first: list[Text] = Field(max_length=32)


class WandbAdapter:
    def __init__(self, chat: ChatTransport):
        self.chat = chat

    def extract(self, incident: Incident) -> list[AtomicClaim]:
        result = self.chat.complete(
            'Split driver statements into atomic, independently testable assertions: exactly one action, '
            'state or negation per claim. Resolve I to the statement driver_id. Preserve negation and '
            'actor identity; never add facts. Include an exact source substring per assertion. '
            'Cover every factual assertion, including those unlikely to be visible. Do not judge truth.',
            {'statements': [s.model_dump() for s in incident.statements]}, Extraction)
        statements = {s.id: s for s in incident.statements}
        claims, seen = [], set()
        for index, item in enumerate(result.claims):
            if item.statement_id not in statements or item.source_quote not in statements[item.statement_id].text:
                raise ProviderError('wandb: extracted claim has invalid statement/source quote')
            key = (item.statement_id, item.text.casefold())
            if key in seen:
                raise ProviderError('wandb: duplicate extracted claim')
            seen.add(key)
            claims.append(AtomicClaim(id=f'c{index + 1}', **item.model_dump(exclude={'source_quote'})))
        return claims

    def generate(self, incident: Incident, claims: list[AtomicClaim], verdicts: list[ClaimVerdict],
                 observations: list[DetectorObservation]) -> IncidentReport:
        outline = self.chat.complete(
            'Organize a human-review incident report using only supplied claim IDs. Put the most '
            'important unresolved claims in review_first. Include every claim exactly once in '
            'claim_order. Do not decide fault, liability, traffic-law violations or invent evidence.',
            {'claims': [c.model_dump(mode='json') for c in claims],
             'verdicts': [v.model_dump(mode='json') for v in verdicts]}, ReportOutline)
        ids = {c.id for c in claims}
        if (len(outline.claim_order) != len(ids) or set(outline.claim_order) != ids or
                not set(outline.review_first) <= ids or len(set(outline.review_first)) != len(outline.review_first)):
            raise ProviderError('wandb: report outline has invalid claim references')
        # Render validated evidence verbatim, rather than allowing a report LLM to rewrite verdicts.
        rows = ['Draft incident report. Human review required. No legal fault determination.',
                f'Report organization: wandb-inference; model={self.chat.model}.',
                'Priority review: ' + (', '.join(outline.review_first) or 'all claims') + '.']
        by_claim = {c.id: c for c in claims}
        by_verdict = {v.claim_id: v for v in verdicts}
        for claim_id in outline.claim_order:
            verdict = by_verdict[claim_id]
            rows.append(f'{claim_id}: {by_claim[claim_id].text} — {verdict.verdict.value}')
            for window in verdict.evidence:
                rows.append(f'Observation [{window.start_seconds:g}–{window.end_seconds:g}s]: '
                            f'{window.description} Source: {window.provenance.adapter}; '
                            f'{window.provenance.source}')
            rows.extend([f'Inference: {verdict.explanation}', f'Uncertainty: {verdict.uncertainty}'])
        rows.append('Detector corroboration: unavailable.' if not observations else
                    'Detector observations are supplied separately; no automatic fault decision.')
        return IncidentReport(incident_id=incident.id, is_mock=False, claims=claims,
                              verdicts=verdicts, observations=observations, summary='\n'.join(rows))


class CosmosAdapter:
    def __init__(self, chat: ChatTransport, asset: VideoAsset):
        self.chat, self.asset = chat, asset

    def provenance(self, stage: str) -> Provenance:
        return Provenance(adapter='nvidia-cosmos-reason2', version=self.chat.model,
                          source=f'{stage}; sha256={self.asset.sha256}; full video input; original-video seconds',
                          is_mock=False)

    def localize(self, incident: Incident, claim: AtomicClaim) -> list[EvidenceWindow]:
        if incident.video_uri != self.asset.uri or incident.is_mock:
            raise ProviderError('cosmos: incident/media mismatch')
        result = self.chat.complete(
            'Locate the visual event relevant to the claim. Timestamps are seconds from the original '
            'video start, never normalized or clip-relative. Give short review windows. Separate '
            'direct visual observations from assumptions. If the claim cannot be seen, return a '
            'not_visible window covering the reviewed footage, explaining what is obscured or absent. '
            'Driver statements are unverified allegations, not visual evidence.',
            {'claim': claim.model_dump(), 'duration_seconds': self.asset.duration}, Localization,
            self.asset.data_url)
        windows = []
        for item in result.windows:
            if item.end_seconds > min(self.asset.duration, incident.duration_seconds):
                raise ProviderError('cosmos: localization timestamp exceeds actual video duration')
            windows.append(EvidenceWindow(video_uri=self.asset.uri, start_seconds=item.start_seconds,
                end_seconds=item.end_seconds, visibility=item.visibility, description=item.observation,
                provenance=self.provenance('localization')))
        return windows

    def verify(self, claim: AtomicClaim, windows: list[EvidenceWindow]) -> ClaimVerdict:
        if not windows or any(w.video_uri != self.asset.uri or w.end_seconds > self.asset.duration or
                              w.start_seconds < 0 or w.end_seconds <= w.start_seconds for w in windows):
            raise ProviderError('cosmos: invalid verification window')
        result = self.chat.complete(
            'Verify this one claim using only visual evidence within the supplied review windows. '
            'The full original video is attached: timestamps stay relative to its start. Return a '
            'brief observation, evidence-based inference and uncertainty separately. supported '
            'requires direct evidence for the claim; contradicted requires direct evidence of its '
            'opposite. Missing, ambiguous, occluded, off-camera or insufficient evidence means '
            'not_visible, never contradicted. Set establishes_claim=false whenever footage does '
            'not resolve truth or falsity. Confidence is optional and uncalibrated. No fault decisions.',
            {'claim': claim.model_dump(), 'windows': [w.model_dump(mode='json') for w in windows]},
            Verification, self.asset.data_url)
        visible = any(w.visibility == 'visible' for w in windows)
        verdict = result.verdict if result.establishes_claim and visible else 'not_visible'
        if verdict == 'not_visible':
            evidence = [EvidenceWindow(**{**w.model_dump(), 'visibility': 'not_visible',
                'description': result.observation, 'provenance': self.provenance('verification')}) for w in windows]
            explanation = 'Reviewed footage does not establish this claim; absence is not contradiction.'
            confidence = None
        else:
            evidence = [EvidenceWindow(**{**w.model_dump(), 'description': result.observation,
                'provenance': self.provenance('verification')}) for w in windows]
            explanation, confidence = result.inference, result.confidence
        return ClaimVerdict(claim_id=claim.id, verdict=verdict, evidence=evidence,
            explanation=explanation, uncertainty=result.uncertainty + ' Model judgment; human review required. Confidence, if supplied, is uncalibrated.',
            confidence=confidence, provenance=self.provenance('verification'))


class NoDetector:
    def observe(self, incident: Incident, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        return []

    def fuse(self, verdict: ClaimVerdict, observations: list[DetectorObservation]) -> ClaimVerdict:
        return verdict


class RealPipeline:
    """Per-run media binding keeps concurrent jobs from mixing incident evidence."""
    def __init__(self, wandb: WandbAdapter, cosmos: ChatTransport, media: LocalMedia, observer: VisionObserver | None = None):
        self.wandb, self.cosmos, self.media = wandb, cosmos, media
        self.observer = observer

    def analyze(self, incident: Incident) -> IncidentReport:
        asset = self.media.load(incident)
        cosmos = CosmosAdapter(self.cosmos, asset)
        none = NoDetector()
        # Bind the detector to the exact immutable bytes supplied to Cosmos.
        observer: YoloObserver = none
        if self.observer is not None:
            observer = SnapshotObserver(self.observer, asset)
        return Pipeline(self.wandb, cosmos, cosmos, observer, none, self.wandb).analyze(incident)


class SnapshotObserver:
    def __init__(self, observer: VisionObserver, asset: VideoAsset):
        self.observer, self.asset = observer, asset

    def observe(self, incident: Incident, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        import base64
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix='witness-vision-') as directory:
            path = Path(directory) / 'source.mp4'
            path.write_bytes(base64.b64decode(self.asset.data_url.split(',', 1)[1]))
            bound = VisionObserver(detector=self.observer.detector, config=self.observer.config,
                                   media_root=Path(directory))
            observations = bound.observe(incident.model_copy(update={'video_uri': str(path)}), claims)
        for observation in observations:
            observation.evidence.video_uri = incident.video_uri
            source = observation.provenance.source.replace(str(path), incident.video_uri)
            source += f'; original video seconds; sha256={self.asset.sha256}'
            observation.provenance = observation.provenance.model_copy(update={'source': source})
            observation.evidence.provenance = observation.provenance.model_copy()
        return observations
