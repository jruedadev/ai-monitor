import os
import tempfile
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


class TestPricingFromSQLite(unittest.TestCase):
    # NOTA: adaptado a la firma real de cost_of() en este repo
    # (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model),
    # no a la firma hipotética cost_of(model, usage) del brief de Task 13.
    # Se agrega `db_path` como kwarg final opcional, preservando compatibilidad
    # con los call sites existentes en claude_code.py/codex.py.
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def test_bootstraps_default_snapshot_on_first_use(self):
        cost = pricing.cost_of(
            input_tokens=1_000_000, output_tokens=0,
            cache_read_tokens=0, cache_write_tokens=0,
            model="claude-sonnet-5",
            db_path=self.db_path,
        )
        self.assertIsNotNone(cost)

    def test_unmapped_model_returns_none(self):
        cost = pricing.cost_of(
            input_tokens=100, output_tokens=0,
            cache_read_tokens=0, cache_write_tokens=0,
            model="totally-unknown-model-xyz",
            db_path=self.db_path,
        )
        self.assertIsNone(cost)


if __name__ == "__main__":
    unittest.main()
