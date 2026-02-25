# uni-api-llm-prober-skill

批量验证 Uni-API 平台模型是否可调用的技能包，包含：

- `SKILL.md`：使用说明与触发场景
- `references/uni-api-llm-endpoints.md`：官方文档端点速查
- `references/performance/uni_api_full_model_stress_20260225.json`：全模型压测原始结果
- `references/performance/stability-baseline-2026-02-25.md`：稳定运行边界结论
- `scripts/probe_uni_api_models.py`：模型可用性批量探测脚本
- `scripts/stress_test_uni_api.py`：并发压力测试脚本

主命令：

- `python3 scripts/probe_uni_api_models.py --help`
- `python3 scripts/stress_test_uni_api.py --help`

测试位于：

- `tests/test_probe_uni_api_models.py`
- `tests/test_stress_test_uni_api.py`
