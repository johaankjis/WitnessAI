"""Text-only Cosmos readiness probe; no app, media, detector or storage construction."""
import json
import os
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict

from .config import cosmos_api_key
from .provider_io import ChatTransport, ProviderError


class SmokeReply(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['ok']


def probe(transport: httpx.BaseTransport | None = None) -> None:
    base = os.getenv('COSMOS_BASE_URL', '').strip()
    model = os.getenv('COSMOS_MODEL', '').strip()
    if not base or not model:
        raise ProviderError('Set COSMOS_BASE_URL and COSMOS_MODEL from provider documentation or API discovery')
    # Never test a replacement model as though it were Reason 2.
    if model not in {'nvidia/cosmos-reason2-8b', 'nvidia/Cosmos-Reason2-8B'}:
        raise ProviderError('This probe requires Cosmos Reason 2 8B; other models need a compatibility decision')
    key = cosmos_api_key()
    if urlsplit(base).hostname not in {'localhost', '127.0.0.1', '::1'} and not key:
        raise ProviderError('Remote probe requires NVIDIA_API_KEY or COSMOS_API_KEY in the process environment')
    try:
        chat = ChatTransport('cosmos', base, model, key, timeout=30, retries=0, transport=transport)
    except ValueError:
        raise ProviderError('Invalid Cosmos endpoint configuration') from None
    chat.complete('Connectivity test only. Return exactly {"status":"ok"}.',
                  {'purpose': 'text-only provider readiness; no incident evidence'}, SmokeReply)


def main() -> int:
    try:
        probe()
    except ProviderError as exc:
        print(json.dumps({'status': 'blocked', 'detail': str(exc)}))
        return 1
    print(json.dumps({'status': 'passed', 'detail':
        'Configured model accepted a text request and returned valid JSON; video readiness is unverified'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
