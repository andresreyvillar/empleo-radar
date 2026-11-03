import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import cli
from radar.ai import Review, Reviewer, ReviewUnavailable, save_reviews
from radar.config import load_config
from radar.feedback import Feedback
from radar.models import Job
from radar.sources.linkedin import LinkedInSource
from radar.state import State

VERDICT = {"apta": True, "encaje": 82, "modalidad": "remoto", "motivo": "PM remoto en consultora, sin requisitos técnicos.",
           "fortalezas": ["Coordinación de proveedores"], "carencias": ["Jira solo teórico"]}


def job(job_id="linkedin:1", title="Project Manager", company="ACME"):
    return Job(id=job_id, source="linkedin", title=title, company=company, location="España",
               url="https://example.test", description="Descripción completa " * 50)


def fake_claude(stdout="", returncode=0):
    def run(args, **kwargs):
        run.args = args
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return run


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def reviewer(self, run):
        with mock.patch("radar.ai.shutil.which", return_value="/bin/claude"), \
             mock.patch("radar.ai._read_profile", return_value="Perfil de prueba"):
            return Reviewer(self.cfg, run=run)

    def test_reads_structured_output_and_applies_it(self):
        run = fake_claude(json.dumps({"is_error": False, "structured_output": VERDICT}))
        review = self.reviewer(run).review(j := job())
        self.assertIn("--json-schema", run.args)
        self.assertEqual(run.args[run.args.index("--tools") + 1], "")      # no tools for the model
        review.apply(j)
        self.assertEqual((j.score, j.workplace, j.ai_reason), (82, "remoto", VERDICT["motivo"]))
        self.assertEqual(j.signals, ["+Coordinación de proveedores", "-Jira solo teórico"])

    def test_errors_make_the_job_wait_and_stop_after_three(self):
        reviewer = self.reviewer(fake_claude(json.dumps({"is_error": True, "result": "Not logged in"}), returncode=1))
        for _ in range(3):
            with self.assertRaises(ReviewUnavailable):
                reviewer.review(job())
        self.assertFalse(reviewer.available)

    def test_missing_claude_binary_or_profile(self):
        with mock.patch("radar.ai.shutil.which", return_value=None):
            self.assertFalse(Reviewer(self.cfg).available)
        with mock.patch("radar.ai.shutil.which", return_value="/bin/claude"), \
             mock.patch("radar.ai._read_profile", return_value=""):
            self.assertFalse(Reviewer(self.cfg).available)

    def test_verdict_is_coerced_and_bounded(self):
        review = Review.parse({"apta": 1, "encaje": "250", "modalidad": "<script>", "motivo": "x" * 5000,
                               "fortalezas": ["a"] * 10, "carencias": None})
        self.assertEqual((review.apta, review.encaje, review.modalidad), (True, 100, "sin especificar"))
        self.assertEqual((len(review.motivo), len(review.fortalezas), review.carencias), (400, 3, []))


class QueueTests(unittest.TestCase):
    def test_queued_job_keeps_full_description_and_stored_review_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            state = State(tmp / "seen.json")
            state.queue_review(job())
            self.assertGreater(len(state.review_queue()[0].description), 400)
            reviews = tmp / "reviews.json"
            save_reviews(reviews, {"linkedin:1": VERDICT})
            with mock.patch.object(cli, "REVIEWS_PATH", reviews):
                accepted = cli.drain_queue(state, Feedback(tmp / "feedback.json"), None, verbose=False)
            self.assertEqual([j.score for j in accepted], [82])
            self.assertEqual(state.review_queue(), [])
            self.assertEqual(len(state.data["matches"]), 1)

    def test_rejected_review_marks_the_job_and_unreviewed_jobs_stay_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            state = State(tmp / "seen.json")
            state.queue_review(job("linkedin:1"))
            state.queue_review(job("linkedin:2", title="PMO"))
            reviews = tmp / "reviews.json"
            save_reviews(reviews, {"linkedin:1": {**VERDICT, "apta": False, "motivo": "Presencial en Madrid"}})
            with mock.patch.object(cli, "REVIEWS_PATH", reviews):
                accepted = cli.drain_queue(state, Feedback(tmp / "feedback.json"), None, verbose=False)
            self.assertEqual(accepted, [])
            self.assertEqual(state.data["seen"]["linkedin:1"]["reason"], "ai:Presencial en Madrid")
            self.assertEqual([j.id for j in state.review_queue()], ["linkedin:2"])


class LinkedInQueryTests(unittest.TestCase):
    def test_exclusions_become_not_terms(self):
        cfg = load_config()
        cfg["sources"]["linkedin"]["exclude_keywords"] = ["developer", "data center"]
        self.assertEqual(LinkedInSource(cfg, 24).exclude, 'NOT developer NOT "data center"')


if __name__ == "__main__":
    unittest.main()
