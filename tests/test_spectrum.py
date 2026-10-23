"""Hardware-independent tests of native RTL-SDR CSV, bounds and recovery."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from amp_scan import cli, spectrum

class SpectrumTests(unittest.TestCase):
    def test_native_csv(self):
        content = (b"2026-10-23, 09:15:00, 88000000, 88250000, 125000, 100, -65.3, -71.0\n"
                   b"2026-10-23, 09:15:10, 88250000, 88500000, 125000, 100, -50.0, -60.0\n")
        readings = list(spectrum.observations(content, "rtl_power"))
        self.assertEqual(len(readings), 4)
        self.assertEqual(readings[0], (88062500.0, -65.3))
        result = spectrum.summarize(readings, {}, "rtl_power")
        self.assertEqual(result["reported_bins"], 1)
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["bins"][0]["peak_dbm"], -50.0)

    def test_invalid_numeric_samples(self):
        content = b"88000000,nan\n90000000,-60\n91000000,inf\n91000000,bogus\n"
        self.assertEqual(list(spectrum.observations(content, "numeric")), [(90000000, -60.)])

    def test_coarsens_when_above_budget(self):
        readings = [(30e6 + i * 1e6, -70. + (i % 5)) for i in range(80)]
        result = spectrum.summarize(readings, {"MAX_REPORT_BINS": "8"}, "numeric")
        self.assertEqual(result["reported_bins"], 8)
        self.assertEqual(sum(b["count"] for b in result["bins"]), 80)
        self.assertTrue(result["coarsened"])

    def test_runner_uses_single_shot_rtl_power(self):
        runner = Mock(return_value=Mock(stdout=b"2026-10-23, 09:15:00, 88000000, 88250000, 125000, 100, -65, -80\n"))
        reading = spectrum.spectrum({"SPECTRUM_MODE":"rtl_power"}, runner=runner)
        self.assertEqual(runner.call_args.args[0],
                         ["/usr/bin/rtl_power", "-f", "88M:108M:125k", "-i", "10", "-1"])
        self.assertEqual(reading["sample_count"], 2)

    def test_range_rejects_shell_injection_and_reversed_range(self):
        for value in ("88M:108M:125k;touch /tmp/hack", "88M:10M:125k",
                      "88M:108M:3M", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                spectrum.checked_ranges(value)

    def test_collector_records_health_when_sdr_missing(self):
        with tempfile.TemporaryDirectory() as workdir:
            cfg={"DB_PATH":str(Path(workdir)/"telemetry.db"),"SPECTRUM_MODE":"rtl_power"}
            with patch.object(cli, "spectrum", side_effect=FileNotFoundError("rtl_power")):
                row = cli.collect(cfg)
            self.assertEqual(row["spectrum"]["error"], "FileNotFoundError")
            self.assertEqual(cli.status(cfg)["pending"], 1)

if __name__ == "__main__":
    unittest.main()
