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


def reply(ids=STEPS, code="x = 1"):
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
        self.assertIn("No source text provided.", spectral.text)

    def test_only_examples_sent_to_the_model_are_named(self):
        examples = [{"notebook": f"lib/nb{i}.ipynb", "code": "lr04.detrend()"} for i in range(3)]
        result = write(reply(), snippets={"detrend": examples})
        detrend = next(c for c in result.cells if c.step == "detrend")
        self.assertIn("`nb0.ipynb`, `nb1.ipynb`", detrend.text)
        self.assertNotIn("nb2.ipynb", detrend.text)

    def test_a_missing_explanation_is_flagged(self):
        text = json.dumps({"steps": [{"id": i, "code": "x = 1"} for i in STEPS]})
        self.assertEqual(len(write(text).problems), len(STEPS))

    def test_examples_carry_their_notebook_text(self):
        examples = [{"markdown_context": "We keep the mean so the axis stays in permil.",
                     "code": "lr04.detrend(preserve_mean=True)"}]
        message = w.build_user_message(lr04_plan(), WORKFLOW, {"detrend": examples})
        self.assertIn("Its notebook's text: We keep the mean", message)

    def test_the_indexer_placeholder_is_not_sent_as_text(self):
        examples = [{"markdown_context": "Notebook start", "code": "lr04.detrend()"}]
        message = w.build_user_message(lr04_plan(), WORKFLOW, {"detrend": examples})
        self.assertNotIn("Notebook start", message)

    def test_the_request_reaches_the_writer_before_the_steps(self):
        plan = lr04_plan()
        plan.request = "use lomb-scargle with n50=4"
        message = w.build_user_message(plan, WORKFLOW, {})
        self.assertIn("## The researcher's request\nuse lomb-scargle with n50=4", message)
        self.assertLess(message.index("n50=4"), message.index("## Step: detrend"))

    def test_a_request_asking_for_an_extra_step_is_still_rejected(self):
        plan = lr04_plan()
        plan.request = "and also run a significance test"
        self.assertEqual(write(reply(STEPS + ["significance"]), plan).cells, [])

    def test_prompt_gives_the_source_but_not_a_duplicate_rationale(self):
        message = w.build_user_message(lr04_plan(), WORKFLOW, {})
        self.assertIn("Source text: I removed the long-term trend", message)
        self.assertNotIn("rationale:", message)


REFERENCE = {"pyleoclim_version": "9.9",
             "links": {"Series.detrend": "http://docs/detrend", "tsutils.detrend": "http://docs/ts",
                       "Series.spectral": "http://docs/spectral", "spectral.mtm": "http://docs/mtm"},
             "methods": {
    "pyleoclim.core.series.Series.spectral": {
        "parameters": [{"name": "method", "type": None, "definition": "The estimator.", "default": "'lomb_scargle'"},
                       {"name": "settings", "type": "dict", "definition": "Method arguments.", "default": "None"}],
        "settings_by_method": {
            "mtm": [{"name": "NW", "type": "float", "definition": "Time-bandwidth.", "default": "None",
                     "source": "spectral.mtm"}],
            "lomb_scargle": [{"name": "n50", "type": "int", "definition": "Segments.", "default": "3",
                              "source": "spectral.lomb_scargle"}]}},
    "pyleoclim.core.series.Series.detrend": {
     "passes_to": [{"name": "n", "type": "int", "definition": "Modes to remove.", "default": "1",
                    "source": "tsutils.detrend"}],
     "parameters": [
        {"name": "method", "type": "str, optional", "definition": "The method for detrending.", "default": "'emd'"},
        {"name": "preserve_mean", "type": "boolean", "definition": "Keeps the mean.", "default": "False"},
        {"name": "keep_log", "type": None, "definition": None, "default": "False"}]}}}
DETREND = next(s for s in WORKFLOW["steps"] if s["id"] == "detrend")
SPECTRAL_STEP = next(s for s in WORKFLOW["steps"] if s["id"] == "spectral_estimate")


class ParameterTests(unittest.TestCase):
    def block(self, code):
        return w._parameters_block(DETREND, code, REFERENCE)

    def test_only_arguments_the_code_sets_are_defined(self):
        block = self.block("a = lr04.detrend(preserve_mean=True)")
        self.assertIn("`preserve_mean=True`: (boolean) Keeps the mean. *(default: False)*", block)
        self.assertNotIn("`method", block)

    def test_a_positional_argument_is_matched_to_its_parameter(self):
        self.assertIn("`method='emd'`", self.block("a = lr04.detrend('emd')"))

    def test_no_arguments_means_no_section(self):
        self.assertIsNone(self.block("a = lr04.detrend()"))

    def test_a_release_names_its_version(self):
        self.assertIn("Quoted from the Pyleoclim 9.9 documentation.", self.block("a = lr04.detrend('emd')"))

    def test_a_beta_says_latest_like_its_links(self):
        block = w._parameters_block(DETREND, "a = lr04.detrend('emd')", {**REFERENCE, "pyleoclim_version": "1.3.2b0"})
        self.assertIn("Quoted from the latest Pyleoclim documentation.", block)

    def test_the_closing_line_says_what_is_quoted(self):
        def closing(code):
            cell = next(c for c in write(reply(code=code)).cells if c.step == "detrend")
            return cell.text.splitlines()[-1]
        self.assertIn("*Written by PaleoPAL*", closing("a = lr04.detrend(preserve_mean=True)"))
        self.assertIn("Sources and Parameters are quoted directly", closing("a = lr04.detrend(preserve_mean=True)"))
        self.assertIn("Sources are quoted directly", closing("x = 1"))

    def test_sources_name_the_guide_not_the_file(self):
        cell = next(c for c in write(reply()).cells if c.step == "detrend")
        self.assertIn("PaleoPAL's guide to spectral analysis, on the detrend step:", cell.text)
        self.assertNotIn("workflow file", cell.text)

    def test_another_objects_arguments_are_not_defined_here(self):
        self.assertIsNone(self.block("a = lr04.slice(start=1)"))

    def test_an_undocumented_argument_says_so(self):
        for code in ("a = lr04.detrend(keep_log=True)", "a = lr04.detrend(unknown=1)"):
            self.assertIn("I couldn't find a definition", self.block(code))

    def test_a_missing_reference_file_means_no_section(self):
        self.assertIsNone(w._parameters_block(DETREND, "a = lr04.detrend('emd')", {}))

    def test_the_real_file_covers_every_workflow_method_and_appears_in_the_cell(self):
        for step in WORKFLOW["steps"]:
            apis = step.get("core_api") or []
            for api in apis if isinstance(apis, list) else [apis]:
                self.assertIn(api, w._parameter_reference()["methods"])
        result = write(reply(code="a = lr04.detrend(preserve_mean=True)"))
        text = next(c.text for c in result.cells if c.step == "detrend")
        self.assertIn("<details><summary>Parameters</summary>", text)
        self.assertLess(text.index("Parameters"), text.index("Sources"))

    def test_an_argument_passed_along_is_defined_and_its_function_linked(self):
        block = self.block("a = lr04.detrend(n=2)")
        self.assertIn("`n=2`: (int) Modes to remove. *(default: 1)*", block)
        self.assertIn("[`Series.detrend`](http://docs/detrend), [`tsutils.detrend`](http://docs/ts)", block)

    def test_the_method_is_linked_without_a_function_it_did_not_use(self):
        block = self.block("a = lr04.detrend(preserve_mean=True)")
        self.assertIn("[`Series.detrend`](http://docs/detrend)", block)
        self.assertNotIn("tsutils", block)

    def test_settings_keys_use_the_chosen_method(self):
        code = "p = s.spectral(method='mtm', settings={'NW': 4})"
        block = w._parameters_block(SPECTRAL_STEP, code, REFERENCE)
        self.assertIn("`settings={'NW': 4}`", block)
        self.assertIn("  - `NW=4`: (float) Time-bandwidth.", block)
        self.assertIn("[`spectral.mtm`](http://docs/mtm)", block)

    def test_settings_keys_use_the_default_method_when_none_is_named(self):
        block = w._parameters_block(SPECTRAL_STEP, "p = s.spectral(settings={'n50': 5})", REFERENCE)
        self.assertIn("`n50=5`: (int) Segments.", block)

    def test_a_setting_of_another_method_says_it_has_no_definition(self):
        code = "p = s.spectral(method='mtm', settings={'n50': 5})"
        self.assertIn("`n50=5`: I couldn't find", w._parameters_block(SPECTRAL_STEP, code, REFERENCE))

    def test_settings_held_in_a_variable_still_defines_settings(self):
        block = w._parameters_block(SPECTRAL_STEP, "p = s.spectral(settings=mine)", REFERENCE)
        self.assertIn("`settings=mine`: (dict) Method arguments.", block)

    def test_a_missing_link_is_left_out(self):
        reference = {**REFERENCE, "links": {}}
        self.assertNotIn("Full documentation", w._parameters_block(DETREND, "a = lr04.detrend(n=2)", reference))

    def _build(self):
        spec = importlib.util.spec_from_file_location(
            "build_parameters", _HERE.parents[1] / "scripts" / "build_pyleoclim_parameters.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        return build

    def test_a_beta_links_to_latest_and_a_release_to_its_own_pages(self):
        build = self._build()
        self.assertEqual(build.docs_version("1.3.1b0"), "latest")
        self.assertEqual(build.docs_version("1.3.2b"), "latest")
        self.assertEqual(build.docs_version("1.3.1"), "v1.3.1")

    def test_only_links_with_a_real_target_are_kept(self):
        page = '<dt id="pyleoclim.core.series.Series.bin">'
        links = self._build().build_links(
            ["pyleoclim.core.series.Series.bin", "pyleoclim.core.series.Series.interp"], "1.3.1", lambda url: page)
        self.assertEqual(list(links), ["Series.bin"])
        self.assertIn("/v1.3.1/core/api.html#pyleoclim.core.series.Series.bin", links["Series.bin"])

    def test_an_unreachable_page_means_no_links_not_a_crash(self):
        def down(url):
            raise OSError("no network")
        self.assertEqual(self._build().build_links(["pyleoclim.core.series.Series.bin"], "1.3.1", down), {})

    def test_unevenly_indented_parameters_are_separate_entries(self):
        parsed = self._build().parse_parameters("""Title

        Parameters
        ----------
        detrend : str
              Which detrending.
          sg_kwargs : dict
              The filter parameters.
              note : not a parameter, just text.
        """, {"detrend", "sg_kwargs"})
        self.assertEqual(parsed["detrend"]["definition"], "Which detrending.")
        self.assertEqual(parsed["sg_kwargs"]["definition"],
                         "The filter parameters. note : not a parameter, just text.")

    def test_docstring_parsing(self):
        parsed = self._build().parse_parameters("""Title

        Parameters
        ----------
        method : str; {'a','b'}

            First line
            second line.

        x, y : float
            Both.
        bare
            No type.

        Returns
        -------
        z : int
            Not a parameter.
        """)
        self.assertEqual(parsed["method"], {"type": "str; {'a','b'}", "definition": "First line second line."})
        self.assertEqual(parsed["y"]["definition"], "Both.")
        self.assertEqual(parsed["bare"], {"type": None, "definition": "No type."})
        self.assertNotIn("z", parsed)


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

    def test_chaining_another_steps_method_is_flagged(self):
        codes = dict.fromkeys(STEPS, "x = 1")
        codes["spectral_estimate"] = "x = lr04.spectral(method='lomb_scargle').signif_test()"
        text = json.dumps({"steps": [{"id": i, "explanation": "T.", "code": codes[i]} for i in STEPS]})
        problems = write(text).problems
        self.assertEqual(len(problems), 1)
        self.assertIn("also calls `signif_test`", problems[0])

    def test_a_step_may_call_its_own_methods(self):
        codes = dict.fromkeys(STEPS, "x = 1")
        codes["spectral_estimate"] = "x = lr04.spectral(method='lomb_scargle')"
        text = json.dumps({"steps": [{"id": i, "explanation": "T.", "code": codes[i]} for i in STEPS]})
        self.assertEqual(write(text).problems, [])

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
