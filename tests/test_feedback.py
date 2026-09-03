import json
import tempfile
import unittest
from pathlib import Path

from radar.feedback import Feedback
from radar.models import Job


def job(job_id, title, company):
    return Job(id=job_id, source="x", title=title, company=company, location="Madrid", url="https://example.test")


class FeedbackTests(unittest.TestCase):
    def test_discarded_by_id_and_by_twin_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feedback.json"
            path.write_text(json.dumps({"statuses": {"linkedin:1": "discarded", "linkedin:2": "saved"}}), encoding="utf-8")
            fb = Feedback(path)
            fb.learn_fingerprints([{"id": "linkedin:1", "title": "PMO", "company": "ACME Group"},
                                   {"id": "linkedin:2", "title": "Project Manager", "company": "Beta"}])
            self.assertTrue(fb.is_discarded(job("linkedin:1", "PMO", "ACME Group")))
            self.assertTrue(fb.is_discarded(job("indeed:9", "PMO", "ACME")))            # same offer, other portal
            self.assertFalse(fb.is_discarded(job("indeed:9", "PMO Senior", "ACME")))
            self.assertFalse(fb.is_discarded(job("linkedin:2", "Project Manager", "Beta")))  # saved, not discarded

    def test_missing_file(self):
        fb = Feedback(Path("/nonexistent/feedback.json"))
        self.assertFalse(fb.is_discarded(job("a:1", "PMO", "ACME")))


if __name__ == "__main__":
    unittest.main()
