import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUN_UI_SMOKE = os.getenv("RUN_UI_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(RUN_UI_SMOKE, "requires RUN_UI_SMOKE=1")
class OwnerPortalBrowserTests(unittest.TestCase):
    def test_review_capture_exercises_desktop_mobile_and_accessibility(self):
        with tempfile.TemporaryDirectory(prefix="owner-review-") as output:
            result = subprocess.run(
                [
                    os.environ.get("PYTHON") or sys.executable,
                    "scripts/capture_owner_portal_review.py",
                    "--output-dir",
                    output,
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            expected = {
                "desktop-login.png",
                "desktop-dashboard.png",
                "desktop-editor.png",
                "desktop-diff.png",
                "desktop-history.png",
                "desktop-profile.png",
                "desktop-superadmin-moderation.png",
                "mobile-login.png",
                "mobile-dashboard.png",
                "mobile-editor.png",
                "mobile-diff.png",
                "mobile-history.png",
                "index.html",
                "review-metrics.json",
            }
            self.assertTrue(expected.issubset({path.name for path in Path(output).iterdir()}))


if __name__ == "__main__":
    unittest.main()
