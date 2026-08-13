import os
import tempfile
import unittest

import history
from collectors import sync_pricing


class TestSyncPricing(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = tmp.name
        history.ensure_schema(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_write_upserts_snapshot_into_pricing_table(self):
        sync_pricing.write(db_path=self.db_path)

        import sqlite3
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM pricing")
        count = cur.fetchone()[0]
        con.close()
        self.assertEqual(count, len(sync_pricing.SNAPSHOT))

    def test_check_returns_true_when_table_matches_snapshot(self):
        sync_pricing.write(db_path=self.db_path)
        self.assertTrue(sync_pricing.check(db_path=self.db_path))

    def test_check_returns_false_when_table_is_stale(self):
        # La tabla arranca vacía (sin sync_pricing.write), así que difiere del SNAPSHOT.
        self.assertFalse(sync_pricing.check(db_path=self.db_path))


if __name__ == "__main__":
    unittest.main()
