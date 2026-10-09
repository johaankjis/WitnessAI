"""Offline connectivity boundary tests; no credentials, media, or production records."""
import json

import httpx
import pytest

from witness_api.config import cosmos_api_key
from witness_api.provider_io import ProviderError
from witness_api.provider_smoke import main, probe


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    for name in ('COSMOS_BASE_URL', 'COSMOS_MODEL', 'COSMOS_API_KEY', 'NVIDIA_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('COSMOS_BASE_URL', 'https://provider.example/v1')
    monkeypatch.setenv('COSMOS_MODEL', 'nvidia/cosmos-reason2-8b')
    monkeypatch.setenv('NVIDIA_API_KEY', 'test-only-secret')


def test_alias_precedence(monkeypatch):
    assert cosmos_api_key() == 'test-only-secret'
    monkeypatch.setenv('COSMOS_API_KEY', 'explicit-test-key')
    assert cosmos_api_key() == 'explicit-test-key'
    monkeypatch.setenv('COSMOS_API_KEY', ' ')
    assert cosmos_api_key() == 'test-only-secret'


def test_text_only_probe():
    def handle(request):
        assert str(request.url) == 'https://provider.example/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-only-secret'
        body = json.loads(request.content)
        assert body['model'] == 'nvidia/cosmos-reason2-8b'
        assert body['stream'] is False
        assert all(isinstance(m['content'], str) for m in body['messages'])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': '{"status":"ok"}'}}]})
    probe(httpx.MockTransport(handle))


@pytest.mark.parametrize('code', [301, 400, 401, 403, 404, 429, 500, 503])
def test_safe_errors_without_retry(code):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(code, text='test-only-secret private provider body')
    with pytest.raises(ProviderError, match=f'HTTP {code}') as error:
        probe(httpx.MockTransport(handle))
    assert 'secret' not in str(error.value)
    assert 'private' not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize('content', ['not JSON', '{"status":"wrong"}',
    '{"status":"ok","extra":true}', '<think>trace</think>{"status":"ok"}'])
def test_invalid_structured_reply(content):
    with pytest.raises(ProviderError, match='invalid structured output'):
        probe(httpx.MockTransport(lambda _: httpx.Response(200, json={
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]})))


@pytest.mark.parametrize('exception', [httpx.ConnectError, httpx.ReadTimeout])
def test_network_errors(exception):
    def handle(request):
        raise exception('private details', request=request)
    with pytest.raises(ProviderError, match='retry limit exhausted'):
        probe(httpx.MockTransport(handle))


@pytest.mark.parametrize('name,value', [('COSMOS_BASE_URL', ''), ('COSMOS_MODEL', ''),
    ('NVIDIA_API_KEY', ''), ('COSMOS_MODEL', 'nvidia/cosmos3-nano-reasoner'),
    ('COSMOS_BASE_URL', 'http://remote.example/v1')])
def test_blocked_before_network(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    def unexpected(request):
        pytest.fail('Blocked configuration must not contact provider')
    with pytest.raises(ProviderError):
        probe(httpx.MockTransport(unexpected))


def test_cli_reports_missing_configuration(monkeypatch, capsys):
    monkeypatch.delenv('COSMOS_BASE_URL')
    assert main() == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'blocked'
