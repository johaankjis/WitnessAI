"""Exercise the mock demo on a running API; writes its deterministic report."""
import argparse
import json
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:8000')
args = parser.parse_args()
for method, path in [('GET', '/health'), ('GET', '/incidents/demo-001'),
                     ('POST', '/incidents/demo-001/analyze'),
                     ('GET', '/incidents/demo-001/status'), ('GET', '/incidents/demo-001/results')]:
    with urlopen(Request(args.base.rstrip('/') + path, method=method), timeout=15) as response:
        data = json.load(response)
        assert response.status == 200
        if path == '/health':
            assert data['analysis_mode'] == 'mock', 'Smoke script requires mock mode'
        if path.endswith(('/status', '/analyze')):
            assert data['state'] == 'completed'
        if path.endswith('/results'):
            assert data['is_mock'] and data['human_review_required']
            assert len(data['claims']) == 5
            assert all(o['provenance']['adapter'] == 'witness-vision-mock' for o in data['observations'])
        print(method, path, response.status)
