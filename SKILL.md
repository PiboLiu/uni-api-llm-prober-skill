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
python3 scripts/probe_uni_api_models.py --include-special-endpoints
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
  --requests-per-level 16 \
  --timeout 15 \
  --json-output /tmp/uni_api_stress_chat_deepseek_v3.json
```

## Output Semantics

- `success`: API returned expected shape for this endpoint.
- `failed`: request failed or response shape does not match expected fields.
- `skipped`: model intentionally skipped (for example special endpoints not enabled, OCR health checks not enabled).

## Evidence and concurrency limits

The archived 2026-02-25 report contains 20 models. It used only four requests
per level, including the level labelled `8`; it cannot validate eight concurrent
requests or production stability. Historical recommendations in that raw JSON
are withdrawn. See `references/performance/stability-baseline-2026-02-25.md`.
No archived measurement supports the later qwen3.5 claims; those claims are removed.

- Set requests per level to at least the largest concurrency; insufficient batches
  are rejected before requests are sent. Use larger samples for meaningful estimates.
- `concurrency` is the configured worker limit, not measured server concurrency.
- Recommendations are candidates for the sampled workload, not production guarantees.
- No qualifying level yields `recommended_concurrency: null`, not a validated fallback.
- OCR checks only `GET /deepseek-ocr/health`, requires `status: healthy`, and reports
  `scope: health_only`. It does not submit images or measure OCR recognition capacity.
  OCR inference concurrency is always unvalidated (`null`).
- `--ocr-image-url` is retained as an ignored compatibility option.
- Only `UNI_API_KEY`, `API_UNI_TOKEN`, or an explicit `--api-key` supplies credentials.
  `OPENAI_API_KEY` is never read automatically. Use a key intended for the chosen base URL.
- The stress script runs every configured level; it does not implement early stopping.

## Endpoint Map

See: `references/uni-api-llm-endpoints.md`
