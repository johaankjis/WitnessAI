import json
import subprocess
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from witness_contracts import AtomicClaim, Incident
from witness_api.config import configured_pipeline
from witness_api.jobs import Jobs, QueueFull
from witness_api.media import LocalMedia, VideoAsset
from witness_api.provider_io import ChatTransport, ProviderError, parse_output
from witness_api.providers import (CosmosAdapter, Extraction, Localization, ReportOutline,
                                   Verification, WandbAdapter, RealPipeline)


@pytest.fixture
def incident():
    return Incident(id='real-1', title='Review', video_uri='clip.mp4', duration_seconds=20,
        is_mock=False, statements=[{'id': 'a', 'driver_id': 'driver-a', 'text': 'I braked and stopped.'},
                                 {'id': 'b', 'driver_id': 'driver-b', 'text': 'The light was green.'}])


@pytest.fixture
def claim():
    return AtomicClaim(id='c1', statement_id='a', text='Driver A braked.', subject='driver-a', category='braking')


def extraction():
    return {'claims': [{'statement_id': 'a', 'source_quote': 'I braked', 'text': 'Driver A braked.',
                        'subject': 'driver-a', 'category': 'braking'},
                       {'statement_id': 'a', 'source_quote': 'stopped', 'text': 'Driver A stopped.',
                        'subject': 'driver-a', 'category': 'other'}]}


def localization(**changes):
    return {'windows': [dict(start_seconds=8.0, end_seconds=12.0, visibility='visible',
                            observation='The vehicle slows.', **changes)]}


def verification(**changes):
    data = dict(verdict='supported', establishes_claim=True, observation='Vehicle slows.',
                inference='Consistent with braking.', uncertainty='Pedal is not visible.', confidence=None)
    data.update(changes)
    return data


def envelope(data, **changes):
    choice = {'finish_reason': 'stop', 'message': {'content': json.dumps(data)}}
    choice.update(changes)
    return {'choices': [choice]}


def chat(responses, requests=None, **options):
    responses = iter(responses)
    def handle(request):
        if requests is not None:
            requests.append(request)
        item = next(responses)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, int):
            return httpx.Response(item, text='private upstream details')
        return httpx.Response(200, json=item)
    return ChatTransport('test-provider', 'https://provider.example/v1', 'test-model', 'test-only-key',
                         transport=httpx.MockTransport(handle), sleep=lambda _: None, **options)


def cosmos(responses, requests=None):
    return CosmosAdapter(chat(responses, requests), VideoAsset('clip.mp4', 20, 'data:video/mp4;base64,AAAA', 'abc'))


@pytest.mark.parametrize('content', ['garbage', '{} trailing', '{"claim_order":["c1"],"claim_order":[],"review_first":[]}',
    '{"claim_order":["c1"],"review_first":[],"extra":1}', '{"claim_order":[],"review_first":[]}',
    '<think>private</think>{"claim_order":["c1"],"review_first":[]}', '[]', 'null', 'NaN', '"x"', 'x' * 100001])
def test_malformed_structured(content):
    with pytest.raises(ProviderError):
        parse_output(content, ReportOutline)


def test_fenced_json():
    result = parse_output('```json\n{"claim_order":["c1"],"review_first":[]}\n```', ReportOutline)
    assert result.claim_order == ['c1']


@pytest.mark.parametrize('body', [{}, {'choices': []}, envelope({}, finish_reason='length'),
                                 envelope({}, message={'content': None}),
                                 envelope({}, message={'content': '{}', 'refusal': 'no'})])
def test_bad_envelopes(body):
    with pytest.raises(ProviderError):
        chat([body]).complete('test', {}, ReportOutline)


def test_retry_wire_contract():
    requests = []
    c = chat([429, 503, envelope({'claim_order': ['c1'], 'review_first': []})], requests, project='team/project')
    assert c.complete('report', {}, ReportOutline).claim_order == ['c1']
    assert len(requests) == 3
    req = requests[0]
    assert req.url.path == '/v1/chat/completions'
    assert req.headers['authorization'] == 'Bearer test-only-key'
    assert req.headers['openai-project'] == 'team/project'
    body = json.loads(req.content)
    assert body['model'] == 'test-model' and body['stream'] is False
    assert 'response_format' not in body


@pytest.mark.parametrize('failure', [401, 403, 400, 302])
def test_permanent_failure_no_retry_or_leak(failure):
    requests = []
    with pytest.raises(ProviderError) as error:
        chat([failure], requests).complete('secret statement', {}, ReportOutline)
    assert len(requests) == 1
    assert 'private' not in str(error.value) and 'test-only-key' not in str(error.value)


@pytest.mark.parametrize('failure', [httpx.ReadTimeout('secret'), httpx.ConnectError('secret'), 503])
def test_retry_exhaustion(failure):
    requests = []
    with pytest.raises(ProviderError, match='retry limit exhausted'):
        chat([failure] * 3, requests).complete('x', {}, ReportOutline)
    assert len(requests) == 3


@pytest.mark.parametrize('url', ['https://user:secret@host/v1', 'http://remote/v1', 'file:///tmp', 'https://host/v1?key=x'])
def test_bad_endpoint(url):
    with pytest.raises(ValueError):
        ChatTransport('x', url, 'model')


def test_atomic_extraction(incident):
    requests = []
    claims = WandbAdapter(chat([envelope(extraction())], requests)).extract(incident)
    assert [c.id for c in claims] == ['c1', 'c2']
    assert claims[0].statement_id == 'a'
    assert 'independently testable' in json.loads(requests[0].content)['messages'][0]['content']


@pytest.mark.parametrize('mutation', ['statement', 'quote', 'duplicate', 'empty', 'category', 'whitespace', 'too_many'])
def test_bad_extraction(incident, mutation):
    data = extraction()
    if mutation == 'statement': data['claims'][0]['statement_id'] = 'missing'
    if mutation == 'quote': data['claims'][0]['source_quote'] = 'fabricated'
    if mutation == 'duplicate': data['claims'].append(data['claims'][0])
    if mutation == 'empty': data['claims'] = []
    if mutation == 'category': data['claims'][0]['category'] = 'fault'
    if mutation == 'whitespace': data['claims'][0]['text'] = '  '
    if mutation == 'too_many': data['claims'] *= 17
    with pytest.raises(ProviderError):
        WandbAdapter(chat([envelope(data)])).extract(incident)


def test_cosmos_video_provenance_and_timestamps(incident, claim):
    requests = []
    adapter = cosmos([envelope(localization()), envelope(verification())], requests)
    windows = adapter.localize(incident, claim)
    verdict = adapter.verify(claim, windows)
    assert verdict.verdict == 'supported'
    assert verdict.evidence[0].start_seconds == 8
    assert verdict.evidence[0].end_seconds == 12
    assert 'sha256=abc' in verdict.provenance.source
    assert verdict.provenance.adapter == 'nvidia-cosmos-reason2'
    assert not verdict.provenance.is_mock
    assert verdict.explanation == 'Consistent with braking.'
    for request in requests:
        content = json.loads(request.content)['messages'][1]['content']
        assert content[1] == {'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,AAAA'}}


@pytest.mark.parametrize('start,end', [(-1, 3), (3, 3), (4, 3), (19, 21), (0, float('inf')), ('0', 3)])
def test_bad_localization(incident, claim, start, end):
    data = localization()
    data['windows'][0].update(start_seconds=start, end_seconds=end)
    with pytest.raises(ProviderError):
        cosmos([envelope(data)]).localize(incident, claim)


@pytest.mark.parametrize('visible,establishes,verdict', [('not_visible', True, 'contradicted'),
    ('visible', False, 'contradicted'), ('visible', False, 'supported'), ('visible', True, 'not_visible')])
def test_absence_never_contradiction(incident, claim, visible, establishes, verdict):
    data = localization()
    data['windows'][0]['visibility'] = visible
    adapter = cosmos([envelope(data), envelope(verification(establishes_claim=establishes, verdict=verdict, confidence=.9))])
    result = adapter.verify(claim, adapter.localize(incident, claim))
    assert result.verdict == 'not_visible'
    assert result.confidence is None
    assert all(w.visibility == 'not_visible' for w in result.evidence)
    assert 'absence is not contradiction' in result.explanation


def test_visible_opposite_can_contradict(incident, claim):
    adapter = cosmos([envelope(localization()), envelope(verification(verdict='contradicted'))])
    assert adapter.verify(claim, adapter.localize(incident, claim)).verdict == 'contradicted'


@pytest.mark.parametrize('changes', [{'confidence': 1.1}, {'establishes_claim': 'false'}, {'uncertainty': ''},
                                    {'verdict': 'probably'}, {'observation': None}])
def test_bad_verification(incident, claim, changes):
    adapter = cosmos([envelope(localization()), envelope(verification(**changes))])
    with pytest.raises(ProviderError):
        adapter.verify(claim, adapter.localize(incident, claim))


def test_report_preserves_evidence(incident, claim):
    adapter = cosmos([envelope(localization()), envelope(verification())])
    verdict = adapter.verify(claim, adapter.localize(incident, claim))
    report = WandbAdapter(chat([envelope({'claim_order': ['c1'], 'review_first': ['c1']})])).generate(
        incident, [claim], [verdict], [])
    assert report.verdicts == [verdict] and report.claims == [claim]
    assert all(label in report.summary for label in ('Observation', 'Inference', 'Uncertainty', 'wandb-inference', '8–12s'))
    assert report.legal_fault_determination == 'not_provided' and report.human_review_required


@pytest.mark.parametrize('order,review', [(['missing'], []), (['c1', 'c1'], []), (['c1'], ['missing'])])
def test_report_invalid_references(incident, claim, order, review):
    with pytest.raises(ProviderError):
        WandbAdapter(chat([envelope({'claim_order': order, 'review_first': review})])).generate(incident, [claim], [], [])


def probe(monkeypatch, duration='20.0'):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        assert Path(args[-1]).read_bytes() == b'video bytes'
        return SimpleNamespace(stdout=json.dumps({'streams': [{'duration': duration}]}))
    monkeypatch.setattr(subprocess, 'run', run)
    return calls


def test_probe_exact_uploaded_bytes(incident, tmp_path, monkeypatch):
    (tmp_path / 'clip.mp4').write_bytes(b'video bytes')
    calls = probe(monkeypatch)
    asset = LocalMedia(tmp_path).load(incident)
    assert asset.duration == 20 and len(asset.sha256) == 64
    assert asset.data_url == 'data:video/mp4;base64,dmlkZW8gYnl0ZXM='
    assert calls[0][1]['timeout'] == 15
    assert not Path(calls[0][0][-1]).exists()


@pytest.mark.parametrize('duration', ['NaN', 'inf', '0', '-1', '21', '121', 'N/A'])
def test_duration_failures(incident, tmp_path, monkeypatch, duration):
    (tmp_path / 'clip.mp4').write_bytes(b'video bytes')
    probe(monkeypatch, duration)
    with pytest.raises(ProviderError):
        LocalMedia(tmp_path).load(incident)


@pytest.mark.parametrize('uri', ['https://host/a.mp4', '../outside.mp4', 'file://remote/clip.mp4', 'mock://video', 'clip.txt'])
def test_unsupported_media(incident, tmp_path, uri):
    with pytest.raises(ProviderError):
        LocalMedia(tmp_path).load(incident.model_copy(update={'video_uri': uri}))


def test_missing_probe(incident, tmp_path, monkeypatch):
    (tmp_path / 'clip.mp4').write_bytes(b'video bytes')
    def fail(*args, **kwargs): raise FileNotFoundError('private path')
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(ProviderError, match='requires ffprobe'):
        LocalMedia(tmp_path).load(incident)


def test_real_end_to_end_mock_transport(incident, tmp_path, monkeypatch):
    (tmp_path / 'clip.mp4').write_bytes(b'video bytes')
    probe(monkeypatch)
    wandb = WandbAdapter(chat([envelope(extraction()), envelope({'claim_order': ['c2', 'c1'], 'review_first': ['c2']})]))
    runner = RealPipeline(wandb, chat([envelope(localization()), envelope(verification()),
                                      envelope(localization()), envelope(verification(establishes_claim=False))]), LocalMedia(tmp_path))
    report = runner.analyze(incident)
    assert not report.is_mock and not report.observations
    assert [v.verdict.value for v in report.verdicts] == ['supported', 'not_visible']


def test_real_rejects_mock_before_network(incident, tmp_path):
    runner = RealPipeline(WandbAdapter(chat([])), chat([]), LocalMedia(tmp_path))
    with pytest.raises(ProviderError, match='synthetic'):
        runner.analyze(incident.model_copy(update={'is_mock': True}))


def test_configuration(monkeypatch):
    monkeypatch.delenv('WANDB_INFERENCE_MODEL', raising=False)
    assert configured_pipeline('mock')
    with pytest.raises(ValueError, match='WANDB_INFERENCE_MODEL'):
        configured_pipeline('real')
    with pytest.raises(ValueError, match='mock or real'):
        configured_pipeline('typo')


def test_jobs_bounded_deduplicated_and_status(incident):
    entered, release, saved = Event(), Event(), Event()
    class Runner:
        def analyze(self, item):
            entered.set()
            assert release.wait(3)
            return item
    class Store:
        def save_report(self, report): saved.set()
    jobs = Jobs(Runner(), Store(), capacity=1)
    try:
        assert jobs.submit(incident).state == 'pending'
        assert entered.wait(1)
        assert jobs.submit(incident).state == 'running'
        with pytest.raises(QueueFull):
            jobs.submit(incident.model_copy(update={'id': 'other'}))
        release.set()
        jobs.executor.shutdown(wait=True)
        assert jobs.submit(incident).state == 'completed'
        assert saved.is_set()
    finally:
        release.set()
        jobs.close()


def test_real_api_nonblocking_and_safe_failure(incident, monkeypatch):
    from witness_api.main import create_app
    entered, release = Event(), Event()
    class Runner:
        def analyze(self, item):
            entered.set()
            assert release.wait(3)
            raise RuntimeError('secret provider credentials')
    class Store:
        def get_incident(self, id): return incident if id == incident.id else None
        def get_report(self, id): return None
        def save_report(self, report): raise AssertionError('must not save')
    monkeypatch.setenv('WITNESS_ANALYSIS_MODE', 'real')
    app = create_app(Store(), Runner())
    with TestClient(app) as client:
        try:
            result = client.post('/incidents/real-1/analyze')
            assert result.status_code == 200 and result.json()['state'] == 'pending'
            assert entered.wait(1)
            assert client.get('/health').json()['analysis_mode'] == 'real'
            assert client.post('/incidents/real-1/analyze').json()['state'] == 'running'
            assert client.get('/incidents/real-1/results').status_code == 409
        finally:
            release.set()
            app.state.jobs.executor.shutdown(wait=True)
        failure = client.post('/incidents/real-1/analyze').json()
        assert failure['state'] == 'failed' and 'secret' not in failure['detail']


def test_response_size_limit():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 1_000_001))
    c = ChatTransport('provider', 'https://provider.example/v1', 'model', transport=transport)
    with pytest.raises(ProviderError, match='size limit'):
        c.complete('x', {}, ReportOutline)


@pytest.mark.parametrize('payload', [b'', b'123456'])
def test_media_size_limit(incident, tmp_path, payload):
    (tmp_path / 'clip.mp4').write_bytes(payload)
    with pytest.raises(ProviderError, match='size limit'):
        LocalMedia(tmp_path, max_bytes=5).load(incident)


def test_probed_duration_is_strict_bound(incident, claim):
    data = localization()
    data['windows'][0]['end_seconds'] = 20.0
    adapter = CosmosAdapter(chat([envelope(data)]), VideoAsset('clip.mp4', 19.99, 'data:video/mp4;base64,AAAA', 'abc'))
    with pytest.raises(ProviderError, match='actual video duration'):
        adapter.localize(incident, claim)


def test_bad_localization_stops_before_verification(incident, tmp_path, monkeypatch):
    (tmp_path / 'clip.mp4').write_bytes(b'video bytes')
    probe(monkeypatch)
    requests = []
    data = localization()
    data['windows'][0]['end_seconds'] = 30.0
    runner = RealPipeline(WandbAdapter(chat([envelope(extraction())])),
        chat([envelope(data)], requests), LocalMedia(tmp_path))
    with pytest.raises(ProviderError):
        runner.analyze(incident)
    assert len(requests) == 1


def test_failure_preserves_saved_report_and_safe_reason(incident):
    class Runner:
        def analyze(self, item): raise ProviderError('cosmos: request timed out; retry limit exhausted')
    class Store:
        saved = 'prior report'
        def save_report(self, report): self.saved = report
    store = Store()
    jobs = Jobs(Runner(), store)
    try:
        jobs.submit(incident)
        jobs.executor.shutdown(wait=True)
        result = jobs.submit(incident)
        assert result.state == 'failed' and 'timed out' in result.detail
        assert store.saved == 'prior report'
    finally:
        jobs.close()
