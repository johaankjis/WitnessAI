import os
from pathlib import Path
from .mock import MockAdapters
from .pipeline import Pipeline
from .jobs import AnalysisRunner


def configured_pipeline(mode: str) -> AnalysisRunner:
    if mode == 'mock':
        mock = MockAdapters()
        from witness_vision.adapter import MockVisionObserver
        return Pipeline(mock, mock, mock, MockVisionObserver(), mock, mock)
    if mode != 'real':
        raise ValueError('WITNESS_ANALYSIS_MODE must be mock or real')
    # Provider transports are constructed only after explicit real-mode selection.
    from .provider_io import ChatTransport
    from .providers import WandbAdapter, RealPipeline
    from .media import LocalMedia
    def required(name: str) -> str:
        value = os.getenv(name, '').strip()
        if not value:
            raise ValueError(f'{name} is required for real mode')
        return value
    options = {'timeout': float(os.getenv('WITNESS_PROVIDER_TIMEOUT', '30')),
               'retries': int(os.getenv('WITNESS_PROVIDER_RETRIES', '2'))}
    wandb = ChatTransport('wandb', os.getenv('WANDB_INFERENCE_BASE_URL', 'https://api.inference.wandb.ai/v1'),
        required('WANDB_INFERENCE_MODEL'), required('WANDB_API_KEY'),
        project=os.getenv('WANDB_INFERENCE_PROJECT', ''), **options)
    cosmos = ChatTransport('cosmos', required('COSMOS_BASE_URL'),
        os.getenv('COSMOS_MODEL', 'nvidia/Cosmos-Reason2-8B'), os.getenv('COSMOS_API_KEY', ''), **options)
    from witness_vision.adapter import VisionObserver
    from witness_vision.detectors import UltralyticsDetector
    weights = Path(required('WITNESS_YOLO_WEIGHTS')).resolve()
    if not weights.is_file():
        raise ValueError('WITNESS_YOLO_WEIGHTS must be an existing local weights file')
    observer = VisionObserver(detector=UltralyticsDetector(weights=str(weights)),
                              media_root=Path(required('WITNESS_MEDIA_ROOT')))
    return RealPipeline(WandbAdapter(wandb), cosmos, LocalMedia(Path(required('WITNESS_MEDIA_ROOT')),
        ffprobe=os.getenv('WITNESS_FFPROBE', 'ffprobe')), observer=observer)
