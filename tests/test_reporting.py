"""Local store-forward reporter delivery and outage recovery, without network."""
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
from amp_scan import cli

class Reply:
    status = 202
    def __enter__(self): return self
    def __exit__(self, *_): return False

class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root = Path(self.dir.name)
        token = root / "report.token"
        token.write_text("fixture-token\n", encoding="ascii")
        self.cfg = {"DB_PATH": str(root / "report.db"), "NODE_ID": "fixture",
                    "REPORT_URL": "https://ingest.example.org/telemetry",
                    "REPORT_TOKEN_FILE": str(token)}
        self.event = cli.collect(self.cfg)

    def test_outage_keeps_event_pending(self):
        sender = Mock()
        sender.open.side_effect = urllib.error.URLError("network offline")
        with patch.object(cli.urllib.request, "build_opener", return_value=sender):
            result = cli.report(self.cfg)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(cli.status(self.cfg)["pending"], 1)

    def test_acknowledged_report_is_idempotent(self):
        sender = Mock()
        sender.open.return_value = Reply()
        with patch.object(cli.urllib.request, "build_opener", return_value=sender):
            sent = cli.report(self.cfg)
            again = cli.report(self.cfg)
        self.assertEqual(sent["sent"], 1)
        self.assertEqual(again["sent"], 0)
        self.assertEqual(cli.status(self.cfg)["delivered_retained"], 1)
        req = sender.open.call_args_list[0].args[0]
        self.assertEqual(req.get_header("Idempotency-key"), self.event["event_id"])
        self.assertEqual(req.get_header("Authorization"), "Bearer fixture-token")

    def test_status_retains_only_error_type(self):
        result = cli.status(self.cfg)
        self.assertEqual(result["pending"], 1)
        self.assertIsNone(result["last_spectrum_error"])
        self.assertGreaterEqual(result["oldest_pending_age_seconds"], 0)

if __name__ == "__main__":
    unittest.main()
