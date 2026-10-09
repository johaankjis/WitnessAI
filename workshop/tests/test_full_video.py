"""Offline parent playback regression tests; all upstream traffic is mocked."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
import main
from incident import INCIDENT
from vss_client import VSSAPIError, VSSAuthError


@pytest.fixture
def media(monkeypatch):
    monkeypatch.setattr(main, 'MODE', 'vast')
    monkeypatch.setattr(main, 'INCIDENT', dict(INCIDENT))
    upstream = MagicMock(status_code=206, headers={
        'Content-Type': 'binary/octet-stream', 'Content-Range': 'bytes 0-1023/31421138',
        'Content-Length': '1024', 'Location': 'https://private/?token=SECRET',
        'Set-Cookie': 'SECRET', 'X-Private': 'SECRET'})
    upstream.iter_content.return_value = [b'x' * 1024]
    vss = MagicMock()
    vss.configured.return_value = True
    vss.open_stream.return_value = upstream
    monkeypatch.setattr(main, 'vss', vss)
    return TestClient(main.app), vss, upstream


@pytest.mark.parametrize('prefix', ['', '/app'])
@pytest.mark.parametrize('range_value', ['bytes=0-1023', 'bytes=0-', 'bytes=-1024'])
def test_parent_range(media, prefix, range_value):
    client, vss, upstream = media
    response = client.get(prefix + '/api/media/full', headers={'Range': range_value})
    assert response.status_code == 206
    assert response.content == b'x' * 1024
    assert response.headers['content-type'] == 'video/mp4'
    assert response.headers['content-range'] == 'bytes 0-1023/31421138'
    assert response.headers['content-length'] == '1024'
    assert response.headers['accept-ranges'] == 'bytes'
    vss.open_stream.assert_called_once_with(INCIDENT['original_video'], range_header=range_value)
    upstream.close.assert_called_once()
    assert 'SECRET' not in str(response.headers)
    assert 's3://' not in str(response.headers)


def test_whole_video_and_segment_remain_separate(media):
    client, vss, upstream = media
    upstream.status_code = 200
    upstream.headers = {'Content-Length': '1024'}
    assert client.get('/api/media/full').status_code == 200
    vss.open_stream.assert_called_with(INCIDENT['original_video'], range_header=None)
    assert client.get('/api/media/stream').status_code == 200
    vss.open_stream.assert_called_with(INCIDENT['source'], range_header=None)


@pytest.mark.parametrize('value', ['bytes=9-2', 'bytes=-0', 'bytes=-', 'bytes=0-1,3-4', 'items=0-1', 'bytes=abc'])
def test_bad_ranges_do_not_contact_upstream(media, value):
    client, vss, _ = media
    assert client.get('/api/media/full', headers={'Range': value}).status_code == 400
    vss.open_stream.assert_not_called()


@pytest.mark.parametrize('query', ['?source=s3://other', '?token=SECRET', '?url=https://other'])
def test_no_source_or_token_override(media, query):
    client, vss, _ = media
    assert client.get('/api/media/full' + query).status_code == 403
    vss.open_stream.assert_not_called()


def test_authorization_and_fixture(media, monkeypatch):
    client, vss, _ = media
    main.INCIDENT['footage_permitted'] = False
    assert client.get('/api/media/full').status_code == 403
    main.INCIDENT['footage_permitted'] = True
    vss.configured.return_value = False
    assert client.get('/api/media/full').status_code == 503
    monkeypatch.setattr(main, 'MODE', 'fixture')
    assert client.get('/api/media/full').status_code == 404
    vss.open_stream.assert_not_called()


@pytest.mark.parametrize('error,status', [
    (VSSAuthError('SECRET s3://private'), 502),
    (VSSAPIError('SECRET https://private?token=x', 403, 'SECRET'), 502),
    (VSSAPIError('SECRET', 416), 416),
])
def test_sanitized_failures(media, error, status):
    client, vss, _ = media
    vss.open_stream.side_effect = error
    response = client.get('/api/media/full')
    assert response.status_code == status
    assert 'SECRET' not in response.text
    assert 's3://' not in response.text
    assert 'token=' not in response.text


@pytest.mark.parametrize('headers', [
    {'Content-Length': 'SECRET'},
    {'Content-Range': 'https://private?token=SECRET'},
    {'Content-Range': 'bytes 0-5/3'},
    {'Content-Range': 'bytes 0-5/100', 'Content-Length': '7'},
])
def test_invalid_upstream_range_is_closed(media, headers):
    client, _, upstream = media
    upstream.headers = headers
    response = client.get('/api/media/full')
    assert response.status_code == 502
    assert 'SECRET' not in response.text
    upstream.close.assert_called_once()
