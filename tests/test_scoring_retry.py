import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from app import anthropic, deepseek, gemini, openai_compat
from app.guardrails import prepare_candidate
from app.providers import ScoringUnavailable
from app.scorer import read_rubric, score_candidate, score_with_rubric

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "rubrics/ai-engineer.md"
RUBRIC = {"Python": 60.0, "Testing": 40.0}
CV = "Jo Example\nBuilt  Python services.\nWrote tests with\npytest daily."
CANDIDATE = prepare_candidate(CV, name="Jo Example")
SAMPLE = ROOT / "samples/cvs/01_strong.txt"
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
OK_REPLY = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}


def card(quote_python="Built Python services.", quote_testing=""):
    met = quote_python != ""
    return {"candidate_hash": CANDIDATE["candidate_hash"], "job_id": "j", "flagged_for_human": True,
            "notes": "n", "overall_score": 60.0 if met else 0.0,
            "verdict": "POSSIBLE_MATCH" if met else "WEAK_MATCH",
            "criteria": [
                {"criterion": "Python", "weight": 60.0, "status": "MET" if met else "NOT_FOUND",
                 "score": 60.0 if met else 0.0, "evidence_quote": quote_python},
                {"criterion": "Testing", "weight": 40.0, "status": "NOT_FOUND", "score": 0.0,
                 "evidence_quote": quote_testing}]}


class Script:
    """A fake `complete` that replays replies and records every conversation it was given."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, messages):
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def run(script):
    return score_with_rubric(CANDIDATE, complete=script, rubric=RUBRIC, guidance="g", job_id="j")


class ParsingAndEvidence(unittest.TestCase):
    def test_fenced_json_is_accepted(self):
        result, attempts = run(Script("```json\n" + json.dumps(card()) + "\n```"))
        self.assertEqual((result.overall_score, attempts), (60.0, 1))

    def test_text_around_the_json_is_ignored(self):
        script = Script("Here is the scorecard:\n" + json.dumps(card()) + "\nHope this helps!")
        self.assertEqual(run(script)[1], 1)

    def test_whitespace_differences_in_a_quote_are_accepted_and_quote_is_kept(self):
        for quote in ("Built Python services.", "Built   Python\nservices.", "Wrote tests with pytest daily."):
            with self.subTest(quote=quote):
                data = card(quote_python=quote)
                result, attempts = run(Script(json.dumps(data)))
                self.assertEqual(result.criteria[0].evidence_quote, quote)  # stored as the model wrote it
                self.assertEqual(attempts, 1)

    def test_a_quote_that_is_not_in_the_cv_is_rejected_after_one_retry(self):
        bad = json.dumps(card(quote_python="Built Rust services."))
        script = Script(bad, bad)
        with self.assertRaisesRegex(ValueError, "not copied exactly"):
            run(script)
        self.assertEqual(len(script.calls), 2)

    def test_fuzzy_matches_are_still_rejected(self):
        bad = json.dumps(card(quote_python="built python services"))
        with self.assertRaisesRegex(ValueError, "not copied exactly"):
            run(Script(bad, bad))


class Retry(unittest.TestCase):
    def test_exactly_one_retry_then_success_reports_two_attempts(self):
        script = Script("not json at all", json.dumps(card()))
        result, attempts = run(script)
        self.assertEqual((attempts, len(script.calls)), (2, 2))

    def test_never_more_than_one_retry(self):
        script = Script("nope", "still nope", json.dumps(card()))
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            run(script)
        self.assertEqual(len(script.calls), 2)

    def test_retry_feedback_names_the_criterion_but_never_cv_or_model_text(self):
        secret = "Built Rust services."
        script = Script(json.dumps(card(quote_python=secret)), json.dumps(card()))
        run(script)
        first, second = script.calls
        self.assertEqual(second[:2], first[:2])
        self.assertEqual(second[2]["role"], "assistant")
        feedback = second[3]["content"]
        self.assertEqual(second[3]["role"], "user")
        self.assertIn("'Python'", feedback)
        self.assertIn("Quote not found in CV", feedback)
        self.assertNotIn(secret, feedback)
        self.assertNotIn("Jo Example", feedback)

    def test_scoring_unavailable_is_not_retried(self):
        script = Script(ScoringUnavailable("down"), json.dumps(card()))
        with self.assertRaises(ScoringUnavailable):
            run(script)
        self.assertEqual(len(script.calls), 1)

    def test_other_transport_errors_are_not_retried(self):
        script = Script(ValueError("provider failed"), json.dumps(card()))
        with self.assertRaisesRegex(ValueError, "provider failed"):
            run(script)
        self.assertEqual(len(script.calls), 1)


class BothRubricRoutes(unittest.TestCase):
    def _reply(self, messages):
        payload = json.loads(messages[1]["content"])
        return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
            overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="stub",
            criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                      for k, v in payload["rubric"].items()]))

    def test_file_rubric_route(self):
        result = score_candidate(SAMPLE, name="Amina Example", complete=self._reply, rubric_path=RUBRIC_PATH)
        self.assertEqual(result.overall_score, 0)

    def test_job_rubric_route(self):
        candidate = prepare_candidate(SAMPLE.read_text(encoding="utf-8"), name="Amina Example")
        result, attempts = score_with_rubric(candidate, complete=self._reply, rubric=read_rubric(RUBRIC_PATH),
                                             guidance="per-job guidance", job_id="job-1")
        self.assertEqual((result.job_id, attempts), ("job-1", 1))


class Transports(unittest.TestCase):
    def test_temperature_zero_and_json_mode_are_requested(self):
        with patch("app.openai_compat.urlopen", return_value=io.BytesIO(json.dumps(OK_REPLY).encode())) as send:
            openai_compat.complete(MESSAGES, base_url="http://x/v1", label="Ollama", model="m")
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual((body["temperature"], body["response_format"]), (0, {"type": "json_object"}))

        with patch("app.deepseek.urlopen", return_value=io.BytesIO(json.dumps(OK_REPLY).encode())) as send:
            deepseek.complete(MESSAGES, key="k", model="m")
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual((body["temperature"], body["response_format"]), (0, {"type": "json_object"}))

    def test_unsupported_json_mode_falls_back_once_and_logs_only_the_provider(self):
        rejected = HTTPError("http://x", 400, "bad", {}, io.BytesIO(b"private model text"))
        with patch("app.openai_compat.urlopen",
                   side_effect=[rejected, io.BytesIO(json.dumps(OK_REPLY).encode())]) as send, \
                self.assertLogs("uvicorn.error", "WARNING") as logs:
            self.assertEqual(openai_compat.complete(MESSAGES, base_url="http://x/v1", label="Groq", model="m"), "{}")
        retried = json.loads(send.call_args.args[0].data)
        self.assertNotIn("response_format", retried)
        self.assertNotIn("temperature", retried)
        self.assertEqual(logs.output, ["WARNING:uvicorn.error:Groq rejected temperature/json mode; retried without it"])

    def test_anthropic_and_gemini_send_the_whole_conversation_with_temperature_zero(self):
        convo = MESSAGES + [{"role": "assistant", "content": "prev"}, {"role": "user", "content": "fix"}]
        reply = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}
        with patch("app.anthropic.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            anthropic.complete(convo, key="k", model="m")
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual(body["temperature"], 0)
        self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])

        reply = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
        with patch("app.gemini.load_dotenv"), \
                patch("app.gemini.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            gemini.complete(convo, key="k", model="gemini-test")
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual(body["generationConfig"]["temperature"], 0)
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])


if __name__ == "__main__":
    unittest.main()
