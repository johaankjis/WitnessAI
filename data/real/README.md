# Real-video incidents

Incident records for real dashcam footage. The footage, model weights and generated
inference outputs are **not committed**; they live under the gitignored `data/local/`.

## nexar-00000

| Field | Value |
| --- | --- |
| Incident | `nexar-00000.json` (`is_mock=false`) |
| Footage | `data/local/nexar/train/positive/00000.mp4`, referenced as `train/positive/00000.mp4` relative to `WITNESS_MEDIA_ROOT=data/local/nexar` |
| Source | Nexar Collision Prediction dataset, Hugging Face `nexar-ai/nexar_collision_prediction`, `train/positive/00000.mp4` (sha256 `9b7364178cb8b6194db0ee0f96df0ad44615fc265efe435297394dcf6a9be5f9`) |
| Media | H.264 1280x720, 28.9 fps, 1158 frames, 40.069204 s (ffprobe) |
| Label | `train/positive/metadata.csv`: `time_of_event` 20.76 s, `time_of_alert` 19.136 s, Normal light, Clear, Urban |
| Claims | `nexar-00000.claims.json`: hand-written atomic claims used to exercise the detector adapter |

**The driver statements are sample text written by the team for testing.** They are not
real statements from the people in the footage and they describe a dispute the team made
up after watching the clip. Do not present them as evidence of anything. The claims file
stands in for the W&B claim extractor's output so the vision adapter can be run without
provider credentials.

The dataset is distributed under the Nexar Open Data License (attribution required, no
resale, no re-identification). Cite: Moura, Daniel C., and Zvitia, Orly. "Nexar Collision
Dataset." Hugging Face, 2025, https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction.

Download the clip and labels (gated: accept the license on Hugging Face and `hf auth login` first):

```sh
python - <<'EOF'
from huggingface_hub import hf_hub_download
for f in ["train/positive/00000.mp4", "train/positive/metadata.csv", "LICENSE"]:
    hf_hub_download("nexar-ai/nexar_collision_prediction", f, repo_type="dataset", local_dir="data/local/nexar")
EOF
```
