---
name: uni-api-llm-prober
description: Use when validating whether Uni-API models can be called successfully across /models, chat, embedding, rerank, and optional search or OCR endpoints.
---

# Uni-API LLM Prober

## Overview

Use this skill to batch-check model availability on `https://uni-api.cstcloud.cn/v1` using the official LLM doc flow:
- Pull model ids from `GET /models`
- Probe each model with its matched endpoint
- Output a JSON report with `success/failed/skipped`

## Prerequisites

Set API key:

```bash
export API_UNI_TOKEN="your_uni_api_key"
```

Also supported:

```bash
export UNI_API_KEY="your_uni_api_key"
```

Optional:

```bash
export UNI_API_BASE_URL="https://uni-api.cstcloud.cn/v1"
export UNI_API_OCR_IMAGE_URL="https://example.com/sample-ocr.png"
```

## Commands

Quick probe all standard models (chat + embedding + rerank):

```bash
python3 scripts/probe_uni_api_models.py
```

Limit to first 10 models:

```bash
python3 scripts/probe_uni_api_models.py --max-models 10
```

Probe specific models:

```bash
python3 scripts/probe_uni_api_models.py --model qwen-max --model rerank-v2-m3
```

Include special endpoints (`web_search`, `ai_search`, `ocr`):

```bash
python3 scripts/probe_uni_api_models.py \
  --include-special-endpoints \
  --ocr-image-url "https://example.com/sample-ocr.png"
```

Write report to file:

```bash
python3 scripts/probe_uni_api_models.py --json-output /tmp/uni_api_probe_report.json
```

Single-model pressure test (recommended before production rollout):

```bash
python3 scripts/stress_test_uni_api.py \
  --kinds chat \
  --model-chat deepseek-v3:671b \
  --concurrency-list 1,2,4,8 \
  --requests-per-level 4 \
  --timeout 15 \
  --json-output /tmp/uni_api_stress_chat_deepseek_v3.json
```

## Output Semantics

- `success`: API returned expected shape for this endpoint.
- `failed`: request failed or response shape does not match expected fields.
- `skipped`: model intentionally skipped (for example special endpoints not enabled, or OCR URL missing).

## Stable Run Profile (Validated 2026-02-25 UTC)

Validation report:

- `references/performance/uni_api_full_model_stress_20260225.json`
- `references/performance/stability-baseline-2026-02-25.md`

Test profile:

- `/models` returned 21 models (chat 14, embedding 3, rerank 2, analysis 1, ocr 1)
- Concurrency levels: `1,2,4,8`
- Requests per level: `4`
- Timeout per request: `15s`
- Early stop when `success_rate < 0.9`
- Stability threshold for recommendation: `success_rate >= 99%` and `p95 <= 13.5s`

Safe default concurrency by kind (production conservative mode):

- `chat`: `1`
- `embedding`: `1`
- `rerank`: `1`
- `analysis`: `8`
- `ocr_pdf`: `8`

High-throughput models validated to run at `c=8` under this profile:

- Chat: `deepseek-v3:671b`, `qwen2.5-vl:72b`, `qwen3:235b`, `spark-x1:70b`, `gpt-oss-120b`
- Embedding: `bge-large-zh:latest`
- Rerank: `qwen3-reranker:8b`
- Analysis: `S1-CitationCalculate`
- OCR: `deepseek-ocr`

Models that should stay at `c=1` (or be avoided for high-QPS workloads):

- Chat: `deepseek-r1:671b-64b`, `deepseek-r1:32b`, `deepseek-r1:671b`, `deepseek-r1:671b-0528`, `qwq:32b`, `qwen3.5`, `S1-Base-Lite`, `S1-Base-Pro`, `S1-Base-Ultra`
- Embedding: `gte-qwen2:7b`, `qwen3-embedding:8b`
- Rerank: `bge-reranker-v2-m3`

### New Model Notes (2026-02-25)

**`qwen3.5`** - Qwen3 series reasoning model:
- Default thinking mode enabled (cannot be disabled)
- Higher token consumption (~200-500+ tokens per request due to thinking output)
- Response time ~5-6s for simple queries
- Recommended for complex reasoning tasks only
- Keep at `c=1` for stable operation

## Stable Operation Policy

1. Default unknown/new models to `c=1`.
2. Use high-throughput whitelist only after model-level stress test passes.
3. Promote concurrency gradually: `1 -> 2 -> 4 -> 8`.
4. Roll back one level immediately if timeout, 5xx, or OOM appears.
5. Re-run stress baseline after model catalog changes (`/models`) or provider upgrades.

## Endpoint Map

See: `references/uni-api-llm-endpoints.md`
