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
              "step_snippets", "workflow_writer", "chat_session"):
    _load(_name)
flow = _load("planning_flow")
_load("plot_flow")
GUIDES = _load("guide_router").load_guides()
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
        method = system.split("use method='")[1].split("'")[0] if "use method='" in system else None
        number = system.split("use number=")[1].split(" ")[0] if "use number=" in system else None
        calls = {"slice": "slice([0, 500])", "detrend": "detrend(method='linear')", "regrid": "interp()",
                 "standardize": "standardize()", "spectral_estimate": f"spectral(method='{method}')",
                 "significance": f"signif_test(number={number})" if number else "signif_test()",
                 "beta_estimate": "beta_est()", "visualize": "plot()"}
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

    KERNEL = {"pyleoclim_version": "1.3.1b0", "series": [
        {"name": "lr04", "type": "Series", "time_unit": "ky BP", "time_name": "Age", "n_points": 30,
         "time_min": 0.0, "time_max": 5320.0, "evenly_spaced": False,
         "time_values": [float(t) for t in range(0, 501, 20)] + [1000.0, 2000.0, 3000.0, 5320.0]}]}

    def test_the_kernel_gives_the_units_and_the_points_left(self):
        result = asyncio.run(flow.run("a request", LR04, WORKFLOW,
                                      writing_chain({**SPECTRAL, "steps": ["slice"], "whole_analysis": True}),
                                      [no_search], kernel=self.KERNEL))
        self.assertIn("I read your range as 0 to 500 ky BP, `lr04`'s time unit. That leaves 26 of the 30 "
                      "points in `lr04`.", texts(result))

    def test_too_few_points_stops_the_analysis_with_the_reason(self):
        short = {"series": [{**self.KERNEL["series"][0], "time_values": [0.0, 1.0, 2.0, 600.0, 5320.0]}]}
        result = asyncio.run(flow.run("a request", LR04, WORKFLOW,
                                      writing_chain({**SPECTRAL, "steps": ["slice"], "whole_analysis": True}),
                                      [no_search], kernel=short))
        self.assertEqual(result["generated_code"], "")
        self.assertTrue(result["needs_user_input"])
        self.assertIn("leaves only 3 of the 5 points in `lr04`. I need at least 20 points", texts(result))

    def test_the_time_axis_never_reaches_the_model(self):
        sent = []
        writer = writing_chain({**SPECTRAL, "steps": ["slice"], "whole_analysis": True})

        def call(system, user):
            sent.append(system + user)
            return writer(system, user)
        asyncio.run(flow.run("a request", LR04, WORKFLOW, call, [no_search], kernel=self.KERNEL))
        self.assertTrue(sent)
        self.assertFalse(any("5320" in m or "time_values" in m for m in sent))
        writing = [m for m in sent if "## Step: " in m]
        self.assertTrue(any("`lr04` has its time as Age, in ky BP" in m for m in writing))

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


class EvenSpacingTests(unittest.TestCase):
    """The kernel says a series is evenly spaced: MTM by default, no regrid, and comparisons asked."""

    HAD = {"name": "had", "type": "Series", "time_unit": "year C.E.", "time_name": "Time", "n_points": 173,
           "time_min": 1850.0, "time_max": 2022.0, "evenly_spaced": True,
           "time_values": [float(t) for t in range(1850, 2023)]}
    ONLY_HAD = EARLIER_NOTE + history("import pyleoclim as pyleo", "had = pyleo.utils.load_dataset('HadCRUT5')")
    BOTH = LR04 + history("had = pyleo.utils.load_dataset('HadCRUT5')",
                          "lr04_psd = lr04.standardize().spectral(method='lomb_scargle')")
    ASK = {**SPECTRAL, "series": "had", "whole_analysis": True}

    def flow(self, notebook, meaning, answers=None):
        return asyncio.run(flow.run("a request", notebook, WORKFLOW, writing_chain(meaning), [no_search],
                                    answers=answers or {}, kernel={"series": [self.HAD]}))

    def test_an_evenly_spaced_series_gets_mtm_and_the_reason(self):
        result = self.flow(self.ONLY_HAD, self.ASK)
        self.assertEqual(result["plan"]["method"], "mtm")
        self.assertNotIn("regrid", result["plan"]["steps"])
        self.assertIn("Your series is already evenly spaced, so I used MTM.", texts(result))
        self.assertEqual(result["checker_findings"], [])

    def test_mtm_named_on_evenly_spaced_data_needs_no_regrid(self):
        result = self.flow(self.ONLY_HAD, {**self.ASK, "method": "mtm"})
        self.assertNotIn("regrid", result["plan"]["steps"])
        self.assertIn("Your series is already evenly spaced, so I did not include a regridding step.",
                      texts(result))
        self.assertNotIn("I used MTM", texts(result))
        self.assertEqual(result["checker_findings"], [])

    def test_a_different_method_from_another_series_is_asked_about(self):
        result = self.flow(self.BOTH, self.ASK)
        question = result["clarification_questions"][0]
        self.assertEqual(question["id"], "comparison_method")
        self.assertEqual(question["question"], "Your spectrum of `lr04` uses Lomb-Scargle. You're about to "
                         "process `had`, which is evenly spaced. Would you still like to use Lomb-Scargle "
                         "for comparison?")
        self.assertEqual(question["context"], "If not, I'll use MTM for `had`.")

    def test_yes_keeps_the_earlier_method_and_records_it(self):
        result = self.flow(self.BOTH, self.ASK, {"comparison_method": "Yes"})
        self.assertEqual(result["plan"]["method"], "lomb_scargle")
        self.assertIn("I used Lomb-Scargle, as you chose, so `had` can be compared with `lr04`.", texts(result))
        self.assertNotIn("I used MTM", texts(result))
        self.assertIn({"step": "comparison_method", "answer": "yes"},
                      [d for c in result["cells"] for d in c.get("decisions", [])])

    def test_no_uses_mtm_and_records_it(self):
        result = self.flow(self.BOTH, self.ASK, {"comparison_method": "No"})
        self.assertEqual(result["plan"]["method"], "mtm")
        self.assertIn("You chose MTM rather than Lomb-Scargle, the method used for `lr04`.", texts(result))

    def test_a_named_method_is_never_questioned(self):
        result = self.flow(self.BOTH, {**self.ASK, "method": "lomb_scargle"})
        self.assertNotIn("clarification_questions", result)

    def test_without_the_kernel_nothing_changes(self):
        result = asyncio.run(flow.run("a request", self.ONLY_HAD, WORKFLOW, writing_chain(self.ASK), [no_search]))
        self.assertEqual(result["plan"]["method"], "lomb_scargle")


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


class SurrogateTests(unittest.TestCase):
    """1,000 surrogates when the goal is finding peaks, the default otherwise, and a note saying which."""

    USED = "I used 1,000 surrogate series"
    DEFAULT = "I used Pyleoclim's default of 200 surrogate series"

    def test_finding_peaks_uses_1000_and_says_why(self):
        result = asyncio.run(flow.run("find the periodicities in lr04", LR04, WORKFLOW,
                                      writing_chain({**PEAKS, "whole_analysis": True}), [no_search]))
        self.assertIn("signif_test(number=1000)", texts(result))
        self.assertIn(self.USED, texts(result))
        self.assertNotIn(self.DEFAULT, texts(result))

    def run_on_a_spectrum(self, meaning):
        hist = LR04 + history("lr04_psd = lr04.standardize().spectral(method='lomb_scargle')")
        return texts(asyncio.run(flow.run("a request", hist, WORKFLOW, writing_chain(meaning), [no_search])))

    def test_asking_for_the_test_means_finding_peaks_so_1000(self):
        text = self.run_on_a_spectrum({**SPECTRAL, "steps": ["significance"]})
        self.assertIn("signif_test(number=1000)", text)
        self.assertIn(self.USED, text)

    def test_a_preliminary_test_uses_the_default_and_says_1000_is_better(self):
        meaning = {**SPECTRAL, "steps": ["significance"], "objective": "exploratory"}
        hist = LR04 + history("lr04_psd = lr04.standardize().spectral(method='lomb_scargle')")
        result = asyncio.run(flow.run("a quick significance test", hist, WORKFLOW, writing_chain(meaning), [no_search]))
        self.assertEqual(result["checker_findings"], [])  # asked for, so not "unrequested"
        text = texts(result)
        self.assertIn("signif_test()", text)
        self.assertIn(self.DEFAULT, text)
        self.assertIn("you can set `number=1000`", text)


class StepOnlyTests(unittest.TestCase):
    """A request naming one of the guide's steps is the guide's, even when the analysis isn't named."""

    def test_a_step_without_the_analysis_named_is_still_covered(self):
        meaning = {"analysis": None, "series": "lr04", "steps": ["detrend"], "whole_analysis": False,
                   "method": None, "objective": None}
        result = asyncio.run(flow.run("detrend Lr04", LR04, WORKFLOW, writing_chain(meaning), [no_search]))
        self.assertIsNotNone(result)
        self.assertIn("detrend", result["plan"]["steps"])

    def test_a_step_on_a_notebook_with_only_data_gives_just_that_step(self):
        meaning = {"analysis": "spectral_analysis", "series": "lr04", "steps": ["detrend"],
                   "whole_analysis": False, "method": None, "objective": None}
        for notebook in (LR04, NEW_NOTEBOOK):
            result = asyncio.run(flow.run("detrend lr04", notebook, WORKFLOW, writing_chain(meaning), [no_search]))
            self.assertEqual(result["plan"]["steps"], ["detrend"])
            self.assertNotIn("significance test", texts(result))
            # Just the step: nothing asks it to show (plot) its result.
            self.assertEqual(result["checker_findings"], [])

    def test_the_whole_analysis_still_gets_the_whole_workflow(self):
        result = asyncio.run(flow.run("run spectral analysis on lr04", LR04, WORKFLOW,
                                      writing_chain({**SPECTRAL, "whole_analysis": True}), [no_search]))
        self.assertIn("spectral_estimate", result["plan"]["steps"])


class NoGuideTests(unittest.TestCase):
    """A request no guide covers gets the model's answer with the note, never the old pipeline."""

    def answer(self, *replies, hist=LR04):
        queue = [json.dumps(r) for r in replies]
        seen = []

        def call(system, user):
            seen.append(user)
            return queue.pop(0)
        result = asyncio.run(flow.answer_uncovered("plot the timeseries", hist, WORKFLOW,
                                                   _pkg.workflow_writer._parameter_reference(), call))
        return result, seen

    def test_explanation_note_then_code(self):
        result, seen = self.answer({"reply": "I plot the series with its own method.", "code": "fig, ax = lr04.plot()"})
        markdown, code = result["cells"]
        self.assertTrue(markdown["text"].startswith("I plot the series with its own method.\n\nNone of my guides"))
        self.assertIn(flow.NO_GUIDE_NOTE, markdown["text"])
        self.assertTrue(markdown["text"].endswith("*Written by PaleoPAL*, an AI assistant."))
        self.assertEqual(code["text"], "# Written by PaleoPAL\nfig, ax = lr04.plot()")
        self.assertTrue(result["model_only"])
        self.assertIn("This is a request written in a notebook cell", seen[0])

    def test_dismantling_is_repaired_before_it_is_shown(self):
        bad = {"reply": "x", "code": "import matplotlib.pyplot as plt\nplt.plot(lr04.time, lr04.value)"}
        result, _ = self.answer(bad, {"reply": "x", "code": "fig, ax = lr04.plot()"})
        self.assertEqual(result["generated_code"], "fig, ax = lr04.plot()")
        self.assertEqual(result["checker_findings"], [])

    def test_quoted_parameters_appear_as_sources(self):
        result, _ = self.answer({"reply": "x", "code": "fig, ax = lr04.plot(title='LR04')", "parameters": [
            {"method": "pyleoclim.core.series.Series.plot", "names": ["title"]}]})
        self.assertIn("parameter `title`", result["cells"][0]["text"])
        self.assertIn(flow.NO_GUIDE_NOTE, result["cells"][0]["text"])

    def test_a_new_notebook_gets_the_intro_first(self):
        result, _ = self.answer({"reply": "x", "code": ""}, hist=NEW_NOTEBOOK)
        self.assertTrue(result["cells"][0]["text"].startswith("**Working with PaleoPAL**"))
        self.assertEqual(len(result["cells"]), 2)  # no code means no code cell


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


class VersionNoteTests(unittest.TestCase):
    def test_the_version_note_is_found_only_in_paleopals_own_cells(self):
        note = f"Your session has Pyleoclim 1.2.1, {flow.workflow_writer.VERSION_NOTE}"
        self.assertTrue(flow._version_noted([{"agent_type": "paleopal_note", "content": note}]))
        self.assertFalse(flow._version_noted([{"role": "user", "content": note}]))
        self.assertFalse(flow._version_noted([]))


class NotRunTests(unittest.TestCase):
    """A variable the cells create but the kernel lacks stops the request, with the reason."""

    HAD = EvenSpacingTests.HAD
    ASK = EvenSpacingTests.ASK
    NOTEBOOK = EvenSpacingTests.ONLY_HAD

    def flow(self, notebook, kernel):
        return asyncio.run(flow.run("a request", notebook, WORKFLOW, writing_chain(self.ASK), [no_search],
                                    kernel=kernel))

    def test_a_series_whose_cell_was_not_run_stops_and_asks(self):
        result = self.flow(self.NOTEBOOK, {"series": [], "variables": {"pyleo": "module"}})
        self.assertTrue(result["needs_user_input"])
        self.assertIn("The cell that creates `had` hasn't been run, so I couldn't check its data. "
                      "Could you run it, then ask me again?", texts(result))
        self.assertNotIn("plan", result)

    def test_a_later_step_that_was_not_run_is_named(self):
        notebook = self.NOTEBOOK + history("had_detrended = had.detrend()")
        result = self.flow(notebook, {"series": [self.HAD], "variables": {"pyleo": "module", "had": "Series"}})
        self.assertIn("The cell that creates `had_detrended` hasn't been run", texts(result))

    def test_variables_that_ran_go_ahead(self):
        result = self.flow(self.NOTEBOOK, {"series": [self.HAD], "variables": {"pyleo": "module", "had": "Series"}})
        self.assertEqual(result["plan"]["method"], "mtm")

    def test_no_kernel_read_or_an_older_extension_goes_ahead(self):
        for kernel in (None, {"series": [self.HAD]}):
            self.assertIn("plan", self.flow(self.NOTEBOOK, kernel))


def both_guides(meaning, plot_choice):
    """The analysis stand-in, plus the plot interpreter's choice and a plot written from `start`."""
    chain = writing_chain(meaning)
    systems = []

    def call(system, user):
        systems.append(system)
        if system.startswith("You read one plotting request"):
            return json.dumps(plot_choice)
        if "## Step: plot_" in user:
            step = [l.split("## Step: ")[1] for l in user.splitlines() if l.startswith("## Step: ")][0]
            start = system.split("Start from `")[1].split("`")[0]
            return json.dumps({"steps": [{"id": step, "explanation": "P.", "code": f"fig2, ax2 = {start}.plot()"}]})
        return chain(system, user)
    call.systems = systems
    return call


class BothGuidesTests(unittest.TestCase):
    """Case 3: the analysis first, then the plot guide against the notebook plus the new cells."""

    def both(self, plot_choice, plot_first=False, notebook=None):
        call = both_guides({**SPECTRAL, "whole_analysis": True}, plot_choice)
        result = asyncio.run(flow.run_both("run spectral analysis on lr04 and plot the detrended series",
                                           notebook or LR04, GUIDES, plot_first, call, [no_search]))
        return result, call

    def test_the_plot_goes_right_after_the_new_cell_it_shows(self):
        result, _ = self.both({"object": "v0", "plot": None})
        code = [c["text"].split("\n", 1)[1] for c in result["cells"] if c["kind"] == "code"]
        self.assertEqual(code[0], "v0 = lr04.detrend(method='linear')")
        self.assertEqual(code[1], "fig2, ax2 = v0.plot()")
        self.assertEqual(code[2], "v1 = v0.standardize()")
        self.assertNotIn("place_after_cell", result)
        self.assertNotIn("I placed this plot", json.dumps(result))

    def test_one_intro_on_a_fresh_notebook(self):
        result, _ = self.both({"object": "v0", "plot": None}, notebook=NEW_NOTEBOOK)
        self.assertEqual(sum("Working with PaleoPAL" in c["text"] for c in result["cells"]), 1)

    def test_the_analysis_interpreter_is_told_plots_are_elsewhere(self):
        _, call = self.both({"object": "v0", "plot": None})
        reader = next(s for s in call.systems if s.startswith("You read one request"))
        self.assertIn("Another of PaleoPAL's guides handles every plot", reader)

    def test_the_analysis_writer_is_told_too(self):
        users = []
        inner = both_guides({**SPECTRAL, "whole_analysis": True}, {"object": "v0", "plot": None})

        def call(system, user):
            if system.startswith("You write the code"):
                users.append(user)
            return inner(system, user)
        asyncio.run(flow.run_both("x", LR04, GUIDES, False, call, [no_search]))
        self.assertIn("Another of PaleoPAL's guides handles every plot", users[0])
        self.assertNotIn("Another of PaleoPAL's guides", users[-1])  # the plot writer isn't told

    def test_an_existing_object_follows_the_request_order(self):
        first, _ = self.both({"object": "lr04", "plot": None}, plot_first=True)
        code = [c["text"] for c in first["cells"] if c["kind"] == "code"]
        self.assertIn("lr04.plot()", code[0])
        last, _ = self.both({"object": "lr04", "plot": None}, plot_first=False)
        code = [c["text"] for c in last["cells"] if c["kind"] == "code"]
        self.assertIn("lr04.plot()", code[-1])

    def test_new_objects_are_not_asked_about_as_not_run(self):
        call = both_guides({**SPECTRAL, "whole_analysis": True}, {"object": "v0", "plot": None})
        kernel = {"variables": {"pyleo": "module", "lr04": "Series"}}
        result = asyncio.run(flow.run_both("x", LR04, GUIDES, False, call, [no_search], kernel=kernel))
        self.assertFalse(result["needs_user_input"])
        self.assertTrue(any("v0.plot()" in c["text"] for c in result["cells"]))

    def test_a_plot_question_comes_under_the_analysis(self):
        result, _ = self.both({"object": "sst", "plot": None})
        self.assertFalse(result["needs_user_input"])
        self.assertIn("spectral_estimate", result["plan"]["steps"])
        self.assertIn("I couldn't find `sst`", result["cells"][-1]["text"])


if __name__ == "__main__":
    unittest.main()
