"""Bounded, server-only GPU adapters. No inference output enters indexed evidence."""
from __future__ import annotations

import asyncio
import base64
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx
import requests

MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
GPU_TIMEOUT_SECONDS = 60
COSMOS_MODEL = "nvidia/cosmos3-nano-reasoner"
YOLO_MODEL = "YOLO11s"
PREFLIGHT_FILE = Path('/tmp/witness-live-preflight.json')


class LiveError(Exception):
    """Only static, credential-free messages may cross this boundary."""


@dataclass(frozen=True)
class GPUSettings:
    cosmos_url: str
    yolo_url: str
    token: str = field(repr=False)

    @classmethod
    def from_env(cls) -> GPUSettings:
        urls = [os.getenv(key, '').rstrip('/') for key in ('COSMOS_GPU_URL', 'YOLO_GPU_URL')]
        for value in urls:
            try:
                parsed = urlsplit(value)
                valid = (parsed.scheme in {'http', 'https'} and parsed.hostname
                         and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
                         and (parsed.port is None or 0 < parsed.port <= 65535))
            except ValueError:
                valid = False
            if not valid:
                raise LiveError('GPU base URLs are missing or invalid')
        token = os.getenv('GPU_BEARER_TOKEN', '')
        if not token or any(not 33 <= ord(c) <= 126 for c in token):
            raise LiveError('GPU authentication is not configured')
        return cls(*urls, token)

    def fingerprint(self, source: str) -> str:
        return hashlib.sha256(json.dumps([self.cosmos_url, self.yolo_url, self.token, source]).encode()).hexdigest()

    def require_preflight(self, source: str) -> None:
        if os.getenv('WITNESS_LIVE_INFERENCE_ENABLED') != 'true':
            raise LiveError('Live inference is disabled')
        try:
            receipt = json.loads(PREFLIGHT_FILE.read_text())
            age = time.time() - receipt['verified_at']
            if receipt['fingerprint'] != self.fingerprint(source) or not 0 <= age < 3600:
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise LiveError('Required pod-side GPU preflight is missing or expired (one hour)') from None


class RequestLimit:
    """Single-process workshop budget: one running request, 30s cooldown, 20/hour."""
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.starts: deque[float] = deque()

    @contextmanager
    def reserve(self) -> Iterator[None]:
        if not self.lock.acquire(blocking=False):
            raise LiveError('Live inference is busy; retry later')
        try:
            now = time.monotonic()
            while self.starts and now - self.starts[0] >= 3600:
                self.starts.popleft()
            if len(self.starts) >= 20 or (self.starts and now - self.starts[-1] < 30):
                raise LiveError('Live inference request limit reached; retry later')
            self.starts.append(now)
            yield
        finally:
            self.lock.release()


def read_video(vss: Any, source: str) -> bytes:
    """Reuse authenticated VSS retrieval; no caller-supplied URL or video bytes."""
    response = vss.open_stream(source)
    try:
        if response.status_code != 200:
            raise LiveError('VSS did not return the complete video')
        content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
        if content_type not in {'video/mp4', 'application/octet-stream'}:
            raise LiveError('VSS returned an unsupported video type')
        length = response.headers.get('Content-Length')
        if length is not None and (not length.isdigit() or not 0 < int(length) <= MAX_VIDEO_BYTES):
            raise LiveError('Video exceeds the 20 MiB limit or has invalid length')
        data = bytearray()
        deadline = time.monotonic() + 30
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if time.monotonic() > deadline:
                raise LiveError('Video retrieval timed out')
            if len(data) + len(chunk) > MAX_VIDEO_BYTES:
                raise LiveError('Video exceeds the 20 MiB limit')
            data.extend(chunk)
        if not data or (length is not None and len(data) != int(length)):
            raise LiveError('VSS returned empty or incomplete video')
        if len(data) < 12 or data[4:8] != b'ftyp':
            raise LiveError('VSS did not return MP4 video')
        return bytes(data)
    except requests.RequestException:
        raise LiveError('Video retrieval failed or timed out') from None
    finally:
        response.close()


async def _post(settings: GPUSettings, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Disable redirects and environment proxy inheritance to keep credentials at the configured host.
    async with httpx.AsyncClient(timeout=httpx.Timeout(55, connect=5), follow_redirects=False,
                                 trust_env=False) as client:
        async with client.stream('POST', url, json=payload,
                                 headers={'Authorization': f'Bearer {settings.token}'}) as response:
            if response.status_code in {401, 403}:
                raise LiveError('GPU authentication rejected')
            if response.status_code != 200:
                raise LiveError(f'GPU service returned HTTP {response.status_code}')
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise LiveError('GPU response exceeds size limit')
                data.extend(chunk)
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result


async def _infer(settings: GPUSettings, service: str, encoded: str, filename: str) -> dict[str, Any]:
    model = COSMOS_MODEL if service == 'cosmos' else YOLO_MODEL
    row: dict[str, Any] = {'model': model, 'status': 'error', 'live_inference': False}
    if service == 'cosmos':
        url = settings.cosmos_url + '/v1/chat/completions'
        payload = {'model': COSMOS_MODEL, 'max_tokens': 512, 'temperature': 0,
                   'messages': [{'role': 'user', 'content': [
                       {'type': 'text', 'text': 'Describe only visible objects and actions in this video. '
                        'State uncertainty and unseen signals. Do not assign fault or judge driver claims.'},
                       {'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,' + encoded}},
                   ]}]}
    else:
        url = settings.yolo_url + '/v1/infer'
        payload = {'video_base64': encoded, 'filename': filename, 'include_frames': False}
    try:
        data = await asyncio.wait_for(_post(settings, url, payload), timeout=GPU_TIMEOUT_SECONDS)
        if service == 'cosmos':
            description = data['choices'][0]['message']['content']
            if not isinstance(description, str) or not description.strip() or len(description) > 16000:
                raise ValueError()
            row['description'] = description
        else:
            classes, counts = data['object_classes'], data['object_counts']
            if isinstance(classes, str):
                classes = [value.strip() for value in classes.split(',') if value.strip()]
            if (data.get('perception_ok') is not True or not isinstance(classes, list)
                    or len(classes) > 200 or any(not isinstance(v, str) or not 0 < len(v) <= 100 for v in classes)
                    or not isinstance(counts, dict) or len(counts) > 200
                    or any(not isinstance(k, str) or not 0 < len(k) <= 100 or type(v) is not int or v < 0
                           for k, v in counts.items())):
                raise ValueError()
            row.update(perception_ok=True, object_classes=classes, object_counts=counts)
        row.update(status='ok', live_inference=True)
    except (asyncio.TimeoutError, httpx.TimeoutException):
        row['error'] = 'GPU inference timed out'
    except httpx.RequestError:
        row['error'] = 'GPU service could not be reached'
    except LiveError as exc:
        row['error'] = str(exc)
    except (ValueError, KeyError, IndexError, TypeError):
        row['error'] = 'GPU returned an invalid inference response'
    return row


async def analyze(settings: GPUSettings, video: bytes, incident: dict[str, Any]) -> dict[str, Any]:
    encoded = base64.b64encode(video).decode('ascii')
    cosmos, yolo = await asyncio.gather(*[
        _infer(settings, service, encoded, incident['segment_filename']) for service in ('cosmos', 'yolo')])
    successes = sum(row['status'] == 'ok' for row in (cosmos, yolo))
    return {'status': 'ok' if successes == 2 else 'partial' if successes else 'error',
            'live_inference': bool(successes), 'attempted_live_inference': True,
            'provenance': {'live_inference': bool(successes), 'synthetic': False,
                           'retrieval': 'authorized VSS segment', 'independent_corroboration': False},
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'incident_id': incident['id'], 'source': incident['source'],
            'evidence_window_sec': incident['evidence_window_sec'],
            'video_sha256': hashlib.sha256(video).hexdigest(),
            'cosmos': cosmos, 'yolo': yolo,
            'human_review_required': True, 'verdicts_changed': False,
            'uncertainty': 'Fresh model observations may be incorrect; not independent corroboration. '
                           'Unseen signals remain not_visible. Human review required. No fault determination.'}
