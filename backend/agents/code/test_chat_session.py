#!/usr/bin/env python3
"""Unit tests for chat_session.py, with a stand-in for the model.

Run from the backend directory:

  cd backend
  python agents/code/test_chat_session.py

Modules are loaded under a stand-in package so that importing them does not pull
in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest

_HERE = pathlib.Path(__file__).parent
_pkg = types.ModuleType("_chat_pkg")
_pkg.__path__ = [str(_HERE)]
sys.modules["_chat_pkg"] = _pkg


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_chat_pkg.{name}", _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    setattr(_pkg, name, module)
    spec.loader.exec_module(module)
    return module


for _name in ("api_validation", "verification", "workflow_detector", "workflow_writer"):
    _load(_name)
chat = _load("chat_session")
WORKFLOW = _pkg.workflow_detector.load_workflow()
REFERENCE = _pkg.workflow_writer._parameter_reference()

NOTEBOOK = [
    {"role": "assistant", "content": "", "agent_type": "code", "generated_content": "import pyleoclim as pyleo"},
    {"role": "assistant", "content": "", "agent_type": "code",
     "generated_content": "lr04 = pyleo.utils.load_dataset('LR04')"},
    {"role": "assistant", "content": "", "agent_type": "code",
     "generated_content": "# Written by PaleoPAL\npsd = lr04.standardize().spectral(method='lomb_scargle')"},
    {"role": "assistant", "content": "### Spectral estimate\n\nI estimated...", "agent_type": "paleopal_note"},
    {"role": "user", "content": "@agent chat what else can the plot do?"},
]
ASK = [{"role": "user", "content": "what else can the plot do?"}]


def answering(*replies):
    """A stand-in model giving these replies in turn."""
    queue = [r if isinstance(r, str) else json.dumps(r) for r in replies]
    seen = []

    def call(system, user):
        seen.append((system, user))
        return queue.pop(0)
    call.seen = seen
    return call


def ask(*replies, messages=ASK):
    return chat.reply(NOTEBOOK, messages, WORKFLOW, REFERENCE, answering(*replies))


class NotebookTests(unittest.TestCase):
    def test_every_cell_is_sent_with_its_author(self):
        text = chat.notebook_text(NOTEBOOK)
        self.assertIn("Cell 2: code, written by the researcher", text)
        self.assertIn("Cell 3: code, written by PaleoPAL", text)
        self.assertIn("Cell 4: markdown, written by PaleoPAL", text)
        self.assertIn("Cell 5: markdown, written by the researcher", text)

    def test_the_model_gets_the_guide_the_reference_and_the_conversation(self):
        model = answering({"reply": "Hi."})
        chat.reply(NOTEBOOK, ASK, WORKFLOW, REFERENCE, model)
        system, user = model.seen[0]
        self.assertIn("PaleoPAL's guide to spectral analysis", system)
        self.assertIn("pyleoclim.core.psds.PSD.plot", system)
        self.assertIn("savefig_settings", system)
        self.assertIn("**Researcher:** what else can the plot do?", user)
        self.assertIn("lr04 = pyleo.utils.load_dataset('LR04')", user)


class SourceTests(unittest.TestCase):
    def test_a_cited_parameter_is_quoted_from_the_reference_with_its_link(self):
        result = ask({"reply": "You can save it.", "parameters": [
            {"method": "pyleoclim.core.psds.PSD.plot", "names": ["savefig_settings"]}]})
        self.assertEqual(len(result.sources), 1)
        source = result.sources[0]
        self.assertIn("`PSD.plot`, parameter `savefig_settings`", source.title)
        self.assertIn('"path" must be specified', source.text)
        self.assertTrue(source.link.endswith("pyleoclim.core.psds.PSD.plot"))
        self.assertEqual(result.note, chat.PARTLY_MODEL_NOTE)  # unless the model says it stayed within

    def test_no_note_only_when_the_answer_stays_within_its_sources(self):
        cited = [{"method": "pyleoclim.core.psds.PSD.plot", "names": ["title"]}]
        self.assertIsNone(ask({"reply": "x", "parameters": cited, "beyond_sources": False}).note)
        self.assertEqual(ask({"reply": "x", "parameters": cited, "beyond_sources": True}).note,
                         chat.PARTLY_MODEL_NOTE)

    def test_the_series_plot_is_in_the_reference(self):
        result = ask({"reply": "x", "parameters": [
            {"method": "pyleoclim.core.series.Series.plot", "names": ["title", "savefig_settings"]}]})
        self.assertEqual(len(result.sources), 2)

    def test_a_cited_step_is_quoted_from_the_guide(self):
        result = ask({"reply": "Because...", "guide_steps": ["standardize"]})
        self.assertIn("on the standardize step", result.sources[0].title)
        self.assertIn("Required by all the underlying spectral methods", result.sources[0].text)

    def test_names_not_in_the_files_are_dropped(self):
        result = ask({"reply": "x", "guide_steps": ["make_it_pretty", 3],
                      "parameters": [{"method": "pyleoclim.core.psds.PSD.plot", "names": ["glitter"]},
                                     {"method": "matplotlib.pyplot.plot", "names": ["color"]}, "oops"]})
        self.assertEqual(result.sources, [])

    def test_nothing_cited_means_the_model_only_note(self):
        result = ask({"reply": "Use twinx."})
        self.assertEqual(result.note, chat.MODEL_ONLY_NOTE)

    def test_an_unreadable_reply_is_a_gentle_message_not_a_crash(self):
        self.assertIn("I'm still learning", ask("not json").reply)


class CodeTests(unittest.TestCase):
    def test_dismantling_is_repaired_quietly(self):
        bad = {"reply": "Here.", "code": "import matplotlib.pyplot as plt\nplt.plot(psd.frequency, psd.amplitude)"}
        good = {"reply": "Here.", "code": "fig, ax = psd.plot()"}
        result = ask(bad, good)
        self.assertEqual((result.code, result.problems), ("fig, ax = psd.plot()", []))

    def test_problems_left_after_the_repairs_are_reported(self):
        bad = {"reply": "Here.", "code": "import matplotlib.pyplot as plt\nplt.plot(psd.frequency, psd.amplitude)"}
        result = ask(bad, bad, bad)
        self.assertTrue(any("object_not_dismantled" in p for p in result.problems))

    def test_the_offer_to_summarize_is_passed_on(self):
        self.assertTrue(ask({"reply": "Agreed.", "offer_summary": True}).offer_summary)
        self.assertFalse(ask({"reply": "Hmm.", "offer_summary": "yes"}).offer_summary)


class SummaryTests(unittest.TestCase):
    MESSAGES = [{"role": "user", "content": "add a title"},
                {"role": "assistant", "content": "Use title=.", "sources": [], "note": None},
                {"role": "user", "content": "and a second axis?"},
                {"role": "assistant", "content": "Use twinx.", "sources": [], "note": chat.MODEL_ONLY_NOTE}]

    def summarize(self, reply):
        return chat.summarize(NOTEBOOK, self.MESSAGES, WORKFLOW, REFERENCE, answering(reply))

    def test_summary_cell_then_code_cell(self):
        result = self.summarize({"summary": "You asked for a title.", "code": "fig, ax = psd.plot(title='LR04')"})
        markdown, code = result["cells"]
        self.assertTrue(markdown["text"].startswith("### Summary of our discussion\n\nYou asked for a title."))
        self.assertEqual(code["text"], "# Written by PaleoPAL\nfig, ax = psd.plot(title='LR04')")

    def test_only_what_the_decision_rests_on_is_quoted_and_a_model_only_reply_is_remembered(self):
        text = self.summarize({"summary": "S.", "code": "", "beyond_sources": False, "parameters": [
            {"method": "pyleoclim.core.series.Series.plot", "names": ["title"]}]})["cells"][0]["text"]
        self.assertIn("Part of this discussion came from the underlying AI model only", text)
        self.assertIn("parameter `title`", text)
        self.assertNotIn("parameter `figsize`", text)
        self.assertTrue(text.endswith("*Written by PaleoPAL*, an AI assistant. Sources are quoted directly, "
                                      "not written by the AI."))

    def test_a_summary_within_its_sources_has_no_note(self):
        messages = [m for m in self.MESSAGES if not m.get("note")][:2]
        text = chat.summarize(NOTEBOOK, messages, WORKFLOW, REFERENCE, answering(
            {"summary": "S.", "code": "", "beyond_sources": False,
             "parameters": [{"method": "pyleoclim.core.series.Series.plot", "names": ["title"]}]}))["cells"][0]["text"]
        self.assertNotIn("underlying AI model only", text)

    def test_no_code_means_one_cell(self):
        self.assertEqual(len(self.summarize({"summary": "S.", "code": ""})["cells"]), 1)

    def test_bad_summary_code_carries_the_warning(self):
        result = self.summarize({"summary": "S.", "code": "lr04 = lr04.standardize()"})
        self.assertIn("I'm still learning", result["cells"][0]["text"])
        self.assertTrue(result["problems"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
