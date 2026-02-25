from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from probe_uni_api_models import (  # type: ignore
    build_probe_request,
    classify_model,
    collect_model_ids,
    summarize_results,
    validate_response,
)


class UniApiProbeUnitTest(unittest.TestCase):
    def test_classify_model_routes_expected_categories(self) -> None:
        self.assertEqual(classify_model("qwen-max"), "chat")
        self.assertEqual(classify_model("BAAI/bge-large-zh-v1.5"), "embedding")
        self.assertEqual(classify_model("gte-qwen2:7b"), "embedding")
        self.assertEqual(classify_model("rerank-v2-m3"), "rerank")
        self.assertEqual(classify_model("web-search"), "web_search")
        self.assertEqual(classify_model("ai-search"), "ai_search")
        self.assertEqual(classify_model("deepseek-ocr"), "ocr_pdf")
        self.assertEqual(classify_model("S1-CitationCalculate"), "analysis")

    def test_collect_model_ids_from_models_response(self) -> None:
        payload = {
            "data": [
                {"id": "qwen-max", "object": "model"},
                {"id": "rerank-v2-m3", "object": "model"},
            ]
        }
        self.assertEqual(collect_model_ids(payload), ["qwen-max", "rerank-v2-m3"])

    def test_build_probe_request_for_chat_model(self) -> None:
        req = build_probe_request(model_id="qwen-max", kind="chat", ocr_image_url="")
        self.assertEqual(req["endpoint"], "/chat/completions")
        payload = req["payload"]
        self.assertEqual(payload["model"], "qwen-max")
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_build_probe_request_for_ocr_uses_health_endpoint(self) -> None:
        req = build_probe_request(model_id="deepseek-ocr", kind="ocr_pdf", ocr_image_url="")
        self.assertEqual(req["endpoint"], "/deepseek-ocr/health")
        self.assertEqual(req["method"], "GET")

    def test_build_probe_request_for_analysis_kind(self) -> None:
        req = build_probe_request(model_id="S1-CitationCalculate", kind="analysis", ocr_image_url="")
        self.assertEqual(req["endpoint"], "/analysis")
        payload = req["payload"]
        self.assertEqual(payload["model"], "S1-CitationCalculate")
        self.assertIn("content", payload)

    def test_validate_response_checks_key_shapes(self) -> None:
        self.assertTrue(validate_response("chat", {"choices": [{"message": {"content": "ok"}}]}))
        self.assertTrue(validate_response("embedding", {"data": [{"embedding": [0.1, 0.2]}]}))
        self.assertTrue(validate_response("rerank", {"results": [{"index": 0, "relevance_score": 0.9}]}))
        self.assertTrue(validate_response("analysis", {"code": 200, "data": {"res": "ok"}}))
        self.assertTrue(validate_response("ocr_pdf", {"status": "healthy"}))
        self.assertFalse(validate_response("chat", {"choices": []}))

    def test_summarize_results_counts_success_failed_skipped(self) -> None:
        summary = summarize_results(
            [
                {"status": "success"},
                {"status": "failed"},
                {"status": "skipped"},
                {"status": "success"},
            ]
        )
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
