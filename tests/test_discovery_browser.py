import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


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
            metrics = json.loads(
                (artifact / "review-metrics.json").read_text(encoding="utf-8")
            )
            self.assertTrue(metrics["desktop"]["skip_link"]["hidden_on_load"])
            self.assertTrue(metrics["mobile"]["skip_link"]["target_focused"])
            for device in ("desktop", "mobile"):
                capture = metrics[device]["full_page_capture"]
                self.assertEqual(capture["scroll_y"], 0)
                self.assertFalse(capture["skip_focused"])
                self.assertLessEqual(capture["skip_link"]["bottom"], 0)
            self.assertEqual(metrics["desktop"]["layout"]["document_width"], 1440)
            self.assertEqual(metrics["mobile"]["layout"]["document_width"], 390)
            self.assertLessEqual(metrics["desktop"]["layout"]["map_canvas_top"], 650)
            self.assertGreaterEqual(
                metrics["desktop"]["layout"]["visible_map_pixels"],
                350,
            )
            self.assertLess(metrics["mobile"]["layout"]["preview_top"], 844)
            self.assertGreaterEqual(metrics["mobile"]["layout"]["preview_height"], 300)
            self.assertIn("mobile homepage without Leaflet", metrics["mobile"]["scenarios"])
            self.assertIn("map onboarding once", metrics["mobile"]["scenarios"])
            self.assertGreaterEqual(
                metrics["bundle"]["headroom_to_10_percent_gzip_bytes"],
                1024,
            )
            self.assertLessEqual(metrics["bundle"]["delta_percent"], 9.0)
            self.assertEqual(metrics["bundle"]["superadmin_assets_in_initial"], [])
            self.assertFalse(metrics["bundle"]["source_maps_included"])
            with Image.open(artifact / "desktop-home.png") as desktop:
                self.assertEqual(desktop.width, 1440)
            with Image.open(artifact / "mobile-home.png") as mobile:
                self.assertEqual(mobile.width, 390)
