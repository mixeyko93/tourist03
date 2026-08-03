from __future__ import annotations

import asyncio
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from tourist03.services.owners import _safe_change_response
from tourist03.settings import Settings
from tourist03.static_files import ProtectedStaticFiles
from tourist03.submission_media import (
    SubmissionMediaError,
    _copy_file_atomically,
    promote_staged_media,
)


class StagedMediaSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(prefix="turistika-staged-security-")
        self.root = Path(self.temp.name)
        self.settings = Settings(environment="test", upload_dir=str(self.root))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _staged_row(self, prefix: str = "owner-changes/staged") -> dict:
        original = self.root / prefix / "source.png"
        thumbnail = self.root / prefix / "source.thumb.webp"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(b"safe-original")
        thumbnail.write_bytes(b"safe-thumbnail")
        return {
            "id": 42,
            "storage_key": f"{prefix}/source.png",
            "thumbnail_storage_key": f"{prefix}/source.thumb.webp",
        }

    def test_promotion_is_compensatable_and_removes_staging_after_commit(self) -> None:
        row = self._staged_row()
        batch = promote_staged_media(
            self.settings,
            [row],
            expected_staged_prefix="owner-changes/staged",
            public_namespace="catalog/owner-changes/7",
        )
        public_key, thumbnail_key = batch.keys_by_id[42]
        self.assertEqual(public_key, "catalog/owner-changes/7/42.png")
        self.assertEqual(thumbnail_key, "catalog/owner-changes/7/42.thumb.webp")
        self.assertTrue((self.root / public_key).is_file())
        self.assertTrue((self.root / row["storage_key"]).is_file())

        batch.rollback()
        self.assertFalse((self.root / public_key).exists())
        self.assertTrue((self.root / row["storage_key"]).is_file())

        batch = promote_staged_media(
            self.settings,
            [row],
            expected_staged_prefix="owner-changes/staged",
            public_namespace="catalog/owner-changes/7",
        )
        batch.finalize()
        self.assertTrue((self.root / public_key).is_file())
        self.assertFalse((self.root / row["storage_key"]).exists())
        self.assertFalse((self.root / row["thumbnail_storage_key"]).exists())

    def test_promotion_rejects_path_traversal_and_wrong_namespace(self) -> None:
        outside = self.root.parent / "must-not-be-read.png"
        outside.write_bytes(b"outside")
        try:
            row = self._staged_row()
            row["storage_key"] = "owner-changes/staged/../../../must-not-be-read.png"
            with self.assertRaises(SubmissionMediaError):
                promote_staged_media(
                    self.settings,
                    [row],
                    expected_staged_prefix="owner-changes/staged",
                    public_namespace="catalog/owner-changes/7",
                )
            self.assertEqual(outside.read_bytes(), b"outside")
            with self.assertRaises(SubmissionMediaError):
                promote_staged_media(
                    self.settings,
                    [self._staged_row()],
                    expected_staged_prefix="owner-changes/staged",
                    public_namespace="../public",
                )
        finally:
            outside.unlink(missing_ok=True)

    def test_atomic_publish_never_replaces_a_concurrent_writer(self) -> None:
        source = self.root / "source.png"
        target = self.root / "catalog" / "public.png"
        source.write_bytes(b"same-safe-image")
        barrier = threading.Barrier(2)
        real_exists = Path.exists

        def synchronized_exists(path: Path) -> bool:
            if path == target:
                barrier.wait(timeout=2)
                return False
            return real_exists(path)

        with patch("pathlib.Path.exists", synchronized_exists):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda _: _copy_file_atomically(source, target),
                        range(2),
                    )
                )

        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(target.read_bytes(), b"same-safe-image")
        self.assertEqual(list(target.parent.glob(".*.tmp")), [])

    def test_static_mount_denies_staging_but_serves_promoted_media(self) -> None:
        staged = self.root / "uploads/owner-changes/staged/private.png"
        submission_staged = (
            self.root / "uploads/submissions/staged/private.png"
        )
        public = self.root / "uploads/catalog/owner-changes/7/public.png"
        staged.parent.mkdir(parents=True, exist_ok=True)
        submission_staged.parent.mkdir(parents=True, exist_ok=True)
        public.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(b"private")
        submission_staged.write_bytes(b"private-submission")
        public.write_bytes(b"public")
        app = FastAPI()
        app.mount("/static", ProtectedStaticFiles(directory=self.root), name="static")

        async def scenario() -> None:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                for path in (
                    "/static/uploads/owner-changes/staged/private.png",
                    "/static/uploads/submissions/staged/private.png",
                    (
                        "/static/uploads/catalog/owner-changes/7/"
                        "../owner-changes/staged/private.png"
                    ),
                ):
                    response = await client.get(path)
                    self.assertEqual(response.status_code, 404, path)
                response = await client.get(
                    "/static/uploads/catalog/owner-changes/7/public.png"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"public")

        asyncio.run(scenario())

    def test_owner_dto_never_exposes_storage_identifiers(self) -> None:
        safe = _safe_change_response(
            {
                "id": 7,
                "staged_media": [
                    {
                        "id": 42,
                        "storage_key": "owner-changes/staged/private.png",
                        "thumbnail_storage_key": (
                            "owner-changes/staged/private.thumb.webp"
                        ),
                        "preview_token": "secret-preview-token",
                        "safe_filename": "private.png",
                        "public_preview_url": "/api/owner/change-media/safe",
                    }
                ],
            }
        )
        encoded = json.dumps(safe)
        self.assertNotIn("storage_key", encoded)
        self.assertNotIn("preview_token", encoded)
        self.assertIn("/api/owner/change-media/safe", encoded)


if __name__ == "__main__":
    unittest.main()
