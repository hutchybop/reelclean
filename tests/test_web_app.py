"""Smoke tests for Flask web routes."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
import importlib.util


HAS_FLASK = importlib.util.find_spec("flask") is not None


@unittest.skipUnless(HAS_FLASK, "Flask not installed in current interpreter")
class FlaskAppTests(unittest.TestCase):
    def test_index_and_quality_job_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            os.environ["REELCLEAN_ALLOWED_DIRS"] = f"Test:{root}"
            os.environ["TMDB_API_KEY"] = ""
            os.environ["FLASK_SECRET_KEY"] = "test-secret"

            from app import create_app

            app = create_app()
            client = app.test_client()

            index_resp = client.get("/")
            self.assertEqual(index_resp.status_code, 200)
            self.assertIn(b"Create Job", index_resp.data)

            create_resp = client.post(
                "/jobs",
                data={"directory": str(root.resolve()), "mode": "quality_only"},
                follow_redirects=False,
            )
            self.assertEqual(create_resp.status_code, 302)
            self.assertIn("/quality", create_resp.location)


if __name__ == "__main__":
    unittest.main()
