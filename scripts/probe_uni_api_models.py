#!/usr/bin/env python3
"""Probe Uni-API model availability across chat/embedding/rerank style endpoints."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://uni-api.cstcloud.cn/v1"
SPECIAL_KINDS = {"web_search", "ai_search"}


class HttpCallError(RuntimeError):
    """Raised when API returns a non-2xx response."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def collect_model_ids(payload: dict[str, Any]) -> list[str]:
    """Read model ids from /models response."""
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    model_ids: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw = item.get("id", "")
        if isinstance(raw, str) and raw.strip():
            model_ids.append(raw.strip())
    return model_ids


def classify_model(model_id: str) -> str:
    """Classify model id to probe kind."""
    lowered = model_id.lower()
    if lowered == "s1-citationcalculate":
        return "analysis"
    if lowered in {"web-search", "web_search"} or "web-search" in lowered:
        return "web_search"
    if lowered in {"ai-search", "ai_search", "scienceone-search", "science-one-search"}:
        return "ai_search"
    if "deepseek-ocr" in lowered or "deepseek-ocp" in lowered:
        return "ocr_pdf"
    if "rerank" in lowered:
        return "rerank"
    if (
        "embedding" in lowered
        or "/bge" in lowered
        or lowered.startswith("bge-")
        or lowered.startswith("gte-")
        or lowered.startswith("gte_")
    ):
        return "embedding"
    return "chat"


def build_probe_request(model_id: str, kind: str, ocr_image_url: str) -> dict[str, Any]:
    """Build endpoint + payload for a single model probe."""
    if kind == "chat":
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Please reply with OK only."}],
            "max_tokens": 16,
            "temperature": 0,
        }
        # ScienceOne base models require id in payload according to official docs.
        if model_id.startswith("S1-Base-"):
            payload["id"] = f"probe-{int(time.time() * 1000)}"
            payload["stream"] = False
        return {
            "endpoint": "/chat/completions",
            "method": "POST",
            "payload": payload,
        }
    if kind == "embedding":
        return {
            "endpoint": "/embeddings",
            "method": "POST",
            "payload": {
                "model": model_id,
                "input": "hello world",
            },
        }
    if kind == "rerank":
        return {
            "endpoint": "/rerank",
            "method": "POST",
            "payload": {
                "model": model_id,
                "query": "What is machine learning?",
                "documents": [
                    "Machine learning is a subfield of AI.",
                    "Bananas are yellow and rich in potassium.",
                    "Deep learning uses neural networks.",
                ],
                "top_n": 2,
            },
        }
    if kind == "web_search":
        return {
            "endpoint": "/chat/web_search",
            "method": "POST",
            "payload": {
                "model": model_id,
                "messages": [{"role": "user", "content": "What is today's major AI news headline?"}],
                "max_tokens": 256,
                "temperature": 0,
            },
        }
    if kind == "ai_search":
        return {
            "endpoint": "/chat/ai_search",
            "method": "POST",
            "payload": {
                "model": model_id,
                "messages": [{"role": "user", "content": "Summarize retrieval augmented generation in 2 sentences."}],
                "max_tokens": 256,
                "temperature": 0,
            },
        }
    if kind == "analysis":
        return {
            "endpoint": "/analysis",
            "method": "POST",
            "payload": {
                "model": model_id,
                "id": f"probe-{int(time.time() * 1000)}",
                "content": {
                    "text": "Earth revolves around the Sun.",
                    "doc_list": [
                        {"context": "Earth revolves around the Sun according to heliocentrism."},
                        {"context": "Mars is the fourth planet of the solar system."},
                    ],
                    "mode": "file",
                },
            },
        }
    if kind == "ocr_pdf":
        return {
            "endpoint": "/deepseek-ocr/health",
            "method": "GET",
            "payload": None,
        }
    raise ValueError(f"Unsupported probe kind: {kind}")


def validate_response(kind: str, payload: dict[str, Any]) -> bool:
    """Minimal shape validation for successful responses."""
    if "error" in payload:
        return False
    if kind in {"chat", "web_search", "ai_search"}:
        choices = payload.get("choices")
        return isinstance(choices, list) and len(choices) > 0
    if kind == "analysis":
        code = payload.get("code")
        data = payload.get("data")
        return code == 200 and isinstance(data, dict)
    if kind == "ocr_pdf":
        status = payload.get("status")
        return isinstance(status, str) and bool(status.strip())
    if kind == "embedding":
        data = payload.get("data")
        return isinstance(data, list) and len(data) > 0
    if kind == "rerank":
        results = payload.get("results")
        if isinstance(results, list) and len(results) > 0:
            return True
        data = payload.get("data")
        return isinstance(data, list) and len(data) > 0
    return False


def summarize_results(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(results), "success": 0, "failed": 0, "skipped": 0}
    for item in results:
        status = item.get("status")
        if status == "success":
            summary["success"] += 1
        elif status == "failed":
            summary["failed"] += 1
        elif status == "skipped":
            summary["skipped"] += 1
    return summary


def _response_preview(payload: dict[str, Any], limit: int = 400) -> str:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= limit:
        return raw
    return f"{raw[:limit - 3]}..."


def _http_json(
    *,
    base_url: str,
    endpoint: str,
    api_key: str,
    method: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    data: bytes | None = None
    headers = {"Authorization": f"Bearer {api_key}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            if not isinstance(parsed, dict):
                parsed = {"raw": parsed}
            return int(resp.getcode()), parsed
    except urllib.error.HTTPError as exc:
        err_raw = exc.read().decode("utf-8", errors="replace")
        detail = err_raw.strip() or str(exc.reason)
        raise HttpCallError(exc.code, f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if exc.reason else str(exc)
        raise RuntimeError(f"Network error: {reason}")


def probe_one_model(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    include_special_endpoints: bool,
    ocr_image_url: str,
    timeout: float,
) -> dict[str, Any]:
    kind = classify_model(model_id)

    if kind in SPECIAL_KINDS and not include_special_endpoints:
        return {
            "model": model_id,
            "kind": kind,
            "status": "skipped",
            "reason": "special endpoint probe disabled; pass --include-special-endpoints to enable",
        }
    try:
        req = build_probe_request(model_id=model_id, kind=kind, ocr_image_url=ocr_image_url)
    except Exception as exc:
        return {
            "model": model_id,
            "kind": kind,
            "status": "failed",
            "error": str(exc),
        }

    start = time.monotonic()
    try:
        http_status, response_payload = _http_json(
            base_url=base_url,
            endpoint=req["endpoint"],
            api_key=api_key,
            method=req.get("method", "POST"),
            timeout=timeout,
            payload=req["payload"],
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        if validate_response(kind, response_payload):
            return {
                "model": model_id,
                "kind": kind,
                "endpoint": req["endpoint"],
                "status": "success",
                "http_status": http_status,
                "latency_ms": latency_ms,
            }
        return {
            "model": model_id,
            "kind": kind,
            "endpoint": req["endpoint"],
            "status": "failed",
            "http_status": http_status,
            "latency_ms": latency_ms,
            "error": "unexpected response shape",
            "response_preview": _response_preview(response_payload),
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "model": model_id,
            "kind": kind,
            "endpoint": req.get("endpoint", ""),
            "status": "failed",
            "latency_ms": latency_ms,
            "error": str(exc),
        }


def run_probe(
    *,
    base_url: str,
    api_key: str,
    model_ids: list[str] | None,
    max_models: int,
    include_special_endpoints: bool,
    ocr_image_url: str,
    timeout: float,
) -> dict[str, Any]:
    if model_ids:
        targets = list(dict.fromkeys(model_ids))
    else:
        _, models_payload = _http_json(
            base_url=base_url,
            endpoint="/models",
            api_key=api_key,
            method="GET",
            timeout=timeout,
        )
        targets = collect_model_ids(models_payload)
        if not targets:
            raise RuntimeError("No models returned from /models")

    if max_models > 0:
        targets = targets[:max_models]

    results = [
        probe_one_model(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            include_special_endpoints=include_special_endpoints,
            ocr_image_url=ocr_image_url,
            timeout=timeout,
        )
        for model_id in targets
    ]
    summary = summarize_results(results)
    return {
        "base_url": base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Uni-API model availability from /models and capability-specific endpoints."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("UNI_API_BASE_URL", DEFAULT_BASE_URL),
        help="Uni-API base url (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv(
            "UNI_API_KEY",
            os.getenv("API_UNI_TOKEN", os.getenv("OPENAI_API_KEY", "")),
        ),
        help="API key. Reads UNI_API_KEY or API_UNI_TOKEN or OPENAI_API_KEY when omitted.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Probe only this model id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=0,
        help="Cap number of tested models (0 means all).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout seconds.",
    )
    parser.add_argument(
        "--include-special-endpoints",
        action="store_true",
        help="Also probe web-search / ai-search / ocr special endpoints.",
    )
    parser.add_argument(
        "--ocr-image-url",
        default=os.getenv("UNI_API_OCR_IMAGE_URL", ""),
        help="Image URL for OCR probing when --include-special-endpoints is enabled.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional output path for JSON report.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print(
            "UNI_API_KEY/API_UNI_TOKEN is required. Example:\n"
            "  export API_UNI_TOKEN='your_key'\n"
            "  python3 scripts/uni_api/probe_uni_api_models.py --max-models 5",
            file=sys.stderr,
        )
        return 2

    try:
        report = run_probe(
            base_url=args.base_url,
            api_key=args.api_key,
            model_ids=args.model,
            max_models=max(0, args.max_models),
            include_special_endpoints=bool(args.include_special_endpoints),
            ocr_image_url=args.ocr_image_url,
            timeout=max(1.0, float(args.timeout)),
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    text = json.dumps(report, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2)
    print(text)
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")

    failed = int(report["summary"]["failed"])
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
