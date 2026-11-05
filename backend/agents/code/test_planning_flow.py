#!/usr/bin/env python3
"""Unit tests for planning_flow.py, with stand-ins for the model and the search.

Run from the backend directory:

  cd backend
  python agents/code/test_planning_flow.py

Modules are loaded under a stand-in package so that importing them does not pull
in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys
import types
import unittest

_HERE = pathlib.Path(__file__).parent
_pkg = types.ModuleType("_flow_pkg")
_pkg.__path__ = [str(_HERE)]
sys.modules["_flow_pkg"] = _pkg


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_flow_pkg.{name}", _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    setattr(_pkg, name, module)
    spec.loader.exec_module(module)
    return module


for _name in ("api_validation", "verification", "workflow_detector", "request_interpreter",
              "step_snippets", "workflow_writer"):
    _load(_name)
flow = _load("planning_flow")
WORKFLOW = _pkg.workflow_detector.load_workflow()
STEPS = ["detrend", "standardize", "spectral_estimate", "visualize"]
GOOD_CODE = {
    "detrend": "a = lr04.detrend(method='emd')",
    "standardize": "b = a.standardize()",
    "spectral_estimate": "psd = b.spectral(method='lomb_scargle')",
    "visualize": "fig, ax = psd.plot()",
}


def history(*code):
    return [{"role": "assistant", "content": "", "generated_content": c} for c in code]


LR04 = history("import pyleoclim as pyleo", "lr04 = pyleo.utils.load_dataset('LR04')")


def model(meaning, steps=STEPS):
    """A stand-in that answers the interpreter and the writer differently."""
    def call(system, user):
        if system.startswith("You read one request"):
            return json.dumps(meaning)
        return json.dumps({"steps": [{"id": s, "explanation": "Text.", "code": GOOD_CODE[s]}
                                     for s in steps]})
    return call


async def no_search(query, top_k):
    return []


def run(call, hist=LR04, request="run spectral analysis on lr04"):
    return asyncio.run(flow.run(request, hist, WORKFLOW, call, [no_search]))


SPECTRAL = {"analysis": "spectral_analysis", "series": "lr04", "objective": None, "method": None}


class SwitchTests(unittest.TestCase):
    def test_off_unless_enabled(self):
        self.assertFalse(flow.is_enabled())


class HistoryTests(unittest.TestCase):
    def test_only_code_cells_are_read(self):
        messages = [{"role": "user", "content": "# My title"}, *history("x = 1"),
                    {"role": "assistant", "content": "", "generated_content": ""}]
        self.assertEqual(flow.code_cells_from_history(messages), ["x = 1"])


class Lr04Tests(unittest.TestCase):
    def setUp(self):
        self.result = run(model(SPECTRAL))

    def test_builds_the_steps_from_the_workflow_file(self):
        self.assertEqual(self.result["plan"]["steps"], STEPS)
        self.assertEqual(self.result["plan"]["method"], "lomb_scargle")

    def test_returns_paired_cells_and_the_proposal(self):
        kinds = [c["kind"] for c in self.result["cells"] if c["step"]]
        self.assertEqual(kinds, ["markdown", "code"] * len(STEPS))
        self.assertIn("add a significance test?", self.result["cells"][-1]["text"])

    def test_good_code_has_no_checker_findings(self):
        self.assertEqual(self.result["checker_findings"], [])

    def test_also_returns_one_code_string_for_the_current_extension(self):
        self.assertIn("psd.plot()", self.result["generated_code"])


class AsksInsteadOfGuessingTests(unittest.TestCase):
    def assert_asks(self, result, text):
        self.assertTrue(result["needs_user_input"])
        self.assertEqual(result["generated_code"], "")
        self.assertIn(text, result["cells"][0]["text"])

    def test_missing_series_asks_rather_than_using_the_only_one(self):
        result = run(model({**SPECTRAL, "series": "sst"}))
        self.assert_asks(result, "couldn't find that series")
        self.assertIn("`lr04`", result["cells"][0]["text"])

    def test_several_series_and_none_named_asks(self):
        hist = history("import pyleoclim as pyleo", "a = pyleo.utils.load_dataset('LR04')",
                       "b = pyleo.utils.load_dataset('SOI')")
        self.assert_asks(run(model({**SPECTRAL, "series": None}), hist), "several series")

    def test_unfamiliar_helper_asks(self):
        hist = LR04 + history("clean = my_helper(lr04)")
        self.assert_asks(run(model(SPECTRAL), hist), "my_helper")

    def test_a_reply_that_changes_the_steps_gets_the_still_learning_message(self):
        self.assert_asks(run(model(SPECTRAL, steps=STEPS[:2])), "still learning")


BAD_PLOT = dict(GOOD_CODE, visualize="plt.loglog(psd.frequency, psd.amplitude)")


def scripted(*writes):
    """A stand-in whose writer replies follow a script, repeating the last one."""
    calls = []

    def call(system, user):
        if system.startswith("You read one request"):
            return json.dumps(SPECTRAL)
        calls.append(user)
        code = writes[min(len(calls) - 1, len(writes) - 1)]
        return json.dumps({"steps": [{"id": s, "explanation": "Text.", "code": code[s]} for s in STEPS]})
    call.calls = calls
    return call


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.history = []

    def run_flow(self, call, hist=LR04):
        return asyncio.run(flow.run("run spectral analysis on lr04", hist, WORKFLOW, call,
                                    [no_search], on_repair=self.history.append))

    def test_a_mistake_is_fixed_quietly(self):
        result = self.run_flow(scripted(BAD_PLOT, GOOD_CODE))
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["checker_findings"], [])
        self.assertIn("psd.plot()", result["generated_code"])
        self.assertNotIn("plt.loglog", result["generated_code"])
        self.assertFalse(any("still learning" in c["text"] for c in result["cells"]))

    def test_the_model_is_told_what_to_fix(self):
        call = scripted(BAD_PLOT, GOOD_CODE)
        self.run_flow(call)
        self.assertNotIn("Problems to fix", call.calls[0])
        self.assertIn("Problems to fix", call.calls[1])
        self.assertIn("object_not_dismantled", call.calls[1])
        self.assertIn("plt.loglog", call.calls[1])

    def test_each_repair_is_recorded(self):
        self.run_flow(scripted(BAD_PLOT, GOOD_CODE))
        self.assertEqual(self.history[0]["attempt"], 1)
        self.assertEqual(self.history[-1]["outcome"], "repaired")

    def test_clean_code_makes_no_repair(self):
        call = scripted(GOOD_CODE)
        self.assertEqual(self.run_flow(call)["repairs"], 0)
        self.assertEqual(len(call.calls), 1)
        self.assertEqual(self.history, [])

    def test_after_three_repairs_the_code_is_shown_with_a_warning(self):
        call = scripted(BAD_PLOT)
        result = self.run_flow(call)
        self.assertEqual(len(call.calls), 4)
        self.assertIn("still learning", result["cells"][0]["text"])
        self.assertIn("object_not_dismantled", result["cells"][0]["text"])
        self.assertIn("plt.loglog", result["generated_code"])
        self.assertEqual(self.history[-1]["outcome"], "failed")

    def test_the_users_own_plot_is_not_blamed_on_paleopal(self):
        hist = LR04 + history("import matplotlib.pyplot as plt", "plt.plot(lr04.time, lr04.value)")
        call = scripted(GOOD_CODE)
        result = self.run_flow(call, hist)
        self.assertEqual(result["repairs"], 0)
        self.assertEqual(len(call.calls), 1)

    def test_a_test_hidden_inside_another_step_is_split_out(self):
        chained = dict(GOOD_CODE, spectral_estimate="psd = b.spectral(method='lomb_scargle').signif_test()")
        result = self.run_flow(scripted(chained, GOOD_CODE))
        self.assertEqual(result["repairs"], 1)
        self.assertIn("also calls `signif_test`", self.history[0]["problems"][0])
        self.assertNotIn("signif_test", result["generated_code"])

    def test_a_repeated_import_is_repaired(self):
        bad = dict(GOOD_CODE, detrend="import pyleoclim as pyleo\na = lr04.detrend(method='emd')")
        result = self.run_flow(scripted(bad, GOOD_CODE))
        self.assertEqual(result["repairs"], 1)
        self.assertNotIn("import", result["generated_code"])

    def test_an_unusable_repair_keeps_the_earlier_code(self):
        replies = iter([json.dumps(SPECTRAL),
                        json.dumps({"steps": [{"id": s, "explanation": "T.", "code": BAD_PLOT[s]} for s in STEPS]})])

        def call(system, user):
            return next(replies, "not json")
        result = self.run_flow(call)
        self.assertIn("plt.loglog", result["generated_code"])
        self.assertIn("still learning", result["cells"][0]["text"])

    def test_history_problems_never_reach_the_user(self):
        flow.record_repair({"x": 1}, path="/nonexistent-dir/history.jsonl")


class OldPipelineTests(unittest.TestCase):
    def test_no_loaded_series(self):
        self.assertIsNone(run(model(SPECTRAL), history("import pyleoclim as pyleo")))

    def test_request_is_not_spectral(self):
        self.assertIsNone(run(model({**SPECTRAL, "analysis": None}), request="plot lr04"))

    def test_no_series_for_a_later_step(self):
        self.assertIsNone(run(model(SPECTRAL), history("x = 1")))


SIGNIF = {**SPECTRAL, "steps": ["significance"]}
LR04_DONE = LR04 + history("a = lr04.detrend(method='emd')", "b = a.standardize()",
                           "psd = b.spectral(method='lomb_scargle')", "fig, ax = psd.plot()")
STANDARDIZED = LR04 + history("s = lr04.standardize()")
DETRENDED = LR04 + history("d = lr04.detrend(method='emd')")


def writing(steps):
    """A stand-in writer with plausible code for whichever steps it's asked for."""
    code = {"detrend": "x1 = lr04.detrend(method='emd')", "standardize": "x2 = x1.standardize()",
            "spectral_estimate": "x3 = x2.spectral(method='lomb_scargle')",
            "significance": "tested = psd.signif_test()", "visualize": "f, g = tested.plot()"}

    def call(system, user):
        if system.startswith("You read one request"):
            return json.dumps(steps)
        ids = [line.split("## Step: ")[1] for line in user.splitlines() if line.startswith("## Step: ")]
        code2 = dict(code)
        if "detrend" not in ids and "standardize" in ids:
            code2["standardize"] = "x2 = d.standardize()"
        if "standardize" not in ids and "spectral_estimate" in ids:
            code2["spectral_estimate"] = "x3 = s.spectral(method='lomb_scargle')"
        return json.dumps({"steps": [{"id": i, "explanation": "T.", "code": code2[i]} for i in ids]})
    return call


def texts(result):
    return "\n".join(c["text"] for c in result["cells"])


PEAKS = {**SPECTRAL, "objective": "peak_detection"}
SLOPE = {**SPECTRAL, "objective": "scaling_exponent"}


def writing_goal(meaning):
    """A stand-in writer whose steps follow from one another, so only the plan is tested."""
    code = {"detrend": "x1 = lr04.detrend(method='emd')", "standardize": "x2 = x1.standardize()",
            "spectral_estimate": "x3 = s.spectral(method='lomb_scargle')",
            "significance": "x4 = x3.signif_test()", "beta_estimate": "x4 = x3.beta_est()",
            "visualize": "f, g = x4.plot()"}

    def call(system, user):
        if system.startswith("You read one request"):
            return json.dumps(meaning)
        ids = [line.split("## Step: ")[1] for line in user.splitlines() if line.startswith("## Step: ")]
        steps = dict(code)
        method = "wwz" if meaning["objective"] == "scaling_exponent" else "lomb_scargle"
        source = "x2" if "standardize" in ids else "s"
        steps["spectral_estimate"] = f"x3 = {source}.spectral(method='{method}')"
        if "detrend" not in ids:
            steps["standardize"] = "x2 = d.standardize()"
        if "spectral_estimate" not in ids:
            steps["significance"] = "x4 = p.signif_test()"
        return json.dumps({"steps": [{"id": i, "explanation": "T.", "code": steps[i]} for i in ids]})
    return call


def run_with(meaning, hist, answers):
    return asyncio.run(flow.run("a request", hist, WORKFLOW, writing_goal(meaning), [no_search],
                                answers=answers))


class StatedGoalTests(unittest.TestCase):
    """Regression: the plan left out the test, so repairs swung between two checks and failed."""

    def test_periodicities_partway_add_the_test_without_repairs(self):
        result = run_with(PEAKS, STANDARDIZED, {"detrend": "Yes"})
        self.assertEqual(result["plan"]["steps"],
                         ["detrend", "standardize", "spectral_estimate", "significance", "visualize"])
        self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))

    def test_slope_partway_adds_the_estimate(self):
        result = run_with(SLOPE, STANDARDIZED, {"detrend": "No"})
        self.assertIn("beta_estimate", result["plan"]["steps"])
        self.assertEqual(result["checker_findings"], [])

    def test_unstated_goal_still_stops_at_the_spectrum(self):
        result = run_with(SPECTRAL, STANDARDIZED, {"detrend": "No"})
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate"])

    def test_spectrum_already_there_gets_just_the_test(self):
        hist = STANDARDIZED + history("p = s.spectral(method='lomb_scargle')")
        result = run_with(PEAKS, hist, {})
        self.assertEqual(result["plan"]["steps"], ["significance", "visualize"])
        self.assertEqual(result["checker_findings"], [])

    def test_test_already_there_changes_nothing(self):
        hist = STANDARDIZED + history("p = s.spectral(method='lomb_scargle')", "q = p.signif_test()")
        result = run_with(PEAKS, hist, {})
        self.assertIn("already has", texts(result))
        self.assertEqual(result["generated_code"], "")

    def test_a_single_earlier_step_is_not_held_to_the_rest_of_the_workflow(self):
        for meaning in (PEAKS, SPECTRAL):
            result = run_with({**meaning, "steps": ["standardize"]}, DETRENDED, {})
            self.assertEqual(result["plan"]["steps"], ["standardize"])
            self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))


class NextStepTests(unittest.TestCase):
    def test_nothing_missing_gives_just_the_step_and_its_plot(self):
        result = run(writing(SIGNIF), LR04_DONE, "add the significance test")
        self.assertEqual(result["plan"]["steps"], ["significance", "visualize"])
        self.assertEqual(result["plan"]["objective"], "peak_detection")
        self.assertNotIn("add a significance test?", texts(result))

    def test_a_missing_required_step_is_added_with_the_reason(self):
        result = run(writing({**SPECTRAL, "method": "lomb_scargle"}), DETRENDED, "use lomb-scargle")
        self.assertEqual(result["plan"]["steps"], ["standardize", "spectral_estimate"])
        self.assertIn("because the workflow requires it", texts(result))

    def test_continuing_from_earlier_work_is_not_repaired_away(self):
        """Regression: the checker once forced code back onto the raw series."""
        result = run(writing({**SPECTRAL, "method": "lomb_scargle"}), DETRENDED, "use lomb-scargle")
        self.assertEqual(result["repairs"], 0)
        self.assertIn("d.standardize()", result["generated_code"])

    def test_code_that_ignores_earlier_work_is_repaired(self):
        spectral = {**SPECTRAL, "method": "lomb_scargle"}
        replies = iter(["x2 = lr04.standardize()", "x2 = d.standardize()"])

        def call(system, user):
            if system.startswith("You read one request"):
                return json.dumps(spectral)
            code = next(replies)
            return json.dumps({"steps": [
                {"id": "standardize", "explanation": "T.", "code": code},
                {"id": "spectral_estimate", "explanation": "T.", "code": "x3 = x2.spectral(method='lomb_scargle')"}]})
        result = run(call, DETRENDED, "use lomb-scargle")
        self.assertEqual(result["repairs"], 1)
        self.assertIn("d.standardize()", result["generated_code"])

    def test_a_missing_recommended_step_asks_first(self):
        result = run(writing({**SPECTRAL, "method": "lomb_scargle"}), STANDARDIZED, "use lomb-scargle")
        question = result["clarification_questions"][0]
        self.assertEqual(question["id"], "detrend")
        self.assertEqual(question["choices"], ["Yes", "No"])
        self.assertIn("slow background changes", question["context"])
        self.assertEqual(result["generated_code"], "")

    def answer(self, answer):
        return asyncio.run(flow.run("use lomb-scargle", STANDARDIZED, WORKFLOW,
                                    writing({**SPECTRAL, "method": "lomb_scargle"}), [no_search],
                                    answers={"detrend": answer}))

    def test_no_continues_and_records_the_choice(self):
        result = self.answer("No")
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate"])
        self.assertIn("You chose not to add the detrend step", texts(result))
        self.assertEqual(result["cells"][0]["decisions"], [{"step": "detrend", "answer": "no"}])

    def test_yes_starts_a_new_chain_and_says_so(self):
        result = self.answer("Yes")
        self.assertEqual(result["plan"]["steps"], ["detrend", "standardize", "spectral_estimate"])
        self.assertIn("because you confirmed it", texts(result))
        self.assertIn("Your earlier cells are unchanged", texts(result))
        self.assertEqual(result["checker_findings"], [])

    def test_an_earlier_answer_is_not_asked_again(self):
        hist = STANDARDIZED + [{"role": "assistant", "content": "note", "agent_type": "paleopal_note",
                                "decisions": [{"step": "detrend", "answer": "no"}]}]
        result = run(writing({**SPECTRAL, "method": "lomb_scargle"}), hist, "use lomb-scargle")
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate"])

    def test_regrid_after_standardize_is_explained_not_attempted(self):
        result = run(writing({**SPECTRAL, "method": "mtm"}), STANDARDIZED, "use mtm")
        self.assertIn("regridding has to come before", result["cells"][0]["text"])
        self.assertEqual(result["generated_code"], "")

    def test_an_existing_step_is_left_alone(self):
        result = run(writing({**SPECTRAL, "steps": ["standardize"]}), STANDARDIZED, "standardize it")
        self.assertIn("already has the standardize step", result["cells"][0]["text"])

    def test_continues_from_the_newest_variable(self):
        prompts = []
        inner = writing(SIGNIF)

        def call(system, user):
            prompts.append(system)
            return inner(system, user)
        run(call, LR04_DONE, "add the significance test")
        self.assertIn("Start from `psd`", prompts[-1])


if __name__ == "__main__":
    unittest.main()
