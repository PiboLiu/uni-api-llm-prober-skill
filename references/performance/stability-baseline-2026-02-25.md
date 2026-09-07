# Historical stress sample (2026-02-25) — conclusions corrected

The original JSON is retained unchanged as historical evidence:
`references/performance/uni_api_full_model_stress_20260225.json`.

It records 20 models, worker limits 1, 2, 4, 8, four requests per level,
and a 15-second request timeout. A batch of four cannot exercise eight concurrent
requests. The previous c=8 whitelist and production safe-default table are withdrawn;
the recommendation fields in the archived JSON must not guide deployment.
Four successful requests also do not establish a 99% population success rate.

OCR used only the health endpoint, not image/PDF recognition. Its results cannot
establish OCR inference availability or throughput. Historical success validation
accepted any nonempty status, including unhealthy; raw responses were not archived,
so these classifications cannot be independently revalidated.

Observed failure labels include timeout, HTTP 500, HTTP 422, and HTTP 422 OOM.
The archived profile described early stopping; the bundled stress CLI has no
such mechanism. This snapshot contains no qwen3.5 measurement.

Before using a concurrency limit, run a fresh representative workload with sufficient
requests and inspect errors and latency. Current output recommendations are sample
candidates only; no qualifying level or OCR health-only data yields null.
