import unittest
from collectors import pricing


class TestPricing(unittest.TestCase):
    def test_known_model_computes_cost(self):
        cost = pricing.cost_of(
            input_tokens=1_000_000, output_tokens=1_000_000,
            cache_read_tokens=0, cache_write_tokens=0,
            model="claude-sonnet-5",
        )
        self.assertAlmostEqual(cost, 3.0 + 15.0)

    def test_unknown_model_returns_none(self):
        cost = pricing.cost_of(
            input_tokens=1000, output_tokens=1000,
            cache_read_tokens=0, cache_write_tokens=0,
            model="some-brand-new-model-nobody-mapped-yet",
        )
        self.assertIsNone(cost)

    def test_none_model_returns_none(self):
        cost = pricing.cost_of(
            input_tokens=1000, output_tokens=1000,
            cache_read_tokens=0, cache_write_tokens=0,
            model=None,
        )
        self.assertIsNone(cost)

    def test_partial_model_name_match(self):
        # Codex/OpenAI model ids often carry suffixes; substring match must work
        cost = pricing.cost_of(
            input_tokens=1_000_000, output_tokens=0,
            cache_read_tokens=0, cache_write_tokens=0,
            model="gpt-5.5-fast",
        )
        self.assertIsNotNone(cost)


if __name__ == "__main__":
    unittest.main()
