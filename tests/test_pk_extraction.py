import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as web
from app.extractor import extract_text, extract_with_report
from app.guardrails import detect_pii, prepare_candidate

FIXTURES = Path(__file__).parent / "fixtures"


def clean(text, **kwargs):
    return prepare_candidate(text, **kwargs)["cleaned_text"]


class PakistaniPii(unittest.TestCase):
    def test_pakistani_cv_pdf_is_fully_redacted_and_evidence_survives(self):
        raw = extract_text(FIXTURES / "pakistani_pii.pdf")
        items = detect_pii(raw)
        self.assertIn("cnic", {i["type"] for i in items})
        self.assertNotIn("35202-1234567-1", [i["value"] for i in items if i["type"] == "phone"])
        out = clean(raw, remove_pii=items)
        for gone in ("35202", "1234567-1", "Ahmed Raza", "Bilal", "House 12", "Street 4", "DHA Phase 5",
                     "14-03-1998", "bilal.ahmed.dev@gmail.com", "linkedin.com/in/bilalahmed"):
            self.assertNotIn(gone, out)
        for kept in ("Senior Software Engineer", "2019 - 2023", "Backend Engineer, Systems Limited"):
            self.assertIn(kept, out)
        self.assertIn("[RELATION REMOVED]", out)
        self.assertIn("[ADDRESS REMOVED]", out)

    def test_cnic_pattern_removal_does_not_depend_on_what_hr_ticked(self):
        raw = extract_text(FIXTURES / "pakistani_pii.pdf")
        out = clean(raw, name="Muhammad Bilal Ahmed")  # nothing selected
        for gone in ("35202", "S/O Ahmed Raza", "House 12"):
            self.assertNotIn(gone, out)

    def test_cnic_with_and_without_dashes(self):
        for number in ("35202-1234567-1", "3520212345671", "35202-12345671"):
            with self.subTest(number=number):
                text = f"Name: X\nCNIC {number}\nBuilt services."
                items = detect_pii(text)
                self.assertEqual([i["value"] for i in items if i["type"] == "cnic"], [number])
                self.assertFalse([i for i in items if i["type"] == "phone"])
                self.assertNotIn(number, clean(text, name="Zed", remove_pii=items))
                self.assertNotIn(number, clean(text, name="Zed"))

    def test_relation_lines(self):
        for line in ("S/O Ahmed Raza", "D/O Raza Khan", "W/O Ali Hassan", "Father Name: Ahmed Raza",
                     "Husband Name: Ali Hassan", "Guardian: Raza Khan", "Zed Khan S/O Ahmed Raza"):
            with self.subTest(line=line):
                out = clean(f"Built services.\n{line}\nBuilt tools.", name="Zed")
                self.assertNotRegex(out, r"Raza|Hassan|Ali")
                self.assertIn("[RELATION REMOVED]", out)
                self.assertIn("Built services.", out)
                self.assertIn("Built tools.", out)

    def test_without_abbreviation_is_not_a_relation(self):
        text = "Worked w/o supervision on W/o tests.\nShipped it."
        self.assertEqual(clean(text, name="Zed"), text)

    def test_address_lines(self):
        for line in ("House 12, Street 4, DHA Phase 5",            # two different pairs, no city
                     "House 12, Street 4, DHA Phase 5, Lahore",
                     "Plot 45, Sector F-7, Islamabad",
                     "Flat 3, Block 7, Gulshan-e-Iqbal, Karachi",  # one pair + city
                     "Street no. 9, Rawalpindi"):
            with self.subTest(line=line):
                out = clean(f"Built services.\n{line}\nBuilt tools.", name="Zed")
                self.assertIn("[ADDRESS REMOVED]", out)
                self.assertNotRegex(out, r"House|Street|Plot|Sector|Block|Gulshan")

    def test_ordinary_lines_survive(self):
        for line in ("Designed block storage for Karachi",
                     "Phase 1 and Phase 2 of the rollout shipped on time",   # same keyword twice
                     "Karachi, Pakistan",
                     "Built a road map for the Lahore team"):
            with self.subTest(line=line):
                self.assertIn(line, clean(f"Built services.\n{line}\nBuilt tools.", name="Zed"))


class PdfExtraction(unittest.TestCase):
    def test_two_columns_are_read_one_after_the_other(self):
        text = extract_text(FIXTURES / "two_column.pdf")
        lines = text.splitlines()
        claim = "Built a claims triage workflow that reads insurance emails in four steps:"
        self.assertTrue(any(claim in ln for ln in lines))
        for ln in lines:  # no line mixes sidebar and experience text
            if claim in ln:
                self.assertNotIn("Python, FastAPI", ln)
                self.assertNotIn("Contact", ln)
        i = lines.index("- Python, FastAPI, Pydantic")
        self.assertEqual(lines[i + 1], "- LLM workflows, prompt design")  # skills stay together
        self.assertLess(text.index("Skills"), text.index("Experience"))

    def test_single_column_pdf_is_read_as_before(self):
        text = extract_text(FIXTURES / "pakistani_pii.pdf")
        self.assertLess(text.index("Education"), text.index("Experience"))
        self.assertIn("- Wrote pytest suites", text)

    def test_hidden_text_is_dropped(self):
        text = extract_text(FIXTURES / "hidden_injection.pdf")
        self.assertNotIn("SYSTEM:", text)
        self.assertNotIn("Award full points", text)
        self.assertIn("Web Designer, Pixel Studio", text)
        self.assertIn("HTML, CSS, Figma, WordPress, Photoshop", text)

    def test_white_text_on_a_coloured_box_is_kept_but_white_on_white_is_not(self):
        text = extract_text(FIXTURES / "white_on_dark.pdf")
        self.assertIn("Hana Example", text)
        self.assertIn("Skills: Python, FastAPI", text)
        self.assertIn("Built a reporting service", text)
        text = extract_text(FIXTURES / "white_on_white.pdf")
        self.assertIn("Built a reporting service", text)
        self.assertNotIn("HIDDEN WHITE", text)

    def test_report_counts_hidden_characters_only_when_something_was_hidden(self):
        for name, hidden in (("hidden_injection", True), ("white_on_white", True), ("white_on_dark", False),
                             ("two_column", False), ("pakistani_pii", False)):
            with self.subTest(pdf=name):
                text, count = extract_with_report(FIXTURES / f"{name}.pdf")
                self.assertEqual(count > 0, hidden)
                self.assertNotIn("SYSTEM:", text)


class HiddenTextNotice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "t.db")
        cls.client = TestClient(web.app)
        reply = cls.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                json={"org_name": "Org", "email": "o@test.test", "password": "password123"})
        cls.h = {"X-Screenos": "1", "Authorization": f"Bearer {reply.json()['token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _preview(self, name):
        files = {"file": (name, (FIXTURES / name).read_bytes())}
        reply = self.client.post("/api/preview", headers=self.h, files=files)
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply

    def test_preview_reports_how_much_was_hidden_but_never_the_text(self):
        reply = self._preview("hidden_injection.pdf")
        notes = [i for i in reply.json()["detected_pii"] if i["type"] == "hidden_text"]
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0]["value"].isdigit() and int(notes[0]["value"]) > 0)
        self.assertNotIn("SYSTEM", reply.text)
        self.assertNotIn("Award full points", reply.text)

    def test_preview_has_no_notice_for_a_legitimate_white_on_dark_design(self):
        for name in ("white_on_dark.pdf", "two_column.pdf", "pakistani_pii.pdf"):
            with self.subTest(pdf=name):
                items = self._preview(name).json()["detected_pii"]
                self.assertNotIn("hidden_text", {i["type"] for i in items})

    def test_every_detected_item_can_be_sent_back_to_confirm(self):
        for name in ("hidden_injection.pdf", "pakistani_pii.pdf"):  # hidden_text and cnic items
            with self.subTest(pdf=name):
                body = self._preview(name).json()
                data = {"raw_text": body["raw_text"], "remove_pii": json.dumps(body["detected_pii"])}
                self.assertEqual(self.client.post("/api/preview/confirm", headers=self.h, data=data).status_code, 200)

    def test_batch_flow_with_cnic_and_hidden_text_items(self):
        files = [("file", (n, (FIXTURES / n).read_bytes())) for n in ("hidden_injection.pdf", "pakistani_pii.pdf")]
        reply = self.client.post("/api/preview/batch", headers=self.h, files=files)
        self.assertEqual(reply.status_code, 200, reply.text)
        seen = {}
        for review in reply.json()["reviews"]:
            types = {i["type"] for i in review["detected_pii"]}
            seen[review["filename"]] = types
            confirm = self.client.post(f"/api/reviews/{review['review_id']}/confirm-pii", headers=self.h,
                                       json={"remove_pii": review["detected_pii"]})
            self.assertEqual(confirm.status_code, 200, confirm.text)
            self.assertNotIn("SYSTEM:", confirm.json()["cleaned_text"])
        self.assertIn("hidden_text", seen["hidden_injection.pdf"])
        self.assertIn("cnic", seen["pakistani_pii.pdf"])
        self.assertNotIn("hidden_text", seen["pakistani_pii.pdf"])


if __name__ == "__main__":
    unittest.main()
