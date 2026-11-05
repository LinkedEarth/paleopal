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


NEW_NOTEBOOK = history("import pyleoclim as pyleo", "lr04 = pyleo.utils.load_dataset('LR04')")
# Most tests aren't about the intro cell, so PaleoPAL has already been here.
EARLIER_NOTE = [{"role": "assistant", "content": "An earlier note.", "agent_type": "paleopal_note"}]
LR04 = EARLIER_NOTE + NEW_NOTEBOOK


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
        hist = EARLIER_NOTE + history("import pyleoclim as pyleo", "a = pyleo.utils.load_dataset('LR04')",
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


class RequestReachesWriterTests(unittest.TestCase):
    def test_the_writer_sees_the_researchers_words(self):
        seen = []

        def call(system, user):
            if system.startswith("You read one request"):
                return json.dumps(SPECTRAL)
            seen.append(user)
            return model(SPECTRAL)(system, user)
        run(call, request="use lomb-scargle with n50=4")
        self.assertIn("use lomb-scargle with n50=4", seen[0])


def writing_chain(meaning):
    """A stand-in writer that follows the plan's chain from `start`, wherever that is."""
    def call(system, user):
        if system.startswith("You read one request"):
            return json.dumps(meaning)
        ids = [line.split("## Step: ")[1] for line in user.splitlines() if line.startswith("## Step: ")]
        current = system.split("Start from `")[1].split("`")[0]
        method = system.split("use method='")[1].split("'")[0]
        calls = {"slice": "slice([0, 500])", "detrend": "detrend(method='linear')", "regrid": "interp()",
                 "standardize": "standardize()", "spectral_estimate": f"spectral(method='{method}')",
                 "significance": "signif_test()", "beta_estimate": "beta_est()", "visualize": "plot()"}
        steps = []
        for number, step in enumerate(ids):
            name = f"v{number}"
            name = "fig, ax" if step == "visualize" else name  # a plot displays the result
            steps.append({"id": step, "explanation": "T.", "code": f"{name} = {current}.{calls[step]}"})
            current = name
        return json.dumps({"steps": steps})
    return call


class SliceTests(unittest.TestCase):
    """"Spectral analysis on part of the record" is a slice, then the workflow on that part."""

    def flow(self, notebook, meaning, answers=None):
        return asyncio.run(flow.run("a request", notebook, WORKFLOW, writing_chain(meaning),
                                    [no_search], answers=answers or {}))

    def test_slicing_comes_first_on_a_clean_notebook(self):
        result = self.flow(LR04, {**SPECTRAL, "steps": ["slice"], "whole_analysis": True})
        self.assertEqual(result["plan"]["steps"], ["slice", "detrend", "standardize",
                                                   "spectral_estimate", "visualize"])
        self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))
        self.assertIn("v0 = lr04.slice([0, 500])", result["generated_code"])
        self.assertIn("I read your range as 0 to 500 in the series' time units.", texts(result))
        self.assertIn("change the numbers given to `timespan`", texts(result))

    def test_a_recommended_step_says_how_to_skip_it(self):
        result = self.flow(LR04, {**SPECTRAL, "steps": ["slice"], "whole_analysis": True})
        detrend = next(c["text"] for c in result["cells"]
                       if c["kind"] == "markdown" and c["step"] == "detrend")
        self.assertIn("don't run this cell, and change `v1` to `v0` in the next cell.", detrend)
        others = [c["text"] for c in result["cells"] if c["step"] in ("slice", "standardize", "visualize")]
        self.assertFalse(any("rather skip" in t for t in others))

    def test_no_skip_line_when_the_next_cell_does_not_use_the_result(self):
        self.assertIsNone(_pkg.workflow_writer._skip_note("a = lr04.detrend()", "b = lr04.standardize()"))
        self.assertIsNone(_pkg.workflow_writer._skip_note("fig, ax = psd.plot()", "x = fig"))

    def test_the_range_note_uses_the_numbers_in_the_code(self):
        note = _pkg.workflow_writer._slice_note("part = lr04.slice(timespan=(10, 800))")
        self.assertIn("as 10 to 800", note)
        self.assertIsNone(_pkg.workflow_writer._slice_note("part = lr04.slice(bounds)"))

    def test_no_slicing_unless_asked(self):
        result = self.flow(LR04, {**SPECTRAL, "whole_analysis": True})
        self.assertNotIn("slice", result["plan"]["steps"])

    def test_slicing_after_detrending_starts_a_new_chain(self):
        result = self.flow(DETRENDED, {**SPECTRAL, "steps": ["slice"], "whole_analysis": True})
        self.assertEqual(result["plan"]["steps"], ["slice", "detrend", "standardize",
                                                   "spectral_estimate", "visualize"])
        self.assertEqual(result["checker_findings"], [])
        self.assertIn("started a new chain from `lr04`", texts(result))

    def test_a_slice_already_in_the_notebook_is_built_on(self):
        sliced = LR04 + history("part = lr04.slice([0, 500])")
        result = self.flow(sliced, {**SPECTRAL, "whole_analysis": True}, {"detrend": "No"})
        self.assertEqual(result["plan"]["steps"], ["standardize", "spectral_estimate", "visualize"])
        self.assertIn("v0 = part.standardize()", result["generated_code"])

    def test_the_checker_flags_slicing_after_detrending(self):
        cells = ["import pyleoclim as pyleo", "lr04 = pyleo.utils.load_dataset('LR04')"]
        findings = _pkg.verification.check_new_code(
            cells, "x = lr04.detrend().slice([0, 500]).standardize().spectral()", {"objective": "exploratory"})
        failed = {f.rule for f in findings if f.status == "violated"}
        self.assertIn("preprocessing_order", failed)


class UnnecessaryRegridTests(unittest.TestCase):
    """Asking to regrid before a method that doesn't need it is explained and waits for yes or no."""

    def flow(self, notebook, meaning, answers=None):
        return asyncio.run(flow.run("a request", notebook, WORKFLOW, writing_chain(meaning),
                                    [no_search], answers=answers or {}))

    REGRID_LS = {**SPECTRAL, "method": "lomb_scargle", "steps": ["regrid"], "whole_analysis": True}

    def test_it_asks_first_with_the_guides_reason(self):
        result = self.flow(LR04, self.REGRID_LS)
        question = result["clarification_questions"][0]
        self.assertEqual((question["id"], question["choices"]), ("regrid", ["Yes", "No"]))
        self.assertIn("`lomb_scargle` doesn't need regridding", question["question"])
        self.assertIn("Lomb-Scargle and WWZ do not require regridding", question["context"])
        self.assertEqual(result["generated_code"], "")

    def test_yes_regrids_and_records_the_choice(self):
        result = self.flow(LR04, self.REGRID_LS, {"regrid": "Yes"})
        self.assertIn("regrid", result["plan"]["steps"])
        self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))
        self.assertIn("I regridded because you confirmed it", texts(result))
        self.assertIn({"step": "regrid", "answer": "yes"},
                      [d for c in result["cells"] for d in c.get("decisions", [])])

    def test_no_skips_it_and_says_so_once(self):
        result = self.flow(LR04, self.REGRID_LS, {"regrid": "No"})
        self.assertNotIn("regrid", result["plan"]["steps"])
        self.assertIn("You chose not to regrid", texts(result))
        self.assertNotIn("tolerates uneven sampling", texts(result))

    def test_a_method_that_needs_it_is_not_asked_about(self):
        result = self.flow(LR04, {**self.REGRID_LS, "method": "mtm"}, {"detrend": "No"})
        self.assertIn("regrid", result["plan"]["steps"])
        self.assertNotIn("clarification_questions", result)

    REGRIDDED = LR04 + history("even = lr04.interp()")

    def test_already_regridded_with_no_method_uses_mtm_and_says_why(self):
        result = self.flow(self.REGRIDDED, {**SPECTRAL, "whole_analysis": True}, {"detrend": "No"})
        self.assertEqual(result["plan"]["method"], "mtm")
        self.assertIn("spectral(method='mtm')", result["generated_code"])
        self.assertIn("Since your data are already regridded, I used MTM.", texts(result))
        self.assertEqual(result["checker_findings"], [])

    def test_already_regridded_slope_uses_mtm_instead_of_wwz(self):
        result = self.flow(self.REGRIDDED, {**SLOPE, "whole_analysis": True}, {"detrend": "No"})
        self.assertEqual(result["plan"]["method"], "mtm")
        self.assertIn("My default method for estimating the slope is WWZ", texts(result))

    def test_already_regridded_with_lomb_scargle_named_keeps_it_quietly(self):
        result = self.flow(self.REGRIDDED, {**SPECTRAL, "method": "lomb_scargle", "whole_analysis": True},
                           {"detrend": "No"})
        self.assertEqual(result["plan"]["method"], "lomb_scargle")
        self.assertNotIn("already regridded", texts(result))
        self.assertEqual(result["checker_findings"], [])


class AskedForEarlierStepTests(unittest.TestCase):
    """Regression: "run spectral analysis with a linear detrend" after standardizing failed all repairs."""

    def flow(self, meaning, answers=None):
        return asyncio.run(flow.run("a request", STANDARDIZED, WORKFLOW, writing_chain(meaning),
                                    [no_search], answers=answers or {}))

    def test_analysis_with_a_detrend_starts_a_new_chain_with_the_spectrum(self):
        result = self.flow({**SPECTRAL, "steps": ["detrend"], "whole_analysis": True})
        self.assertEqual(result["plan"]["steps"], ["detrend", "standardize", "spectral_estimate", "visualize"])
        self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))
        self.assertIn("lr04.detrend(method='linear')", result["generated_code"])
        self.assertIn("started a new chain from `lr04`", texts(result))

    def test_only_the_step_stays_only_the_step(self):
        result = self.flow({**SPECTRAL, "steps": ["detrend"], "whole_analysis": False})
        self.assertEqual(result["plan"]["steps"], ["detrend"])
        self.assertEqual((result["repairs"], result["checker_findings"]), (0, []))
        self.assertIn("started a new chain", texts(result))

    def test_asked_for_regrid_with_mtm_starts_a_new_chain(self):
        meaning = {**SPECTRAL, "method": "mtm", "steps": ["regrid"], "whole_analysis": True}
        result = self.flow(meaning, {"detrend": "No"})
        self.assertEqual(result["plan"]["steps"], ["regrid", "standardize", "spectral_estimate", "visualize"])
        self.assertEqual(result["checker_findings"], [])

    def test_the_whole_analysis_partway_includes_the_plot(self):
        result = self.flow({**SPECTRAL, "whole_analysis": True}, {"detrend": "No"})
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate", "visualize"])

    def test_only_naming_an_estimator_stays_a_snippet(self):
        result = self.flow({**SPECTRAL, "method": "lomb_scargle"}, {"detrend": "No"})
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate"])

    def test_naming_an_estimator_asks_for_the_spectrum_too(self):
        meaning = {**SPECTRAL, "method": "lomb_scargle", "steps": ["detrend"], "whole_analysis": False}
        self.assertIn("spectral_estimate", self.flow(meaning)["plan"]["steps"])

    def test_a_step_without_a_spectrum_says_nothing_about_one(self):
        result = self.flow({**SPECTRAL, "steps": ["detrend"], "whole_analysis": False})
        self.assertNotIn("first look at the spectrum", texts(result))

    def test_mtm_without_asking_for_regrid_still_explains(self):
        result = self.flow({**SPECTRAL, "method": "mtm"})
        self.assertIn("needs evenly spaced data", texts(result))

    def test_a_later_step_does_not_start_a_new_chain(self):
        result = run(writing(SIGNIF), LR04_DONE, "add the significance test")
        self.assertNotIn("started a new chain", texts(result))


class NamedMethodTests(unittest.TestCase):
    def test_naming_an_estimator_stays_in_the_flow_even_if_the_analysis_is_missed(self):
        """Regression: "use lomb-scargle" sometimes fell through to the old pipeline."""
        meaning = {**SPECTRAL, "analysis": None, "method": "lomb_scargle"}
        result = asyncio.run(flow.run("use lomb-scargle", STANDARDIZED, WORKFLOW, writing_chain(meaning),
                                      [no_search], answers={"detrend": "No"}))
        self.assertEqual(result["plan"]["steps"], ["spectral_estimate"])


class NotCoveredTests(unittest.TestCase):
    """Part of a request the guide doesn't cover is named, never dropped silently."""

    def test_the_note_comes_first_and_lists_the_parts(self):
        result = run(writing_goal({**SPECTRAL, "not_covered": ["save the figure as a PDF"]}))
        first = result["cells"][0]["text"]
        self.assertTrue(first.startswith("I haven't done this part of your request, because my guide "
                                         "to spectral analysis doesn't cover it yet:"))
        self.assertIn("- save the figure as a PDF", first)
        self.assertIn("I'd rather tell you than guess. Everything below follows the guide.", first)
        self.assertNotIn("save the figure", result["generated_code"])

    def test_it_follows_the_intro(self):
        result = run(writing_goal({**SPECTRAL, "not_covered": ["save the figure as a PDF"]}), NEW_NOTEBOOK)
        self.assertTrue(result["cells"][0]["text"].startswith("**Working with PaleoPAL**"))
        self.assertTrue(result["cells"][1]["text"].startswith("I haven't done this part"))

    def test_the_interpreter_is_told_that_plots_can_be_saved(self):
        settings = flow.step_settings(WORKFLOW, _pkg.workflow_writer._parameter_reference())
        self.assertIn("savefig_settings", settings["visualize"])
        self.assertIn("timespan", settings["slice"])
        self.assertIn("method", settings["detrend"])

    def test_no_note_when_everything_is_covered(self):
        self.assertFalse(any("I haven't done" in c["text"] for c in run(writing_goal(SPECTRAL))["cells"]))

    def test_no_note_on_a_question(self):
        result = run(model({**SPECTRAL, "series": "sst", "not_covered": ["save it"]}))
        self.assertFalse(any("I haven't done" in c["text"] for c in result["cells"]))


class IntroTests(unittest.TestCase):
    def assert_intro(self, hist, expected):
        result = run(writing_goal(SPECTRAL), hist)
        self.assertEqual(result["cells"][0]["text"].startswith("**Working with PaleoPAL**"), expected)

    def test_a_notebook_with_no_paleopal_cells_gets_it_first(self):
        self.assert_intro(NEW_NOTEBOOK, True)

    def test_it_says_it_can_be_deleted(self):
        self.assertIn("You can delete this cell", run(writing_goal(SPECTRAL), NEW_NOTEBOOK)["cells"][0]["text"])

    def test_a_paleopal_note_means_no_intro(self):
        self.assert_intro(NEW_NOTEBOOK + EARLIER_NOTE, False)

    def test_a_paleopal_code_cell_means_no_intro(self):
        self.assert_intro(NEW_NOTEBOOK + history("# Written by PaleoPAL\nd = lr04.detrend()"), False)

    def test_the_researchers_markdown_does_not_count(self):
        self.assert_intro([{"role": "user", "content": "# My title"}, *NEW_NOTEBOOK], True)

    def test_a_question_in_a_cell_gets_it_too(self):
        result = run(model({**SPECTRAL, "series": "sst"}), NEW_NOTEBOOK)
        self.assertTrue(result["cells"][0]["text"].startswith("**Working with PaleoPAL**"))

    def test_a_panel_question_adds_no_cell(self):
        result = run(writing_goal(SPECTRAL), STANDARDIZED)
        self.assertNotIn("cells", result)

    def test_the_intro_is_not_code_and_not_a_step(self):
        cell = run(writing_goal(SPECTRAL), NEW_NOTEBOOK)["cells"][0]
        self.assertEqual((cell["kind"], cell["step"]), ("markdown", None))


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
