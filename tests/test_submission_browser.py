import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUN_UI_SMOKE = os.getenv("RUN_UI_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(RUN_UI_SMOKE, "requires RUN_UI_SMOKE=1")
class SubmissionBrowserSmokeTests(unittest.TestCase):
    def test_form_tracking_and_moderation_review_capture(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/capture_placement_submissions_review.py",
                    "--output-dir",
                    temporary_dir,
                ],
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metrics = json.loads(
                (Path(temporary_dir) / "review-metrics.json").read_text(encoding="utf-8")
            )
            self.assertGreaterEqual(metrics["image_count"], 25)
            self.assertEqual(metrics["form_steps"], 8)
            self.assertTrue(metrics["browser_assertions"]["required_steps_cannot_be_skipped"])
            self.assertTrue(metrics["browser_assertions"]["indexeddb_restore"])
            self.assertTrue(metrics["browser_assertions"]["coordinate_picker_desktop"])
            self.assertTrue(metrics["browser_assertions"]["coordinate_picker_mobile"])
            self.assertTrue(metrics["browser_assertions"]["coordinate_picker_manual_input"])
            self.assertTrue(metrics["browser_assertions"]["coordinate_picker_range_validation"])
            for filename in (
                "desktop-step-1-applicant.png",
                "desktop-submit-success.png",
                "desktop-tracking-status.png",
                "desktop-superadmin-detail.png",
                "mobile-preview.png",
                "mobile-superadmin-detail.png",
                "index.html",
            ):
                self.assertTrue((Path(temporary_dir) / filename).is_file(), filename)


if __name__ == "__main__":
    unittest.main()
