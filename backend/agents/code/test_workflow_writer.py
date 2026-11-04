#!/usr/bin/env python3
"""Unit tests for workflow_writer.py, with a stand-in for the model.

Run from the backend directory:

  cd backend
  python agents/code/test_workflow_writer.py

Modules are loaded straight from their files so that importing them does not
pull in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


d = _load("workflow_detector")
w = _load("workflow_writer")
WORKFLOW = d.load_workflow()
CELLS = ["import pyleoclim as pyleo", "lr04 = pyleo.utils.load_dataset('LR04')"]
STEPS = ["detrend", "standardize", "spectral_estimate", "visualize"]


def lr04_plan(objective=None, method=None):
    state = d.detect(CELLS, WORKFLOW, objective=objective or "exploratory")
    return w.build_plan(state, WORKFLOW, objective, method)


def reply(ids=STEPS, code="x = lr04.standardize()"):
    return json.dumps({"steps": [{"id": i, "explanation": "Model text.", "code": code} for i in ids]})


def write(text, plan=None, snippets=None):
    return w.write_workflow(plan or lr04_plan(), WORKFLOW, snippets or {}, lambda system, user: text)


class PlanTests(unittest.TestCase):
    def test_lr04_steps_come_from_the_workflow_file(self):
        self.assertEqual([s["id"] for s in lr04_plan().steps], STEPS)

    def test_unstated_method_uses_the_workflow_default(self):
        self.assertEqual(lr04_plan().method, "lomb_scargle")

    def test_tolerant_method_skips_regrid_and_says_so(self):
        plan = lr04_plan()
        self.assertNotIn("regrid", [s["id"] for s in plan.steps])
        self.assertIn("did not include a regridding step", plan.notes["spectral_estimate"][0])

    def test_even_spacing_method_includes_regrid_before_standardize(self):
        ids = [s["id"] for s in lr04_plan(method="mtm").steps]
        self.assertLess(ids.index("regrid"), ids.index("standardize"))

    def test_exploratory_adds_the_approved_statement(self):
        self.assertIn("Would you like me to add a significance test?", lr04_plan().notes[""][0])

    def test_peak_detection_writes_the_test_without_proposing_it(self):
        plan = lr04_plan(objective="peak_detection")
        self.assertIn("significance", [s["id"] for s in plan.steps])
        self.assertNotIn("", plan.notes)


class CellTests(unittest.TestCase):
    def setUp(self):
        self.result = write(reply())
        self.steps = {c.step: c for c in self.result.cells if c.kind == "markdown" and c.step}

    def test_each_step_is_a_markdown_then_code_pair(self):
        self.assertEqual(self.result.problems, [])
        kinds = [c.kind for c in self.result.cells if c.step]
        self.assertEqual(kinds, ["markdown", "code"] * len(STEPS))

    def test_authorship_is_visible_in_every_cell(self):
        for cell in self.result.cells:
            marker = w.AUTHORSHIP_CODE if cell.kind == "code" else w.AUTHORSHIP_MARKDOWN
            self.assertIn(marker, cell.text)

    def test_explanations_are_the_models_words(self):
        for step in STEPS:
            self.assertIn("Model text.", self.steps[step].text)

    def test_python_adds_the_exact_source_in_a_collapsed_section(self):
        text = self.steps["standardize"].text
        self.assertIn("<details><summary>Sources</summary>", text)
        self.assertIn("> Required by all the underlying spectral methods", text)
        self.assertLess(text.index("Model text."), text.index("<details>"))

    def test_authorship_stays_outside_the_collapsed_section(self):
        for step in STEPS:
            text = self.steps[step].text
            self.assertGreater(text.index(w.AUTHORSHIP_MARKDOWN), text.index("</details>"))

    def test_spectral_source_comes_from_the_chosen_method(self):
        self.assertIn("using Lomb-Scargle", self.steps["spectral_estimate"].text)

    def test_every_lr04_step_has_source_text(self):
        for step in lr04_plan().steps:
            self.assertIsNotNone(w.source_text(step, lr04_plan(), WORKFLOW), step["id"])

    def test_recommended_steps_are_labelled(self):
        self.assertIn("(recommended)", self.steps["detrend"].text)
        self.assertNotIn("(recommended)", self.steps["standardize"].text)

    def test_python_adds_the_required_statements(self):
        self.assertIn("did not include a regridding step", self.steps["spectral_estimate"].text)
        self.assertIn("Would you like me to add a significance test?", self.result.cells[-1].text)


class SourceTests(unittest.TestCase):
    def test_method_without_source_text_says_so(self):
        plan = lr04_plan(method="wwz")
        result = write(reply(), plan)
        spectral = next(c for c in result.cells if c.step == "spectral_estimate")
        self.assertIn("has no source text for this step yet", spectral.text)

    def test_only_examples_sent_to_the_model_are_named(self):
        examples = [{"notebook": f"lib/nb{i}.ipynb", "code": "lr04.detrend()"} for i in range(3)]
        result = write(reply(), snippets={"detrend": examples})
        detrend = next(c for c in result.cells if c.step == "detrend")
        self.assertIn("`nb0.ipynb`, `nb1.ipynb`", detrend.text)
        self.assertNotIn("nb2.ipynb", detrend.text)

    def test_a_missing_explanation_is_flagged(self):
        text = json.dumps({"steps": [{"id": i, "code": "x = 1"} for i in STEPS]})
        self.assertEqual(len(write(text).problems), len(STEPS))

    def test_prompt_gives_the_source_but_not_a_duplicate_rationale(self):
        message = w.build_user_message(lr04_plan(), WORKFLOW, {})
        self.assertIn("Source text: I removed the long-term trend", message)
        self.assertNotIn("rationale:", message)


class RejectionTests(unittest.TestCase):
    def assert_rejected(self, ids):
        result = write(reply(ids))
        self.assertEqual(result.cells, [])
        self.assertEqual(len(result.problems), 1)

    def test_an_added_step_is_rejected(self):
        self.assert_rejected(STEPS + ["significance"])

    def test_a_dropped_step_is_rejected(self):
        self.assert_rejected(STEPS[:-1])

    def test_reordered_steps_are_rejected(self):
        self.assert_rejected(list(reversed(STEPS)))

    def test_a_repeated_import_is_flagged(self):
        result = write(reply(code="import pyleoclim as pyleo"))
        self.assertTrue(all("repeats an import" in p for p in result.problems))
        self.assertEqual(len(result.problems), len(STEPS))

    def test_code_that_does_not_parse_is_flagged(self):
        self.assertIn("doesn't parse", write(reply(code="x = (")).problems[0])

    def test_prose_reply_is_a_problem_not_a_crash(self):
        result = write("Here is your workflow.")
        self.assertEqual(result.cells, [])
        self.assertEqual(len(result.problems), 1)


if __name__ == "__main__":
    unittest.main()
