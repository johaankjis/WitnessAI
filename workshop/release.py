"""Offline allowlisted packaging and VM deployment planning; never deploys or contacts VSS."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from config import INTERNAL_VSS_URL, mode, vast_settings

ROOT = Path(__file__).resolve().parent
RUNTIME = ('main.py', 'config.py', 'fixtures.py', 'vss_client.py', 'verdicts.py',
           'incident.py', 'wandb_adapter.py', 'live_inference.py', 'live_preflight.py', 'index.html', 'app.js', 'styles.css', 'requirements.txt')
EXTRAS = ('release.py', 'README.md', 'DEPLOYMENT.md', 'TASK-005C.md', 'TASK-006B.md', 'TASK-007.md', 'deployment-env.json', 'start-mac.sh')
# Leave substantial room below Kubernetes' 1 MiB ConfigMap limit.
MAX_CONFIGMAP = 750_000
MAX_PACKAGE = 900_000


def sources(root: Path = ROOT) -> dict[str, str]:
    data = {}
    for name in RUNTIME:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Required regular file missing: {name}')
        data[name] = path.read_text()
        if re.search(r'(?i)(?:X-Amz-Signature=|-----BEGIN .*PRIVATE KEY|https?://[^\s/]+:[^\s/]+@)', data[name]):
            raise ValueError(f'Potential credential material in {name}')
    if len(json.dumps(data).encode()) > MAX_CONFIGMAP:
        raise ValueError('Source exceeds conservative ConfigMap size budget')
    return data


def package(root: Path, output: Path) -> dict:
    sources(root)
    names = list(RUNTIME + EXTRAS) + sorted(str(p.relative_to(root)) for p in (root / 'tests').glob('*.py'))
    payload = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Required regular file missing: {name}')
        payload[name] = path.read_bytes()
    if sum(map(len, payload.values())) > MAX_PACKAGE:
        raise ValueError('Uncompressed release exceeds size budget')
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in payload.items()}
    payload['MANIFEST.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    # tar, not gzip: fixed metadata makes identical source produce identical bytes.
    with tarfile.open(output, 'w') as archive:
        for name, value in sorted(payload.items()):
            info = tarfile.TarInfo('witness-workshop/' + name)
            info.size = len(value)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(value))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n')
    return {'archive': str(output), 'sha256': digest, 'source_bytes': sum(len(v.encode()) for v in sources(root).values()),
            'archive_bytes': output.stat().st_size, 'files': len(payload)}


def verify(root: Path) -> None:
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    expected = set(RUNTIME + EXTRAS)
    if not expected.issubset(manifest) or any(
        name not in expected and not re.fullmatch(r'tests/[a-zA-Z0-9_]+\.py', name) for name in manifest
    ):
        raise ValueError('Unexpected release manifest entries')
    for name, digest in manifest.items():
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Release checksum mismatch: {name}')
    sources(root)


def plan(root: Path, deployment: dict, service: dict, ingress: dict,
         container_name: str, volume_name: str, secret: str) -> tuple[dict, dict]:
    """Validate the existing Team 6 app shape; build immutable source + replacement spec."""
    data = sources(root)
    for obj, kind in [(deployment, 'Deployment'), (service, 'Service'), (ingress, 'Ingress')]:
        if obj.get('kind') != kind or obj.get('metadata', {}).get('namespace') != 'team-6':
            raise ValueError(f'Expected Team 6 {kind}')
    spec = deployment['spec']['template']['spec']
    container = next((c for c in spec['containers'] if c['name'] == container_name), None)
    volume = next((v for v in spec['volumes'] if v['name'] == volume_name), None)
    if not container or not volume or 'configMap' not in volume:
        raise ValueError('Named container/source ConfigMap volume not found')
    mounts = [m for m in container.get('volumeMounts', []) if m['name'] == volume_name]
    if len(mounts) != 1 or 'subPath' in mounts[0] or 'subPathExpr' in mounts[0]:
        raise ValueError('Requires one whole-directory source ConfigMap mount')
    mount = mounts[0]['mountPath']
    if not mount.startswith('/') or mount in {'/', '/usr', '/etc', '/bin'}:
        raise ValueError('Unsafe source mount path')
    labels = deployment['spec']['template']['metadata']['labels']
    selector = service['spec'].get('selector', {})
    if not selector or any(labels.get(k) != v for k, v in selector.items()):
        raise ValueError('Service selector does not match application')
    ports = service['spec']['ports']
    named_ports = {p.get('name'): p['containerPort'] for p in container.get('ports', [])}
    def targets_app(port: dict) -> bool:
        target = port.get('targetPort', port['port'])
        return target == 8080 or named_ports.get(target) == 8080
    app_ports = [p for p in ports if targets_app(p)]
    if not app_ports:
        raise ValueError('Service must target container port 8080')
    paths = [p for r in ingress['spec'].get('rules', []) for p in r.get('http', {}).get('paths', [])]
    def app_route(p: dict) -> bool:
        backend = p.get('backend', {}).get('service', {})
        port = backend.get('port', {})
        return (p.get('path') in {'/app', '/app/', '/app(/|$)(.*)'}
                and backend.get('name') == service['metadata']['name']
                and any(port.get('number') == s['port'] or
                        (port.get('name') and port['name'] == s.get('name')) for s in app_ports))
    if not any(app_route(p) for p in paths):
        raise ValueError('Ingress /app does not route to the application Service')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', secret):
        raise ValueError('Invalid existing Secret name')
    revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    cm_name = 'witness-source-' + revision
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': cm_name, 'namespace': 'team-6'},
          'immutable': True, 'data': data}
    volume['configMap'] = {'name': cm_name}
    container['workingDir'] = mount
    container['command'] = ['python', 'main.py']
    container['args'] = []
    env = [e for e in container.get('env', []) if e['name'] not in
           {'WITNESS_WORKSHOP_MODE', 'VSS_URL', 'VSS_USERNAME', 'VSS_PASSWORD', 'PORT', 'HOST'}]
    env += [{'name': k, 'value': v} for k, v in
            {'WITNESS_WORKSHOP_MODE': 'vast', 'HOST': '0.0.0.0', 'PORT': '8080',
             'VSS_URL': INTERNAL_VSS_URL}.items()]
    env += [{'name': k, 'valueFrom': {'secretKeyRef': {'name': secret, 'key': k}}}
            for k in ['VSS_USERNAME', 'VSS_PASSWORD']]
    container['env'] = env
    # Do not serialize live metadata/status or any old literal secret values.
    result = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
              'metadata': {'name': deployment['metadata']['name'], 'namespace': 'team-6'},
              'spec': deployment['spec']}
    if len(json.dumps(cm).encode()) > MAX_CONFIGMAP:
        raise ValueError('Serialized ConfigMap exceeds budget')
    return cm, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['package', 'verify', 'preflight'])
    parser.add_argument('--output', type=Path, default=Path('/tmp/witness-workshop.tar'))
    parser.add_argument('--vm', action='store_true', help='Validate VM environment and emit deployment plan')
    for name in ['deployment', 'service', 'ingress']:
        parser.add_argument('--' + name, type=Path)
    for name in ['container', 'volume', 'secret']:
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ required')
    try:
        if args.action == 'package':
            print(json.dumps(package(ROOT, args.output), indent=2))
        elif args.action == 'verify':
            verify(ROOT)
            print('Release manifest verified')
        else:
            data = sources()
            if args.vm:
                if mode() != 'vast':
                    raise ValueError('VM requires WITNESS_WORKSHOP_MODE=vast')
                url, _, _, _ = vast_settings()  # presence + syntax only; no network
                if url != INTERNAL_VSS_URL:
                    raise ValueError("VM requires the Team 6 internal VSS service URL")
                if not all([args.deployment, args.service, args.ingress, args.container, args.volume, args.secret]):
                    raise ValueError('VM preflight requires deployment/service/ingress JSON, container, volume, secret')
                cm, deploy = plan(ROOT, json.loads(args.deployment.read_text()),
                                  json.loads(args.service.read_text()), json.loads(args.ingress.read_text()),
                                  args.container, args.volume, args.secret)
                args.output.mkdir(exist_ok=True)
                (args.output / 'configmap.json').write_text(json.dumps(cm, indent=2))
                # Generated deployment specs are VM-local and may contain pre-existing env values.
                path = args.output / 'deployment.json'
                path.touch(mode=0o600, exist_ok=False)
                path.write_text(json.dumps(deploy, indent=2))
            print(f'PASS: {len(data)} flat runtime files; {len(json.dumps(data).encode())} serialized bytes; no network used')
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, f'Preflight/package failed: {exc}\n')


if __name__ == '__main__':
    main()
