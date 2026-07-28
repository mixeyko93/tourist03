import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUN_BROWSER = os.getenv("RUN_BROWSER_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(RUN_BROWSER, "requires RUN_BROWSER_SMOKE=1")
class TourismDiscoveryBrowserTests(unittest.TestCase):
    def test_review_browser_regression(self):
        with tempfile.TemporaryDirectory(prefix="tourism-discovery-browser-") as directory:
            completed = subprocess.run(
                [
                    os.environ.get("PYTHON") or sys.executable,
                    "scripts/capture_tourism_discovery_review.py",
                    "--skip-lighthouse",
                    "--output-dir",
                    directory,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            artifact = Path(directory)
            self.assertTrue((artifact / "index.html").is_file())
            self.assertGreaterEqual(len(list(artifact.glob("desktop-*.png"))), 11)
            self.assertGreaterEqual(len(list(artifact.glob("mobile-*.png"))), 10)
