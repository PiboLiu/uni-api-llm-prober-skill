#!/usr/bin/env python3
"""Run concurrency pressure tests for Uni-API endpoints and models."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any


DEFAULT_BASE_URL = "https://uni-api.cstcloud.cn/v1"
DEFAULT_KIND_MODELS: dict[str, str] = {
    "chat": "deepseek-v3:671b",
    "embedding": "bge-large-zh:latest",
    "rerank": "bge-reranker-v2-m3",
    "analysis": "S1-CitationCalculate",
    "ocr_pdf": "deepseek-ocr",
}


def parse_positive_int_list(raw: str) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        num = int(item)
        if num <= 0:
            raise ValueError("list values must be positive integers")
        if num not in seen:
            values.append(num)
            seen.add(num)
    if not values:
        raise ValueError("at least one positive integer is required")
    return values


def percentile_ms(latencies: list[int], pct: int) -> int:
    if not latencies:
        return 0
    ordered = sorted(latencies)
    rank = int(math.ceil((pct / 100) * len(ordered)))
    index = max(0, min(len(ordered) - 1, rank - 1))
    return int(ordered[index])


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    success = sum(1 for s in samples if bool(s.get("ok")))
    failed = total - success
    latencies = [int(s.get("latency_ms", 0)) for s in samples]
    errors = Counter(str(s.get("error", "")) for s in samples if not bool(s.get("ok")))
    error_counts = {k: v for k, v in errors.items() if k}
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": (success / total) if total else 0.0,
        "p50_ms": percentile_ms(latencies, 50),
        "p95_ms": percentile_ms(latencies, 95),
        "max_ms": max(latencies) if latencies else 0,
        "error_counts": error_counts,
    }


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
    req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            if not isinstance(parsed, dict):
                parsed = {"raw": parsed}
            return int(resp.getcode()), parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body.strip() or str(exc.reason)
        raise RuntimeError(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}")


def _build_request(kind: str, model_id: str) -> tuple[str, str, dict[str, Any] | None]:
    if kind == "chat":
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with OK only."}],
            "max_tokens": 16,
            "temperature": 0,
        }
        if model_id.startswith("S1-Base-"):
            payload["id"] = f"stress-{int(time.time() * 1000)}"
            payload["stream"] = False
        return "POST", "/chat/completions", payload
    if kind == "embedding":
        return "POST", "/embeddings", {"model": model_id, "input": "hello world"}
    if kind == "rerank":
        return (
            "POST",
            "/rerank",
            {
                "model": model_id,
                "query": "What is machine learning?",
                "documents": [
                    "Machine learning is a subfield of AI.",
                    "Bananas are yellow and rich in potassium.",
                    "Deep learning uses neural networks.",
                ],
                "top_n": 2,
            },
        )
    if kind == "analysis":
        return (
            "POST",
            "/analysis",
            {
                "model": model_id,
                "id": f"stress-{int(time.time() * 1000)}",
                "content": {
                    "text": "Earth revolves around the Sun.",
                    "doc_list": [
                        {"context": "Earth revolves around the Sun according to heliocentrism."},
                        {"context": "Mars is the fourth planet of the solar system."},
                    ],
                    "mode": "file",
                },
            },
        )
    if kind == "ocr_pdf":
        return "GET", "/deepseek-ocr/health", None
    raise ValueError(f"Unsupported kind: {kind}")


def _is_success(kind: str, payload: dict[str, Any]) -> bool:
    if kind == "chat":
        choices = payload.get("choices")
        return isinstance(choices, list) and len(choices) > 0
    if kind == "embedding":
        data = payload.get("data")
        return isinstance(data, list) and len(data) > 0
    if kind == "rerank":
        results = payload.get("results")
        data = payload.get("data")
        return (isinstance(results, list) and len(results) > 0) or (isinstance(data, list) and len(data) > 0)
    if kind == "analysis":
        return payload.get("code") == 200
    if kind == "ocr_pdf":
        status = payload.get("status")
        return isinstance(status, str) and bool(status.strip())
    return False


def _run_one(
    *,
    base_url: str,
    api_key: str,
    kind: str,
    model_id: str,
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    method, endpoint, payload = _build_request(kind, model_id)
    try:
        _, data = _http_json(
            base_url=base_url,
            endpoint=endpoint,
            api_key=api_key,
            method=method,
            timeout=timeout,
            payload=payload,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        ok = _is_success(kind, data)
        return {
            "ok": ok,
            "latency_ms": latency_ms,
            "error": "" if ok else "unexpected response shape",
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


def run_level(
    *,
    base_url: str,
    api_key: str,
    kind: str,
    model_id: str,
    concurrency: int,
    requests: int,
    timeout: float,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                _run_one,
                base_url=base_url,
                api_key=api_key,
                kind=kind,
                model_id=model_id,
                timeout=timeout,
            )
            for _ in range(requests)
        ]
        for future in as_completed(futures):
            samples.append(future.result())
    summary = summarize_samples(samples)
    summary.update(
        {
            "kind": kind,
            "model": model_id,
            "concurrency": concurrency,
            "requests": requests,
        }
    )
    return summary


def build_recommendations(levels: list[dict[str, Any]], timeout: float) -> dict[str, Any]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for level in levels:
        by_kind.setdefault(str(level["kind"]), []).append(level)

    rec: dict[str, Any] = {}
    p95_limit = int(timeout * 1000 * 0.9)
    for kind, rows in by_kind.items():
        rows_sorted = sorted(rows, key=lambda x: int(x["concurrency"]))
        stable = [
            row
            for row in rows_sorted
            if float(row["success_rate"]) >= 0.99 and int(row["p95_ms"]) <= p95_limit
        ]
        if stable:
            chosen = stable[-1]
            rec[kind] = {
                "recommended_concurrency": int(chosen["concurrency"]),
                "reason": f"success_rate>=99% and p95<={p95_limit}ms",
            }
        else:
            rec[kind] = {
                "recommended_concurrency": 1,
                "reason": "no stable level reached strict threshold; fallback to 1",
            }
    return rec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pressure test Uni-API endpoints with concurrency levels.")
    parser.add_argument("--base-url", default=os.getenv("UNI_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--api-key",
        default=os.getenv(
            "UNI_API_KEY",
            os.getenv("API_UNI_TOKEN", os.getenv("OPENAI_API_KEY", "")),
        ),
    )
    parser.add_argument("--kinds", default="chat,embedding,rerank,analysis,ocr_pdf")
    parser.add_argument("--concurrency-list", default="1,2,4,8")
    parser.add_argument("--requests-per-level", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--model-chat", default=DEFAULT_KIND_MODELS["chat"])
    parser.add_argument("--model-embedding", default=DEFAULT_KIND_MODELS["embedding"])
    parser.add_argument("--model-rerank", default=DEFAULT_KIND_MODELS["rerank"])
    parser.add_argument("--model-analysis", default=DEFAULT_KIND_MODELS["analysis"])
    parser.add_argument("--model-ocr-pdf", default=DEFAULT_KIND_MODELS["ocr_pdf"])
    parser.add_argument("--json-output", default="")
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print(
            "UNI_API_KEY/API_UNI_TOKEN is required. Example:\n"
            "  export API_UNI_TOKEN='your_key'\n"
            "  python3 scripts/stress_test_uni_api.py",
        )
        return 2

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    concurrencies = parse_positive_int_list(args.concurrency_list)
    requests = max(1, int(args.requests_per_level))
    timeout = max(1.0, float(args.timeout))
    model_by_kind = {
        "chat": args.model_chat,
        "embedding": args.model_embedding,
        "rerank": args.model_rerank,
        "analysis": args.model_analysis,
        "ocr_pdf": args.model_ocr_pdf,
    }

    levels: list[dict[str, Any]] = []
    for kind in kinds:
        if kind not in model_by_kind:
            raise ValueError(f"Unsupported kind in --kinds: {kind}")
        model = model_by_kind[kind]
        for concurrency in concurrencies:
            levels.append(
                run_level(
                    base_url=args.base_url,
                    api_key=args.api_key,
                    kind=kind,
                    model_id=model,
                    concurrency=concurrency,
                    requests=requests,
                    timeout=timeout,
                )
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "kinds": kinds,
        "concurrency_list": concurrencies,
        "requests_per_level": requests,
        "timeout_seconds": timeout,
        "levels": levels,
        "recommendations": build_recommendations(levels, timeout),
    }
    text = json.dumps(
        report,
        ensure_ascii=False,
        separators=(",", ":") if args.compact else None,
        indent=None if args.compact else 2,
    )
    print(text)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
