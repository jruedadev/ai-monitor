import unittest

from collectors import openrouter


class TestOpenRouterCollector(unittest.TestCase):
    def test_missing_api_key_marks_unavailable(self):
        data = openrouter.collect(api_key=None, fetch=lambda url, key: {})
        self.assertTrue(data["unavailable"])
        self.assertIn("OPENROUTER_API_KEY", data["reason"])

    def test_successful_fetch_aggregates_by_model_and_day(self):
        fake_response = {
            "data": [
                {"model": "openai/gpt-5.5", "date": "2026-08-10",
                 "usage": 0.5, "prompt_tokens": 1000, "completion_tokens": 200},
                {"model": "openai/gpt-5.5", "date": "2026-08-11",
                 "usage": 0.25, "prompt_tokens": 500, "completion_tokens": 100},
                {"model": "anthropic/claude-sonnet-5", "date": "2026-08-11",
                 "usage": 1.0, "prompt_tokens": 2000, "completion_tokens": 300},
            ]
        }

        data = openrouter.collect(api_key="fake-key", fetch=lambda url, key: fake_response)

        self.assertFalse(data["unavailable"])
        self.assertEqual(data["models"]["openai/gpt-5.5"]["tokens"], 1000 + 200 + 500 + 100)
        self.assertAlmostEqual(data["models"]["openai/gpt-5.5"]["cost"], 0.75)
        self.assertEqual(data["models"]["openai/gpt-5.5"]["requests"], 2)
        self.assertIn("anthropic/claude-sonnet-5", data["models"])
        self.assertAlmostEqual(data["by_day"]["2026-08-11"]["cost"], 1.25)

    def test_malformed_response_marks_unavailable(self):
        data = openrouter.collect(api_key="fake-key", fetch=lambda url, key: "not a dict")
        self.assertTrue(data["unavailable"])
        self.assertIn("reason", data)

        data_none = openrouter.collect(api_key="fake-key", fetch=lambda url, key: None)
        self.assertTrue(data_none["unavailable"])
        self.assertIn("reason", data_none)

    def test_fetch_error_marks_unavailable_with_reason(self):
        def failing_fetch(url, key):
            raise RuntimeError("HTTP 401")

        data = openrouter.collect(api_key="bad-key", fetch=failing_fetch)
        self.assertTrue(data["unavailable"])
        self.assertIn("401", data["reason"])


if __name__ == "__main__":
    unittest.main()
