"""Bounded local MP4 acquisition; probe exactly the bytes sent to Cosmos."""
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
from witness_contracts import Incident
from .provider_io import ProviderError


@dataclass(frozen=True)
class VideoAsset:
    uri: str
    duration: float
    data_url: str
    sha256: str


class LocalMedia:
    def __init__(self, root: Path, ffprobe: str = 'ffprobe', max_bytes: int = 25_000_000):
        self.root, self.ffprobe, self.max_bytes = root.resolve(), ffprobe, max_bytes

    def resolve(self, incident: Incident) -> Path:
        uri = urlsplit(incident.video_uri)
        if uri.scheme not in ('', 'file') or uri.netloc or uri.query or uri.fragment:
            raise ProviderError('media: only local MP4 files under WITNESS_MEDIA_ROOT are supported')
        path = Path(unquote(uri.path))
        path = (path if path.is_absolute() else self.root / path).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() != '.mp4':
            raise ProviderError('media: file must be MP4 within WITNESS_MEDIA_ROOT')
        if not path.is_file():
            raise ProviderError("media: file unavailable")
        return path

    def load(self, incident: Incident) -> VideoAsset:
        if incident.is_mock:
            raise ProviderError('real providers cannot analyze synthetic incidents')
        path = self.resolve(incident)
        try:
            with path.open('rb') as handle:
                payload = handle.read(self.max_bytes + 1)
            if not payload or len(payload) > self.max_bytes:
                raise ProviderError('media: empty file or size limit exceeded')
            with tempfile.NamedTemporaryFile(suffix='.mp4') as snapshot:
                snapshot.write(payload)
                snapshot.flush()
                result = subprocess.run([self.ffprobe, '-v', 'error', '-select_streams', 'v:0',
                    '-show_entries', 'stream=duration', '-of', 'json', snapshot.name],
                    capture_output=True, text=True, timeout=15, check=True)
            streams = json.loads(result.stdout)['streams']
            duration = float(streams[0]['duration'])
            if not math.isfinite(duration) or not 0 < duration <= 120:
                raise ValueError()
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderError('media: cannot probe video stream duration (requires ffprobe; maximum 120 seconds)') from None
        if abs(duration - incident.duration_seconds) > 0.05:
            raise ProviderError('media: incident duration differs from probed video duration')
        return VideoAsset(incident.video_uri, duration, 'data:video/mp4;base64,' +
                          base64.b64encode(payload).decode('ascii'), hashlib.sha256(payload).hexdigest())
