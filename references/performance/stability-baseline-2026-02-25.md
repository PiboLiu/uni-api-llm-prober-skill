# Uni-API Full-Model Stability Baseline (2026-02-25)

## Scope

- Environment date (UTC): 2026-02-25
- Model source: `GET /models`
- Total models: 20
- Tested targets: 20
- Kinds covered: `chat`, `embedding`, `rerank`, `analysis`, `ocr_pdf`

## Test Profile

- Concurrency levels: `1,2,4,8`
- Requests per level: `4`
- Timeout per request: `15s`
- Early-stop rule: stop higher levels for a model when `success_rate < 0.9`
- Recommendation threshold: `success_rate >= 99%` and `p95 <= 13.5s`

Raw JSON report:

- `references/performance/uni_api_full_model_stress_20260225.json`

## Safe Defaults By Kind

| Kind | Safe default concurrency | Tested model count |
|---|---:|---:|
| chat | 1 | 13 |
| embedding | 1 | 3 |
| rerank | 1 | 2 |
| analysis | 8 | 1 |
| ocr_pdf | 8 | 1 |

## Models Validated at c=8

- `chat`: `deepseek-v3:671b`, `qwen2.5-vl:72b`, `qwen3:235b`, `spark-x1:70b`, `gpt-oss-120b`
- `embedding`: `bge-large-zh:latest`
- `rerank`: `qwen3-reranker:8b`
- `analysis`: `S1-CitationCalculate`
- `ocr_pdf`: `deepseek-ocr`

## Models Restricted to c=1

- `chat`: `deepseek-r1:671b-64k`, `deepseek-r1:32b`, `deepseek-r1:671b`, `deepseek-r1:671b-0528`, `qwq:32b`, `S1-Base-Lite`, `S1-Base-Pro`, `S1-Base-Ultra`
- `embedding`: `gte-qwen2:7b`, `qwen3-embedding:8b`
- `rerank`: `bge-reranker-v2-m3`

## Representative Failure Signatures

- Read timeout at `c=1` on several chat/embedding models.
- HTTP 500 on `gte-qwen2:7b` embedding.
- HTTP 422 on `S1-Base-Lite` chat.
- CUDA OOM (HTTP 422) on `bge-reranker-v2-m3` at `c=2`.

## Operational Guidance

1. Start production with per-kind safe defaults.
2. Allow only c=8 models into high-throughput pool.
3. Any timeout/5xx/OOM triggers immediate fallback to lower concurrency.
4. Re-run baseline after model list changes or provider upgrades.
