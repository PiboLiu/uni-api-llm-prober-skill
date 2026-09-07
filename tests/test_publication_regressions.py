from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import probe_uni_api_models as probe
import stress_test_uni_api as stress


class PublicationRegressionTests(unittest.TestCase):
    def test_unrelated_key_never_triggers_network(self):
        for module in (probe, stress):
            with self.subTest(module=module.__name__), patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-unrelated"}, clear=True), patch.object(sys, "argv", ["test"]), patch.object(module, "_http_json") as http, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.parse_args().api_key, "")
                self.assertEqual(module.main(), 2)
                http.assert_not_called()

    def test_explicit_and_dedicated_keys(self):
        for module in (probe, stress):
            for env, argv, expected in [
                ({"API_UNI_TOKEN": "token"}, [], "token"),
                ({"UNI_API_KEY": "key", "API_UNI_TOKEN": "token"}, [], "key"),
                ({"UNI_API_KEY": "", "API_UNI_TOKEN": "token"}, [], "token"),
                ({"UNI_API_KEY": "key"}, ["--api-key", "explicit"], "explicit"),
            ]:
                with self.subTest(module=module.__name__, env=env), patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["test"] + argv):
                    self.assertEqual(module.parse_args().api_key, expected)

    def test_ocr_fails_closed(self):
        for validate in (probe.validate_response, stress._is_success):
            self.assertTrue(validate("ocr_pdf", {"status": "healthy"}))
            for status in ("unhealthy", "degraded", "unknown", "", None, True):
                self.assertFalse(validate("ocr_pdf", {"status": status}))
            self.assertFalse(validate("ocr_pdf", {"status": "healthy", "error": "failed"}))

    def test_ocr_is_optional_and_health_only(self):
        args = dict(base_url="unused", api_key="dummy", model_id="deepseek-ocr", ocr_image_url="", timeout=1)
        with patch.object(probe, "_http_json", return_value=(200, {"status": "healthy"})) as http:
            self.assertEqual(probe.probe_one_model(**args, include_special_endpoints=False)["status"], "skipped")
            http.assert_not_called()
            result = probe.probe_one_model(**args, include_special_endpoints=True)
            self.assertEqual(result["scope"], "health_only")
            self.assertEqual(http.call_args.kwargs["endpoint"], "/deepseek-ocr/health")

    def test_undersized_batch_rejected_without_requests(self):
        with patch.object(stress, "_run_one") as request:
            with self.assertRaises(ValueError):
                stress.run_level(base_url="unused", api_key="dummy", kind="chat", model_id="dummy", concurrency=8, requests=4, timeout=1)
            request.assert_not_called()
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "argv", ["test", "--api-key", "dummy", "--requests-per-level", "4"]), patch.object(stress, "run_level") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(stress.main(), 2)
            run.assert_not_called()

    def test_recommendations_require_sufficient_samples(self):
        row = dict(kind="chat", concurrency=8, requests=4, total=4, success_rate=1, p95_ms=50)
        self.assertIsNone(stress.build_recommendations([row], 15)["chat"]["recommended_concurrency"])
        row.update(requests=16, total=16)
        self.assertEqual(stress.build_recommendations([row], 15)["chat"]["recommended_concurrency"], 8)
        row["success_rate"] = 0
        self.assertIsNone(stress.build_recommendations([row], 15)["chat"]["recommended_concurrency"])
        row.update(kind="ocr_pdf", success_rate=1)
        self.assertIsNone(stress.build_recommendations([row], 15)["ocr_pdf"]["recommended_concurrency"])

    def test_valid_batch_keeps_requested_count(self):
        with patch.object(stress, "_run_one", return_value={"ok": True, "latency_ms": 1, "error": ""}) as request:
            result = stress.run_level(base_url="unused", api_key="dummy", kind="chat", model_id="dummy", concurrency=8, requests=16, timeout=1)
            self.assertEqual(request.call_count, 16)
            self.assertEqual(result["total"], 16)
            self.assertEqual(result["scope"], "inference")
