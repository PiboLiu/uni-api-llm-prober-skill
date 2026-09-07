# uni-api-llm-prober-skill

批量验证 Uni-API 平台模型是否可调用的技能包，包含：

- `SKILL.md`：使用说明与触发场景
- `references/uni-api-llm-endpoints.md`：官方文档端点速查
- `references/performance/uni_api_full_model_stress_20260225.json`：全模型压测原始结果
- `references/performance/stability-baseline-2026-02-25.md`：历史压测的证据限制与更正
- `scripts/probe_uni_api_models.py`：模型可用性批量探测脚本
- `scripts/stress_test_uni_api.py`：并发压力测试脚本

主命令：

- `python3 scripts/probe_uni_api_models.py --help`
- `python3 scripts/stress_test_uni_api.py --help`

测试位于：

- `tests/test_probe_uni_api_models.py`
- `tests/test_stress_test_uni_api.py`

## Validation and limitations

Requires Python 3.10+; scripts use only the standard library.
Run offline tests with `python -m unittest discover -s tests -v`.

Credentials come only from `UNI_API_KEY`, `API_UNI_TOKEN`, or `--api-key`.
OCR support is a health check only, not image recognition. Historical c=8 and
production stability recommendations are withdrawn; see the corrected baseline.
Use at least as many requests per level as the largest worker limit. Recommendations
are sample-based candidates, and null means capacity was not validated.
