"""Run ONLY from the VM via kubectl exec inside the actual app pod.

Performs fresh inference on the authorized VSS segment, then enables the local
runtime gate for one hour. No credentials, URLs or model output are printed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from live_inference import GPUSettings, LiveError, PREFLIGHT_FILE, analyze, read_video


def main() -> int:
    if sys.platform != 'linux' or not os.getenv('KUBERNETES_SERVICE_HOST'):
        print('FAIL: Run from the VM using kubectl exec inside the application pod.')
        return 1
    try:
        # A failed recheck must not leave an earlier successful gate usable.
        PREFLIGHT_FILE.unlink(missing_ok=True)
        import main as application
        if application.MODE != 'vast' or not application.INCIDENT.get('footage_permitted'):
            raise LiveError('Preflight requires authorized VAST footage')
        settings = GPUSettings.from_env()
        incident = application.INCIDENT
        metadata = application.vss.segment_metadata(incident['source'])
        application.validate_evidence(metadata, metadata=True)
        video = read_video(application.vss, incident['source'])
        result = asyncio.run(analyze(settings, video, incident))
        if result['status'] != 'ok':
            for name in ('cosmos', 'yolo'):
                print(f"{name}: {result[name]['status']}; {result[name].get('error', 'validated response')}")
            return 1
        receipt = {'verified_at': time.time(), 'fingerprint': settings.fingerprint(incident['source'])}
        temporary = PREFLIGHT_FILE.with_suffix('.tmp')
        with open(temporary, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as out:
            json.dump(receipt, out)
        os.replace(temporary, PREFLIGHT_FILE)
        print('PASS: both GPU services completed authenticated inference from this pod; gate valid for one hour.')
        return 0
    except Exception:
        # Never print exceptions from transport/configuration: they can contain credentials.
        print('FAIL: authorized video retrieval or GPU configuration failed. No gate issued.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
