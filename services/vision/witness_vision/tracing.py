"""Optional W&B Weave tracing. Off unless WITNESS_WEAVE_PROJECT is set; any import or
initialization failure leaves functions untraced and never breaks analysis."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])
_state: dict[str, Any] = {"initialized": False, "weave": None}


def weave_project() -> str | None:
    return os.getenv("WITNESS_WEAVE_PROJECT") or None


def init_weave(project: str | None = None) -> Any | None:
    """Initialize Weave once. Returns the weave module, or None when disabled/unavailable.
    Credentials come from the standard W&B environment (WANDB_API_KEY or `wandb login`)."""
    if _state["initialized"]:
        return _state["weave"]
    _state["initialized"] = True
    project = project or weave_project()
    if not project:
        return None
    try:
        import weave
        weave.init(project)
    except Exception as exc:  # missing package, credentials or network
        logger.warning("Weave tracing disabled: %s", exc)
        return None
    _state["weave"] = weave
    return weave


def traced(name: str) -> Callable[[F], F]:
    """Decorator: route calls through weave.op when Weave is active, else call directly."""
    def decorate(fn: F) -> F:
        cache: dict[str, Any] = {}

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            weave = init_weave()
            if weave is None:
                return fn(*args, **kwargs)
            if "op" not in cache:
                cache["op"] = weave.op(name=name)(fn)
            return cache["op"](*args, **kwargs)

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]
    return decorate


def reset_for_tests() -> None:
    _state.update(initialized=False, weave=None)
