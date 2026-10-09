"""VSS retrieval client — uses documented workshop API contracts only.

Auth: POST /api/v1/auth/login
Search: POST /api/v1/search
Metadata: GET /api/v1/videos/metadata
Detections: GET /api/v1/videos/detections
Stream: GET /api/v1/videos/stream?source=&token=
Agent (scoped): POST /api/v1/agent/ask with original_video
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any


import requests

log = logging.getLogger("witness.vss")


class VSSAuthError(Exception):
    """Login or token failure."""


class VSSAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class VSSClient:
    mode = "vast"
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = (os.environ.get("VSS_URL", "") if base_url is None else base_url).rstrip("/")
        self.username = os.environ.get("VSS_USERNAME", "") if username is None else username
        self.password = os.environ.get("VSS_PASSWORD", "") if password is None else password
        self.timeout = timeout
        self._session = session or requests.Session()
        self._token: str | None = None
        self._token_lock = threading.Lock()
        self._token_obtained_at: float = 0.0

    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def login(self, force: bool = False) -> str:
        if not self.configured():
            raise VSSAuthError("VSS_URL / VSS_USERNAME / VSS_PASSWORD not configured")
        with self._token_lock:
            if self._token and not force and (time.time() - self._token_obtained_at) < 1500:
                return self._token
            url = f"{self.base_url}/api/v1/auth/login"
            try:
                resp = self._session.post(
                    url,
                    json={"username": self.username, "password": self.password},
                    allow_redirects=False,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise VSSAuthError("login request failed") from exc
            try:
                if resp.status_code >= 300:
                    raise VSSAuthError(f"login rejected HTTP {resp.status_code}")
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise VSSAuthError("login response not JSON") from exc
                token = data.get("access_token") if isinstance(data, dict) else None
                if not isinstance(token, str) or not token:
                    raise VSSAuthError("login response missing access_token")
                self._token = token
                self._token_obtained_at = time.time()
                return token
            finally:
                resp.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        stream: bool = False,
        use_query_token: bool = False,
        retry_auth: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        token = self.login()
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = dict(extra_headers or {})
        req_params = dict(params or {})
        if use_query_token:
            req_params["token"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=headers,
                params=req_params,
                json=json_body,
                allow_redirects=False,
                timeout=self.timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            raise VSSAPIError("VSS request failed") from exc
        if resp.status_code == 401 and retry_auth:
            resp.close()
            self.login(force=True)
            return self._request(
                method,
                path,
                json_body=json_body,
                params=params,
                stream=stream,
                use_query_token=use_query_token,
                retry_auth=False,
                extra_headers=extra_headers,
            )
        if resp.status_code >= 300 and not (resp.status_code == 404 and path.endswith("/detections")):
            resp.close()
            raise VSSAPIError("VSS upstream request failed", resp.status_code)
        return resp

    @staticmethod
    def _json(resp: requests.Response, kind: str) -> dict[str, Any]:
        try:
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError()
            json.dumps(data, allow_nan=False)
            if kind == "search":
                rows = data.get("results")
                if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                    raise ValueError()
                synthesis = data.get("llm_synthesis")
                if synthesis is not None and (not isinstance(synthesis, dict) or
                        not isinstance(synthesis.get("response", ""), str)):
                    raise ValueError()
            if kind == "agent" and not isinstance(data.get("answer"), str):
                raise ValueError()
            if kind == "metadata" and data.get("reasoning_content") is not None and not isinstance(data["reasoning_content"], str):
                raise ValueError()
            if kind == "detections":
                frames = data.get("frames", [])
                if not isinstance(frames, list):
                    raise ValueError()
                for frame in frames:
                    if not isinstance(frame, dict) or not isinstance(frame.get("detections", []), list):
                        raise ValueError()
                    if any(not isinstance(d, dict) or not isinstance(d.get("label", ""), str)
                           for d in frame.get("detections", [])):
                        raise ValueError()
            return data
        except ValueError as exc:
            raise VSSAPIError("Invalid VSS JSON response") from exc
        finally:
            resp.close()

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        min_similarity: float = 0.2,
        metadata_filters: dict | None = None,
        llm_top_n: int = 1,
        time_filter: str = "all",
    ) -> dict[str, Any]:
        body = {
            "query": query,
            "top_k": top_k,
            "llm_top_n": llm_top_n,
            "min_similarity": min_similarity,
            "time_filter": time_filter,
            "metadata_filters": metadata_filters or {},
            "include_public": True,
        }
        resp = self._request("POST", "/api/v1/search", json_body=body)
        return self._json(resp, "search")

    def segment_metadata(self, source: str) -> dict[str, Any]:
        resp = self._request(
            "GET",
            "/api/v1/videos/metadata",
            params={"source": source},
        )
        return self._json(resp, "metadata")

    def segment_detections(self, source: str) -> dict[str, Any] | None:
        resp = self._request(
            "GET",
            "/api/v1/videos/detections",
            params={"source": source},
        )
        if resp.status_code == 404:
            resp.close()
            return None
        return self._json(resp, "detections")

    def agent_ask_scoped(self, question: str, original_video: str, top_k: int = 8) -> dict[str, Any]:
        """Prefer scoped ask — global /agent/ask was observed returning 500 on workshop."""
        body = {"question": question, "original_video": original_video, "top_k": top_k}
        resp = self._request("POST", "/api/v1/agent/ask", json_body=body)
        return self._json(resp, "agent")

    def open_stream(self, source: str, range_header: str | None = None) -> requests.Response:
        # Share bounded refresh and sanitized transport errors with all other calls.
        resp = self._request("GET", "/api/v1/videos/stream", params={"source": source},
                             stream=True, use_query_token=True,
                             extra_headers={"Range": range_header} if range_header else {})
        if resp.status_code not in {200, 206}:
            resp.close()
            raise VSSAPIError("stream failed", resp.status_code)
        return resp


def prefer_incident_hit(results: list[dict[str, Any]], source: str) -> dict[str, Any] | None:
    """Prefer the fixed incident segment when present among search hits."""
    for row in results or []:
        if row.get("source") == source:
            return row
    return None


def validate_detection_provenance(
    det: dict[str, Any], metadata: dict[str, Any], *, source: str,
    legacy_source: str, expected_sidecar: str,
) -> None:
    """Validate footage independently of the detector identifier; never rewrite inputs.

    Caller must first validate the metadata's exact source and timestamps.
    The legacy exception is restricted to one explicitly published source pair.
    """
    if not isinstance(det, dict) or det.get("source") != "yolo11_coco":
        raise ValueError("Unexpected detection identifier")
    if det.get("synthetic", False):
        raise ValueError("Detection evidence mode mismatch")
    if metadata.get("source") != source:
        raise ValueError("Metadata source mismatch")
    if det.get("segment_source") not in (source, legacy_source):
        raise ValueError("Detection segment source mismatch")
    anchor_sidecar = metadata.get("detection_sidecar_uri")
    if anchor_sidecar != expected_sidecar:
        raise ValueError("Detection sidecar mismatch")
    # Some responses echo the sidecar URI. If present it must agree exactly.
    if "detection_sidecar_uri" in det and det["detection_sidecar_uri"] != anchor_sidecar:
        raise ValueError("Detection sidecar mismatch")
    counts = (metadata.get("detection_count"), det.get("detection_count"))
    if any(type(count) is not int or count < 0 for count in counts) or counts[0] != counts[1]:
        raise ValueError("Detection count mismatch")


def summarize_detections(det: dict[str, Any] | None) -> dict[str, Any]:
    if not det:
        return {
            "available": False,
            "detection_count": 0,
            "object_classes": [],
            "object_counts": {},
            "fps": None,
            "frame_count": None,
            "max_detection_conf": None,
            "note": "No YOLO sidecar for this segment.",
        }
    return {
        "synthetic": bool(det.get("synthetic", False)),
        "available": True,
        "source": det.get("source"),
        "segment_source": det.get("segment_source"),
        "detection_sidecar_uri": det.get("detection_sidecar_uri"),
        "detection_count": det.get("detection_count"),
        "object_classes": det.get("object_classes"),
        "object_counts": det.get("object_counts"),
        "fps": det.get("fps"),
        "frame_count": det.get("frame_count"),
        "video_shape": det.get("video_shape"),
        "max_detection_conf": det.get("max_detection_conf"),
        "provenance": ("SYNTHETIC FIXTURE; not measurements or independent corroboration" if det.get("synthetic") else "YOLO11 detections from VSS /api/v1/videos/detections"),
        # Do not dump full frame bboxes to the UI payload by default (size);
        # inspector can request denser data later if needed.
        "sample_frame0_labels": sorted(
            {
                d.get("label")
                for d in ((det.get("frames") or [{}])[0].get("detections") or [])
                if d.get("label")
            }
        )[:20],
    }


def public_evidence_row(row: dict[str, Any] | None, *, source_fallback: str) -> dict[str, Any]:
    if not row:
        return {
            "found": False,
            "source": source_fallback,
            "reasoning_content": None,
            "segment_start_sec": None,
            "segment_end_sec": None,
        }
    return {
        "synthetic": bool(row.get("synthetic", False)),
        "found": True,
        "source": row.get("source") or source_fallback,
        "original_video": row.get("original_video"),
        "filename": row.get("filename"),
        "reasoning_content": row.get("reasoning_content"),
        "segment_start_sec": row.get("segment_start_sec"),
        "segment_end_sec": row.get("segment_end_sec"),
        "segment_number": row.get("segment_number"),
        "duration": row.get("duration"),
        "similarity_score": row.get("similarity_score"),
        "location": row.get("location"),
        "camera_id": row.get("camera_id"),
        "capture_type": row.get("capture_type"),
        "object_classes": row.get("object_classes"),
        "object_counts": row.get("object_counts"),
        "detection_count": row.get("detection_count"),
        "cosmos_model": row.get("cosmos_model"),
        "detection_sidecar_uri": row.get("detection_sidecar_uri"),
        "provenance": {
            "reasoning_source": "SYNTHETIC FIXTURE" if row.get("synthetic") else "Cosmos Reasoner (reasoning_content from VastDB / search)",
            "objects_source": "SYNTHETIC FIXTURE" if row.get("synthetic") else "YOLO fields on segment row (may differ from detections sidecar)",
        },
    }
