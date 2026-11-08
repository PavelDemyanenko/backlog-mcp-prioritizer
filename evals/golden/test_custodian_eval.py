"""Custodian eval tests (no LLM).  Run: python3 -I -m unittest discover -s evals/golden"""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_custodian_eval as ce  # noqa: E402

DATASET = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
# What the live run on 2026-11-08 reported (findings rows of its table).
GOOD = [{"task": "GOLD-23", "finding": "BROKEN_LINK", "adr": "0031", "quote": "adr_refs: 0031 missing"},
        {"task": "GOLD-8", "finding": "NEEDS_ADR", "adr": None, "quote": "no ADR covers the orchestrator"}]


def failed(findings, run_checks=None):
    return {c["check"] for c in ce.evaluate(findings, DATASET, run_checks)["checks"] if not c["ok"]}


class Expectations(unittest.TestCase):
    def test_derived_from_dataset(self):
        exp = ce.expectations(DATASET)
        self.assertEqual(exp["required"], {("GOLD-23", "BROKEN_LINK"), ("GOLD-8", "NEEDS_ADR")})
        self.assertEqual(exp["clean"], {"GOLD-7"})


class Gates(unittest.TestCase):
    def test_correct_report_passes_and_extra_needs_adr_is_only_reported(self):
        r = ce.evaluate(GOOD + [{"task": "GOLD-22", "finding": "NEEDS_ADR", "adr": None, "quote": "x"}], DATASET)
        self.assertTrue(r["passed"])
        self.assertEqual(r["extra_needs_adr"], ["GOLD-22"])

    def test_violations(self):
        self.assertIn("required findings reported (BROKEN_LINK, NEEDS_ADR)", failed(GOOD[:1]))
        self.assertIn("tasks backed by an accepted ADR have no findings",
                      failed(GOOD + [{"task": "GOLD-7", "finding": "NOT_ACCEPTED", "adr": "0015"}]))
        self.assertIn("no false CONFLICT (dataset has none)",
                      failed(GOOD + [{"task": "GOLD-2", "finding": "CONFLICT", "adr": "0015", "quote": "q"}]))
        self.assertIn("every CONFLICT quotes its ADR",
                      failed(GOOD + [{"task": "GOLD-2", "finding": "CONFLICT", "adr": "0015", "quote": ""}]))
        self.assertIn("findings file is a list of known finding types", failed([{"task": "GOLD-8", "finding": "MAYBE"}]))
        self.assertIn("findings file is a list of known finding types", failed({"not": "a list"}))

    def test_live_run_checks_are_gates(self):
        bad = [{"check": "read-only: no ADR file written", "ok": False, "detail": "new: ['0002-x.md']"}]
        self.assertIn("read-only: no ADR file written", failed(GOOD, bad))


class Cli(unittest.TestCase):
    def run_cli(self, findings):
        tmp = pathlib.Path(tempfile.mkdtemp())
        src = tmp / "f.json"
        src.write_text(json.dumps(findings), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return ce.main(["x", "--agent", f"replay:{src}", "--out", str(tmp / "runs")])

    def test_replay_exit_codes(self):
        self.assertEqual(self.run_cli(GOOD), 0)
        self.assertEqual(self.run_cli([]), 1)

    def test_prompt_asks_for_machine_readable_findings_and_forbids_drafts(self):
        p = ce.build_prompt(DATASET)
        self.assertIn("adr-findings.json", p)
        self.assertIn("do not draft or write any ADR", p)
