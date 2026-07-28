import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUN_UI_SMOKE = os.getenv("RUN_UI_SMOKE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
RUN_FULL_REVIEW = os.getenv(
    "UNIVERSAL_REVIEW_FULL", ""
).strip().lower() in {"1", "true", "yes", "on"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(RUN_UI_SMOKE, "requires RUN_UI_SMOKE=1")
class UniversalCatalogBrowserTests(unittest.TestCase):
    def test_mixed_catalog_review_capture_and_accessibility(self):
        with tempfile.TemporaryDirectory(
            prefix="universal-catalog-review-"
        ) as output:
            command = [
                os.environ.get("PYTHON") or sys.executable,
                "scripts/capture_universal_catalog_review.py",
                "--output-dir",
                output,
            ]
            if not RUN_FULL_REVIEW:
                command.append("--skip-lighthouse")
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
                capture_output=True,
                timeout=480 if RUN_FULL_REVIEW else 300,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + "\n" + result.stderr,
            )

            output_dir = Path(output)
            expected = {
                "desktop-home.png",
                "desktop-map.png",
                "desktop-search.png",
                "desktop-filters.png",
                "desktop-accommodation-card.png",
                "desktop-service-card.png",
                "desktop-excursion-card.png",
                "desktop-owner-portal.png",
                "desktop-superadmin.png",
                "mobile-home.png",
                "mobile-map.png",
                "mobile-search.png",
                "mobile-filters.png",
                "mobile-service-card.png",
                "mobile-accommodation-card.png",
                "mobile-excursion-card.png",
                "mobile-owner-portal.png",
                "index.html",
                "review-metrics.json",
                "bundle-report.json",
                "verification-summary.md",
            }
            if RUN_FULL_REVIEW:
                expected.update(
                    {
                        "lighthouse-mobile.html",
                        "lighthouse-mobile.json",
                        "lighthouse-desktop.html",
                        "lighthouse-desktop.json",
                    }
                )
            missing = expected.difference(
                path.name for path in output_dir.iterdir()
            )
            self.assertEqual(missing, set(), f"missing review files: {missing}")

            metrics = json.loads(
                (output_dir / "review-metrics.json").read_text(
                    encoding="utf-8"
                )
            )
            assertions = metrics["browser_assertions"]
            self.assertGreaterEqual(assertions["mixed_kind_count"], 6)
            self.assertGreaterEqual(assertions["unique_marker_icons"], 6)
            self.assertTrue(assertions["six_kind_filters"])
            self.assertTrue(assertions["cross_entity_search"])
            self.assertTrue(assertions["schema_driven_cards"])
            self.assertTrue(assertions["owner_create_entry"])
            self.assertTrue(assertions["superadmin_entity_management"])
            self.assertTrue(assertions["telegram_independent"])
            self.assertTrue(assertions["public_bundle_within_ten_percent"])
            self.assertGreaterEqual(metrics["superadmin"]["entity_rows"], 6)

            for query in ("лодка", "рыбалка", "отель", "экскурсия"):
                self.assertIn(query, metrics["search"])
                self.assertIn(
                    metrics["search"][query]["expected_slug"],
                    metrics["search"][query]["result_slugs"],
                )

            for detail in metrics["details"].values():
                self.assertFalse(detail["horizontal_overflow"])
                self.assertEqual(detail["unnamed_visible_controls"], 0)
                self.assertIn("BreadcrumbList", detail["json_ld_types"])

            bundle = metrics["bundle"]
            self.assertLessEqual(
                bundle["after"]["gzip_bytes"],
                bundle["baseline"]["gzip_limit_plus_10_percent"],
            )

            if RUN_FULL_REVIEW:
                self.assertGreaterEqual(
                    metrics["lighthouse"]["mobile"]["categories"][
                        "performance"
                    ],
                    90,
                )
                self.assertEqual(
                    metrics["lighthouse"]["mobile"]["categories"][
                        "accessibility"
                    ],
                    100,
                )
                self.assertLessEqual(
                    metrics["lighthouse"]["mobile"]["cls"], 0.05
                )
                self.assertGreaterEqual(
                    metrics["lighthouse"]["desktop"]["categories"][
                        "performance"
                    ],
                    95,
                )
                self.assertEqual(
                    metrics["lighthouse"]["desktop"]["categories"][
                        "accessibility"
                    ],
                    100,
                )
                self.assertLessEqual(
                    metrics["lighthouse"]["desktop"]["cls"], 0.05
                )


if __name__ == "__main__":
    unittest.main()
