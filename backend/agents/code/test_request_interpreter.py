#!/usr/bin/env python3
"""Unit tests for request_interpreter.py, with a stand-in for the model.

These check the Python around the model, not the model itself, and cost nothing.
Run from the backend directory:

  cd backend
  python agents/code/test_request_interpreter.py

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


r = _load("request_interpreter")
WORKFLOW = _load("workflow_detector").load_workflow()


def interpret(reply, series=("lr04",)):
    text = reply if isinstance(reply, str) else json.dumps(reply)
    return r.interpret_request("a request", WORKFLOW, list(series), lambda system, user: text)


class ValidReplyTests(unittest.TestCase):
    def test_all_values_on_the_lists_are_kept(self):
        result = interpret({"analysis": "spectral_analysis", "series": "lr04",
                            "objective": "peak_detection", "method": "mtm"})
        self.assertEqual((result.analysis, result.series, result.objective, result.method),
                         ("spectral_analysis", "lr04", "peak_detection", "mtm"))
        self.assertEqual(result.problems, [])

    def test_unstated_values_stay_none_without_a_problem(self):
        result = interpret({"analysis": "spectral_analysis", "series": "lr04",
                            "objective": None, "method": None})
        self.assertIsNone(result.objective)
        self.assertIsNone(result.method)
        self.assertEqual(result.problems, [])

    def test_requested_steps_are_kept(self):
        self.assertEqual(interpret({"steps": ["significance"]}).steps, ["significance"])

    def test_whole_analysis_is_read_and_defaults_to_false(self):
        self.assertTrue(interpret({"whole_analysis": True}).whole_analysis)
        self.assertFalse(interpret({}).whole_analysis)
        self.assertFalse(interpret({"whole_analysis": "yes"}).whole_analysis)

    def test_uncovered_parts_are_kept_as_written_and_never_cause_a_problem(self):
        result = interpret({"not_covered": ["save the figure  as a PDF", 3, "", None]})
        self.assertEqual(result.not_covered, ["save the figure as a PDF"])
        self.assertEqual(result.problems, [])
        self.assertEqual(interpret({"not_covered": "oops"}).not_covered, [])
        self.assertEqual(interpret({}).not_covered, [])

    def test_the_prompt_lists_each_steps_settings_when_given(self):
        prompt = r.build_system_prompt(WORKFLOW, ["lr04"], {"visualize": ["savefig_settings", "title"]})
        self.assertIn("- visualize (settings: savefig_settings, title)", prompt)
        self.assertIn("- detrend\n", prompt)
        self.assertIn("detrend, ", r.build_system_prompt(WORKFLOW, ["lr04"]))

    def test_an_invented_step_is_dropped(self):
        result = interpret({"steps": ["make_it_pretty"]})
        self.assertEqual(result.steps, [])
        self.assertEqual(len(result.problems), 1)

    def test_json_inside_a_code_fence_is_read(self):
        result = interpret('```json\n{"analysis": "spectral_analysis", "series": "lr04"}\n```')
        self.assertEqual(result.series, "lr04")


class RejectedReplyTests(unittest.TestCase):
    def test_series_not_in_the_notebook_is_dropped(self):
        result = interpret({"analysis": "spectral_analysis", "series": "sst"})
        self.assertIsNone(result.series)
        self.assertEqual(len(result.problems), 1)
        self.assertIn("sst", result.problems[0])

    def test_invented_objective_and_method_are_dropped(self):
        result = interpret({"objective": "find_cycles", "method": "fourier"})
        self.assertIsNone(result.objective)
        self.assertIsNone(result.method)
        self.assertEqual(len(result.problems), 2)

    def test_non_text_value_is_dropped(self):
        result = interpret({"series": ["lr04"]})
        self.assertIsNone(result.series)
        self.assertEqual(len(result.problems), 1)

    def test_prose_reply_is_a_problem_not_a_crash(self):
        result = interpret("I think this is spectral analysis.")
        self.assertIsNone(result.analysis)
        self.assertEqual(len(result.problems), 1)

    def test_broken_json_is_a_problem_not_a_crash(self):
        result = interpret('{"analysis": ')
        self.assertEqual(len(result.problems), 1)


class PromptTests(unittest.TestCase):
    def test_prompt_comes_from_the_workflow_file(self):
        prompt = r.build_system_prompt(WORKFLOW, ["lr04"])
        for expected in ("spectral_analysis", "peak_detection", "lomb_scargle", "periodogram", "lr04",
                         "periodicities, cycles, peaks"):
            self.assertIn(expected, prompt)


if __name__ == "__main__":
    unittest.main()
