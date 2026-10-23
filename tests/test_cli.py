import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amp_scan import cli

class NodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = {"DB_PATH": str(Path(self.tmp.name) / "data.db"),
                    "NODE_ID": "test-node"}

    def test_collect_and_status(self):
        payload = cli.collect(self.cfg)
        self.assertEqual(payload["schema"], "amp-scan.v1")
        self.assertEqual(cli.status(self.cfg)["pending"], 1)

    def test_reporting_disabled_by_default(self):
        cli.collect(self.cfg)
        self.assertEqual(cli.report(self.cfg), {"sent": 0, "disabled": True})
        self.assertEqual(cli.status(self.cfg)["pending"], 1)

    def test_http_rejected(self):
        with self.assertRaises(ValueError):
            cli.report({**self.cfg, "REPORT_URL": "http://example.org/upload"})

    def test_retention(self):
        cli.collect(self.cfg)
        with cli.connect(self.cfg) as con:
            con.execute("UPDATE reports SET created_at=1")
            cli.purge(con, self.cfg, now=1000000000)
        self.assertEqual(cli.status(self.cfg)["pending"], 0)

    def test_spectrum_disabled(self):
        self.assertEqual(cli.spectrum(self.cfg), {"enabled": False})

if __name__ == "__main__":
    unittest.main()
