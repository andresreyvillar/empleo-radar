import json
import tempfile
import unittest
from pathlib import Path

from radar.site import build_site
from radar.text import markdown_to_text


class SiteTests(unittest.TestCase):
    def test_builds_self_contained_page_with_escaped_data(self):
        state = {"matches": [{"id": "x:1", "title": "PM </script><b>", "company": "ACME", "location": "Vigo",
                              "url": "https://example.test/1", "score": 60, "modality": "galicia", "source": "linkedin",
                              "signals": ["+Agile"], "description": "texto", "posted": "2026-09-01",
                              "notified_at": "2026-09-01T10:00:00+00:00"}],
                 "last_run": {"at": "2026-09-01T10:00:00+00:00", "stats": {"linkedin": {"fetched": 1, "candidates": 1, "accepted": 1, "errors": []}}}}
        with tempfile.TemporaryDirectory() as tmp:
            out = build_site(state, Path(tmp))
            html = out.read_text(encoding="utf-8")
            self.assertTrue((Path(tmp) / ".nojekyll").exists())
            self.assertIn('id="data"', html)
            self.assertNotIn("</script><b>", html.split('id="data"')[1].split("</script>")[0])
            payload = html.split('type="application/json">')[1].split("</script>")[0]
            self.assertEqual(json.loads(payload)["matches"][0]["company"], "ACME")


class TextTests(unittest.TestCase):
    def test_markdown_escapes_are_removed_and_lines_kept(self):
        self.assertEqual(markdown_to_text("Banda salarial: 25\\.000 \\- 30\\.000 €\n\n\n\n**I\\+D\\+i**"),
                         "Banda salarial: 25.000 - 30.000 €\n\nI+D+i")


if __name__ == "__main__":
    unittest.main()
