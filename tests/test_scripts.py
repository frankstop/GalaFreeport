from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScriptTests(unittest.TestCase):
    def test_workflow_summary_is_useful_with_or_without_baseline(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/workflow_summary.py"], cwd=ROOT, text=True, capture_output=True, check=True
        )
        self.assertIn("Gala Freeport–Merrick pipeline", result.stdout)
        self.assertTrue(
            "No healthy production snapshot" in result.stdout or "Status: **healthy**" in result.stdout
        )

    def test_workflow_has_daily_collection_and_fail_closed_publish_gate(self) -> None:
        workflow = (ROOT / ".github/workflows/daily_crawl.yml").read_text()
        self.assertIn('cron: "17 5 * * *"', workflow)
        self.assertIn('timezone: "America/New_York"', workflow)
        self.assertIn("daily-gala-freeport-catalog", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn("python -m gala_freeport run --verbose", workflow)
        self.assertIn("python -m playwright install chromium", workflow)
        self.assertNotIn("playwright install --with-deps", workflow)
        self.assertIn("python -m unittest discover -v", workflow)
        self.assertIn("python scripts/check.py", workflow)
        self.assertIn("if: success()", workflow)
        self.assertIn("git add data/snapshots docs", workflow)


if __name__ == "__main__":
    unittest.main()
