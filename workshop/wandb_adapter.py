"""Optional W&B Serverless Inference adapter boundary.

Disabled by default: workshop VM currently receives Cloudflare 403/1010 when
calling https://api.inference.wandb.ai. MVP uses VSS synthesis / scoped agent
Q&A instead. Flip WITNESS_ENABLE_WANDB=1 only after connectivity is restored.
"""

from __future__ import annotations

import os
from typing import Any


class WandBInferenceAdapter:
    name = "wandb_serverless_inference"
    base_url = "https://api.inference.wandb.ai/v1"

    def __init__(self) -> None:
        self.enabled = os.environ.get("WITNESS_ENABLE_WANDB", "").strip() in {"1", "true", "yes"}
        self.api_key_present = bool(os.environ.get("WANDB_API_KEY"))
        self.team = os.environ.get("WANDB_TEAM") or ""
        self.project = os.environ.get("WANDB_PROJECT") or ""

    def status(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "enabled": self.enabled,
            "api_key_configured": self.api_key_present,
            "team_configured": bool(self.team),
            "project_configured": bool(self.project),
            "base_url": self.base_url,
            "active": False,
            "note": (
                "W&B inference is intentionally inactive for this MVP. "
                "Use VSS scoped agent / search synthesis until outbound 403 is resolved."
            ),
        }

    def complete(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError(
            "W&B adapter is disabled for Witness workshop MVP "
            "(set WITNESS_ENABLE_WANDB=1 only after 403/1010 is fixed)."
        )
