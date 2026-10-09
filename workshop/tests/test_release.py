from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

import pytest
from release import ROOT, RUNTIME, package, plan, sources, verify


def app_objects():
    deployment = {'kind': 'Deployment', 'metadata': {'name': 'app', 'namespace': 'team-6'},
        'spec': {'selector': {'matchLabels': {'app': 'app'}}, 'template': {
            'metadata': {'labels': {'app': 'app'}}, 'spec': {
                'containers': [{'name': 'app', 'image': 'existing-image',
                    'volumeMounts': [{'name': 'source', 'mountPath': '/workshop'}]}],
                'volumes': [{'name': 'source', 'configMap': {'name': 'old-source'}}]}}}}
    service = {'kind': 'Service', 'metadata': {'name': 'app', 'namespace': 'team-6'},
               'spec': {'selector': {'app': 'app'}, 'ports': [{'port': 80, 'targetPort': 8080}]}}
    ingress = {'kind': 'Ingress', 'metadata': {'name': 'app', 'namespace': 'team-6'},
               'spec': {'rules': [{'http': {'paths': [{'path': '/app', 'backend': {
                   'service': {'name': 'app', 'port': {'number': 80}}}}]}}]}}
    return deployment, service, ingress


def test_package_allowlist_and_reproducibility(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache'))
    for name in ['.env', 'credentials.json', 'footage.mp4', 'weights.pt', 'generated.json']:
        (root / name).write_text('MUST NOT SHIP')
    (root / 'node_modules').mkdir()
    (root / 'node_modules' / 'package.js').write_text('MUST NOT SHIP')
    a, b = tmp_path / 'a.tar', tmp_path / 'b.tar'
    package(root, a)
    package(root, b)
    assert a.read_bytes() == b.read_bytes()
    with tarfile.open(a) as archive:
        assert not any(name.endswith(('.env', '.mp4', '.pt', 'credentials.json', 'generated.json')) for name in archive.getnames())
        archive.extractall(tmp_path / 'unpacked', filter='data')
    extracted = tmp_path / 'unpacked' / 'witness-workshop'
    verify(extracted)
    (extracted / 'main.py').write_text('tampered')
    with pytest.raises(ValueError, match='checksum'):
        verify(extracted)


def test_size_and_symlink_rejection(tmp_path):
    for name in RUNTIME:
        (tmp_path / name).write_text((ROOT / name).read_text())
    (tmp_path / 'main.py').write_text('x' * 750_001)
    with pytest.raises(ValueError, match='size'):
        sources(tmp_path)
    (tmp_path / 'main.py').unlink()
    (tmp_path / 'main.py').symlink_to(ROOT / 'main.py')
    with pytest.raises(ValueError, match='regular file'):
        sources(tmp_path)


def test_plan_keeps_image_and_uses_immutable_source():
    cm, deployment = plan(ROOT, *app_objects(), 'app', 'source', 'vss-secret')
    assert cm['immutable'] is True
    container = deployment['spec']['template']['spec']['containers'][0]
    assert container['image'] == 'existing-image'
    assert container['workingDir'] == '/workshop'
    env = {e['name']: e for e in container['env']}
    assert env['WITNESS_WORKSHOP_MODE']['value'] == 'vast'
    assert env['VSS_PASSWORD']['valueFrom']['secretKeyRef']['name'] == 'vss-secret'
    assert len(json.dumps(cm).encode()) < 750_000


@pytest.mark.parametrize('failure', ['namespace', 'selector', 'port', 'path', 'subpath', 'volume', 'container'])
def test_plan_rejects_incompatible_app(failure):
    deployment, service, ingress = app_objects()
    spec = deployment['spec']['template']['spec']
    if failure == 'namespace':
        deployment['metadata']['namespace'] = 'team-7'
    elif failure == 'selector':
        service['spec']['selector'] = {'other': 'app'}
    elif failure == 'port':
        service['spec']['ports'][0]['targetPort'] = 9000
    elif failure == 'path':
        ingress['spec']['rules'][0]['http']['paths'][0]['path'] = '/other'
    elif failure == 'subpath':
        spec['containers'][0]['volumeMounts'][0]['subPath'] = 'main.py'
    elif failure == 'volume':
        spec['volumes'][0] = {'name': 'source', 'emptyDir': {}}
    elif failure == 'container':
        spec['containers'][0]['name'] = 'other'
    with pytest.raises(ValueError):
        plan(ROOT, deployment, service, ingress, 'app', 'source', 'vss-secret')
