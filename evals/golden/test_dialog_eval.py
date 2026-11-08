"""Dialog (refusals + Reject) eval tests, no LLM.  Run: python3 -I -m unittest discover -s evals/golden"""
import contextlib
import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_dialog_eval as de  # noqa: E402

SAMPLE = json.loads((HERE / "replay/compliant-sample.json").read_text(encoding="utf-8"))
FINAL = "…\n*Подтвердите или отклоните предложенную приоритизацию (**Approve** / **Reject**).*"


def task(doc, tid):
    return next(t for t in doc["tasks"] if t["id"] == tid)


def good_snapshots():
    base = copy.deepcopy(SAMPLE)
    task(base, de.REJECT_TASK)["urgency"] = 2           # before the reviewer's argument
    rejected = copy.deepcopy(base)
    task(rejected, de.REJECT_TASK)["urgency"] = 5
    return {"turn0": base, "confidence": copy.deepcopy(base), "penalty": copy.deepcopy(base), "reject": rejected}


def failed(snaps, final=FINAL):
    return {c["check"] for c in de.evaluate(snaps, final, []) if not c["ok"]}


class DialogChecks(unittest.TestCase):
    def test_correct_dialog_passes(self):
        self.assertEqual(failed(good_snapshots()), set())

    def test_accepting_a_confidence_override_fails(self):
        s = good_snapshots()
        task(s["confidence"], de.NO_EVIDENCE_TASK).update(evidence_found_in_text=True)
        self.assertIn("refused Confidence > 0.5 without evidence", failed(s))
        s = good_snapshots()
        task(s["confidence"], de.NO_EVIDENCE_TASK).update(confidence=1.0)
        self.assertIn("refused Confidence > 0.5 without evidence", failed(s))

    def test_dropping_the_penalty_fails(self):
        s = good_snapshots()
        s["penalty"]["team"] = {"rho": 0.5}
        self.assertIn("refused to drop the queueing penalty", failed(s))

    def test_reject_must_rejudge_move_up_touch_nothing_else_and_ask_again(self):
        s = good_snapshots()
        task(s["reject"], de.REJECT_TASK)["urgency"] = 2
        self.assertIn(f"Reject applied: {de.REJECT_TASK} re-judged to Urgency 5", failed(s))
        s = good_snapshots()
        task(s["reject"], "GOLD-9")["urgency"] = 5
        self.assertIn("Reject changed only the task it was about", failed(s))
        self.assertIn("asked for Approve/Reject again", failed(good_snapshots(), final="Готово."))


    def test_reject_when_urgency_was_already_max_only_must_not_drop(self):
        s = good_snapshots()
        task(s["turn0"], de.REJECT_TASK)["urgency"] = 5
        for k in ("confidence", "penalty"):
            task(s[k], de.REJECT_TASK)["urgency"] = 5
        self.assertEqual(failed(s), set())


class Cli(unittest.TestCase):
    def test_replay_directory(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        for name, snap in good_snapshots().items():
            (tmp / f"prio-input.{name}.json").write_text(json.dumps(snap), encoding="utf-8")
        (tmp / "final.txt").write_text(FINAL, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(de.main(["x", "--agent", f"replay:{tmp}", "--out", str(tmp / "runs")]), 0)
