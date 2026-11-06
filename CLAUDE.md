# PaleoPAL — Project Context

RAG-based agentic AI assistant for paleoclimate scientists, built on Pyleoclim
and the LinkedEarth ecosystem (LiPDGraph, PyLiPD, PyleoTUPS). FastAPI +
LangGraph backend, React frontend, VS Code extension as primary UI.

Deborah Khider (USC ISI) — project owner. Owns all decisions, scientific
and architectural. Varun Ratnakar (USC ISI) — built PaleoPAL, so he's the
best source of context on how the existing backend and VS Code extension
work; consult him for that knowledge, but decisions don't wait on him.

## The redesign — why this exists

PaleoPAL wasn't specialized enough: generated code destroyed Pyleoclim
`Series` objects and dropped to raw matplotlib instead of `Series.plot()`.

Root cause, after auditing the repo: the architecture was a generic RAG
pipeline with paleoclimate content poured in. **Relevance and authority are
orthogonal** — "unevenly spaced series must be regridded before spectral
analysis" is a *rule*; "here is how one notebook made a map" is an
*instance*. Both are topically relevant; cosine similarity ranks the
instance above the rule. A single vector space can't separate them.

Corpus was also independently broken: ~44% duplicate notebooks, more
matplotlib cells than Pyleoclim cells indexed, parent/child retrieval
silently disabled. Fixing this is Phase 1 Item 4, separate from the
schema work below.

## Deadline

Deborah has an accepted conference abstract for **December 2026**; goal:
most of what's needed for T1 working by then.

**How to treat it (Deborah, 2026-10-01): the demo is a motivator, not an
absolute goal.** The real priority is **getting PaleoPAL up and running
sooner rather than later**, demo or not; the demo gets built around
whatever works. Claude's job is to say plainly when something should wait
because something else needs to be tested first — not to cut corners to
hit December. Working pace: 1–2 days a
week. Rough estimate (2026-10-01): ~14–23 working days of T1 work vs
~10–20 available — tight; only works with a fixed scope.

**December scope (Deborah, 2026-10-01): a live demo in a notebook** —
- *Must have:* spectral and wavelet analysis, with the data loading
  attached (data phase → analysis phase).
- *Nice to have:* synthesis (comparing methods).
- *Coherence:* stretch — "see how well we are doing".
- *Format:* a **poster** — Deborah demos, and visitors also **play with it
  themselves**, understood as a prototype. So unscripted requests will
  happen: graceful failure (the "still learning" message, the LLM-only
  note) matters as much as the demo path.
- **Demo mode needed:** PaleoPAL must not remember preferences set during
  the demo (each visitor starts fresh; nothing persists).
A live demo rewards reliability over breadth: a known demo path that
works every time matters more than covering every case.
**Focus for AGU (Deborah, 2026-11-05):** after a meeting with Julien, who was
impressed by how the new design works with a scientist, put as much as
possible into the human interaction. The chatbot would be valuable even if it
only covers the spectral workflow.

## Reminders for the user docs / tutorials

Remind Deborah of these when we get to writing PaleoPAL's docs:
- The "LLM-only" vs "LinkedEarth-covered" terminology, and the two labels
  every request gets (how it's asked; its coverage).
- What kernel access is for and why PaleoPAL asks for it (read-only
  inspection checks only).

## Objectives we design against (from the NSF proposal; agreed 2026-10-01)

Source: Deborah's NSF CAIG proposal (kept outside the repo; ask her for
it). Paraphrased — PaleoPAL performs five tasks, alone or combined:
1. **Data search** — find datasets (e.g. by region, time, archive) via the
   graph (SPARQL) or vector search.
2. **Paleoclimate method search** — recommend suitable methods, from a
   method catalog.
3. **Standard method search** — everyday non-paleo tasks (e.g. reading a
   CSV with pandas), answered from the LLM's own knowledge. This is the
   LLM-only fallback.
4. **Workflow creation** — build notebook workflows, adapt as the
   researcher explores, and track variable names and object types.
5. **Explanation** — explain methods and why a step or method was chosen.
It recognises the task type, uses all available context, and asks for
clarification until it reaches consensus with the researcher.
**Success criterion:** not producing the "best" workflow, but working
with a researcher the way another researcher would — including
disagreements, compromises and a rationale for choices.

**Caveats vs the proposal:**
1. *Interface:* the proposal promised a JupyterLab extension with cell
   magics. **Decided (Deborah, 2026-10-01): VS Code is the interface going
   forward; JupyterLab is dropped.** **Architecture rule (agreed
   2026-10-01): all reasoning lives in the backend** (plan step, checker,
   workflow files, gap rules, demo mode); **the extension is thin** — it
   shows what the backend sends, collects the user's answers, and
   reads/writes the notebook (cells, kernel variables, input history) on
   request. Cost: the extension must send enough notebook context each
   time.
   **What the VS Code extension does today** (read 2026-10-01, ~620 lines
   in `vscode-extension/src/`):
   - *Routing is manual:* a quick-pick (Code / SPARQL / Workflow / Chat),
     or a markdown cell starting `@agent code|sparql|workflow …`; the
     result is inserted below that cell.
   - *Context sent:* only cell **text**. Markdown cells become "user"
     messages, code cells become "assistant" code. `notebook_context` is
     sent **empty** — no kernel variables, no outputs, no input history.
     The backend's variable context (`_create_comprehensive_variable_context`)
     comes from its *own* execution service (the web flow), and execution
     is off by default in the extension — so **in VS Code the backend
     can't see the user's kernel at all today.**
   - **Feasibility checked 2026-10-01 — it can be done.** The Jupyter
     extension (`ms-toolsai.jupyter`, npm types `@vscode/jupyter-extension`)
     exposes `kernels.getKernel(notebookUri)` → `Kernel.executeCode(code,
     token)`, which "executes code in the kernel without affecting the
     execution count & execution history" and streams back outputs (MIME
     items, so JSON works). Limits: only kernels the user has already
     started, for open notebooks. The user is prompted once to grant the
     extension kernel access (revocable via "Jupyter: Manage Access To
     Jupyter Kernels"); granting it lets the extension run *any* code in
     the kernel. Input history is reachable the same way (IPython `_ih`).
     Pre-grant access on the poster demo machine.
   - **Firm rule (agreed 2026-10-01): code run silently in the user's
     kernel is limited to a small, fixed set of hand-written, reviewed,
     read-only inspection snippets** (e.g. is this series evenly spaced,
     what columns does this DataFrame have, input history). Never
     LLM-generated code. Snippets must leave no trace in the user's
     namespace. Everything the LLM writes goes into a visible cell.
   - **Tell the user** what kernel access is for when they're first
     prompted. The prompt itself belongs to the Jupyter extension and its
     wording can't be changed, so PaleoPAL shows its own short explanation
     just before triggering it (only read-only checks; never runs code
     without showing it). **Reminder for Deborah:** put this in the user
     docs too.
   - *Markdown as "user" messages* mixes a preamble with conversation
     turns — conflicts with the locked decision to keep notebook markdown
     separate from session history.
   - Each request is stateless (new conversation id every time).
   - Can insert, delete and **replace** cells; has a webview panel for
     clarification questions.
2. *Science themes (Deborah, 2026-10-01).* **Now: complete the first
   redesign for T1.** T1 priority = **spectral, wavelet and coherence**
   (most of Pyleoclim); more Pyleoclim later. T1 also has a **synthesis
   step**: run several spectral methods and present conflicting results —
   requested by the user or suggested by PaleoPAL. T2 (tipping points) and
   T3 (BayGMST) come later, likely January 2027. T2 will use Ammonyte
   (being redesigned now) and should be close to the T1 design. T3 is
   mostly model *configuration* (inputs, priors, noise, scenarios), not
   ordered steps — needs its own design later.
3. *Data sources (agreed 2026-10-01).* The first redesign's data phase
   (and `data_loading.yml`) covers: **the LiPDGraph (SPARQL), LiPD files
   (PyLiPD), NOAA and PANGAEA (via PyleoTUPS), and the user's own files.**
   PaleoJump, emission scenarios and model output (CMIP6-PMIP4) stay in
   the LLM-only fallback until T2/T3.
4. *Literature and interpretation (Deborah, 2026-10-01).*
   - The literature library caused many problems; **the workflow YAML
     files are what replace it.** Not part of the redesign.
   - **Interpretation knowledge** (GitHub issue #1) is needed for T1 and
     belongs in this redesign — the explanation objective and the
     synthesis step depend on it — **but only after some of the pipeline
     is wired and shown to work.** It isn't in current PaleoPAL. Candidate
     home: an `interpretation` section per workflow file, keyed by
     objective. One thing at a time.
5. *Learning from the scientist across sessions (Deborah, 2026-10-01).*
   Partly built but not plugged in: the idea was a vector database of
   each user's preferences (e.g. prefers binning; always compares
   Lomb-Scargle with WWZ). It lives in the Docker container, so data stays
   local. **Not in the first redesign, but a close second step.** Note
   for then: preferences are user-specific *rules*; retrieving them by
   similarity alone risks the same relevance-vs-authority problem the
   redesign exists to fix.

## Agents and their scope (Deborah, 2026-10-01)

PaleoPAL has several distinct problems; earlier redesign work mixed them
together. Keep them separate. Today there are three agents:

1. **SPARQL** — queries the knowledge graph. Do not try to improve it now;
   first see whether changes help the other agents. Update (Deborah,
   2026-11-04): a smoke-test query (marine/ocean datasets with temperature
   variables) wouldn't work as written, so SPARQL generation does need work
   in the redesign, possibly after December. The problem is vocabulary: the
   LinkedEarth Ontology has separate modules, and `archiveType` is a
   **controlled vocabulary**, so user terms must be matched to it (marine /
   ocean → `MarineSediment`), not searched as text. Synonyms already exist
   in the PyLiPD codebase and PaleoPAL would need to read them.
2. **Code** — returns a *snippet* for a single request, not a multi-step
   process. "Use Lomb-Scargle" should yield essentially
   `spectral(method='lomb_scargle')`. It assumes preprocessing (e.g.
   regridding) has already been done correctly. Its known problem:
   using matplotlib for plots where Pyleoclim's own `.plot()` belongs.
3. **Workflow** — links SPARQL and code into a multi-step analysis. This is
   where PaleoPAL is expected to reason about whether regridding etc. is
   necessary.

**Data access is its own concern.** PyLiPD and PyleoTUPS are technically
code (handled by the code agent; PyleoTUPS isn't integrated yet), but they
are the *data* part of a scientific workflow. "Open `hccd.lpd`" should route
to PyLiPD; "search the graph..." should route to SPARQL.

**Intent must be resolved from the request *and* the notebook.** "Use
Lomb-Scargle to run spectral analysis" in a notebook that already contains
preprocessing steps means "just give the spectral call", not the whole
workflow. With no preprocessing present and a request that also asks for
data etc., the full workflow is appropriate.

**Mode (updated 2026-11-04): building the agreed first version**, one piece
at a time. Anything outside its scope stays design-first: work it out with
Deborah and write it into this file before changing code.

**How much to produce is a central open question.** Three levels
(confirmed by Deborah):
1. **Snippet** — one call, no surrounding context ("use Lomb-Scargle").
2. **One step of a workflow** — snippet-sized, but has neighbours. Two
   flavours: (a) *adding the next step* while working through a workflow
   (gap rules below apply); (b) *editing an existing step*, which can
   invalidate other steps (switching to `mtm` makes regridding required).
3. **Whole workflow.**
The ported checker was built only for level 3.

**User-facing principles (Deborah, 2026-10-01):**
- **Always gentle in tone** — every warning, question, correction and edit
  proposal, especially about the user's own code.
- **We want users to learn** — always give the *why*; part of the user
  base is new to paleoclimate.
- **Never go blind** — no silent compliance, no silent changes.
- **Voice: PaleoPAL speaks as "I"**, consistently (e.g. "I'm still
  learning…", "I recommend…"). Tentative (Deborah: "maybe") — revisit if
  "we" (the LinkedEarth team) turns out to fit better, but never mix.

**Summary — how much PaleoPAL produces (agreed 2026-10-01; details below):**

| situation | what PaleoPAL does |
|---|---|
| Blank notebook, or only data loaded | Builds the whole workflow: required + recommended steps, recommended ones labelled with the reason |
| Next step, nothing missing | Gives the snippet |
| Next step, a required step is missing | Gives a corrected snippet including the step, with the reason |
| Next step, a recommended step is missing | Asks, with the reason; waits for yes/no |
| Editing an existing step | Shows before/after + reason in the panel; applies only on yes; points out later code to re-run |

**Deciding the level — working idea: the level comes from the gap**
between the steps a request requires (per the workflow YAML) and what the
notebook already contains. Nothing missing → snippet; everything missing →
whole workflow; request points at an existing step → one step + check what
it affects downstream.

**Decided (Deborah, 2026-10-01) — request reads as a snippet but the
notebook is missing a required step** (e.g. "use Lomb-Scargle" on a
Series that was never standardized):
- **Never silently give just the snippet.** Part of the user base is new to
  paleoclimate; PaleoPAL must not go blind.
- **What PaleoPAL does depends on how required the missing step is.** The
  YAML has two labelling systems — rules carry `severity`
  (prohibited/discouraged/advisory), steps carry `requiredness`. A missing
  *step* is judged by its requiredness:
  - **`required`, or `determined_by(...)` / `required_for(...)` that
    applies here** → treated like prohibited: give a **corrected** snippet
    that already includes the missing step (e.g. regrid + MTM), with the
    reason. The user can explicitly override.
  - **`recommended`** (e.g. detrend, which the YAML says must never be
    chosen silently) → don't add it. Ask whether to add it, give the
    reason, and **wait for yes/no**.
  - **`available_not_default`** → say nothing.
- **User explicitly asks for an unnecessary step** (e.g. regrid before
  Lomb-Scargle — the A/B harness's immovable `override_unnecessary_regrid`
  case): before writing it, say why it isn't needed and **wait for
  yes/no** (Deborah, 2026-10-01). Users may legitimately insist — e.g.
  comparing two methods on identical preprocessing. Implication for the
  checker: an override the user confirmed must be passed to it, so it
  doesn't flag or "repair" what the user chose.
  **How long a "yes, I insist" holds (Deborah, 2026-10-01):** ask the
  first and second time; from the third time on, also offer "keep this
  answer for the rest of the session". **Count by kind of choice, across
  all series** (e.g. "regrid before an estimator that doesn't need it"),
  not per series — the reason for insisting usually applies to every
  record in a comparison.
- **Whole workflow** (notebook blank, or only data loaded): build all
  `required` **and** `recommended` steps **without asking**, marking the
  recommended ones as recommended with the reason. The user can delete the
  cell. The ask-and-wait rule for `recommended` applies when the user is
  working through the workflow step by step (e.g. regrid → standardize →
  spectral: ask whether they also want detrend).
- **Editing an existing step (Deborah, 2026-10-01):** do what Claude Code
  does — highlight the proposed change in place, give the reason, and ask
  whether the user wants it applied. Never assume one step per cell: a
  cell may hold a whole chain (`ts.interp().standardize().spectral()`) or
  several steps. The unit of change is the code, not the cell. The VS Code
  extension **cannot** show a proposed edit as a diff (Deborah,
  2026-10-01) — an intermediate presentation is needed for now.
  **Decided interim:** show current code, proposed code and the reason in
  the PaleoPAL panel and ask "apply this?"; only on yes does PaleoPAL
  replace the code in the cell. Nothing in the notebook changes before
  the user agrees. Verified 2026-10-01: the extension can replace a
  cell's contents (`updateCellText` in `vscode-extension/src/notebook.ts`),
  and its webview panel (`clarifyPanel.ts`) can host the before/after view.
- **Downstream effects of an edit:** point out later code that uses the
  changed result and needs re-running (e.g. a `psd.signif_test()` cell
  after the spectral method changes).
- **Backburner — "extra assist" mode:** an opt-in setting (off by
  default) for help that would be annoying if always on. So far:
  - make `available_not_default` options (outlier removal, segmenting on
    gaps) more prominent;
  - when the user names a method that works but isn't the best fit for
    their data (e.g. MTM on uneven data), add one gentle line about the
    alternative ("Lomb-Scargle or WWZ could skip the regridding"), without
    waiting for an answer. With extra assist off, just do what they asked
    (regrid + MTM, with the reason for the regrid).
  Not now; keep in mind.
- **Always say *why*** (e.g. why standardize — not something a user would
  necessarily know). The why matters to scientists; it comes from the
  rationale kept in the workflow YAML.
- Context: Pyleoclim itself raises an error for MTM on unevenly spaced
  data (Deborah), but not every prohibited case has such a guard.
- Every warning needs a reason, so every step that can be flagged needs
  one in the YAML. Standardize lacked a "why required" — added as
  `rationale:` from Deborah's explanation (2026-10-01).

**Where a workflow lives (Deborah, 2026-10-01):**
- Combine sources, but for now assume **the notebook holds the entire
  picture of the workflow.**
- Users will write steps themselves, outside PaleoPAL, and PaleoPAL must
  build on them. Example: a user loads data with PyLiPD into a DataFrame
  on their own; asked to finish the workflow, PaleoPAL must recognise and
  use that DataFrame as the data source rather than start over.

**Chatbot design (Deborah, 2026-11-05), design-first, nothing built:** the existing Chat option
(quick-pick → `/agents/chat`) is a bare model call: no system prompt, no guide, code cells dropped
(their text is in `generated_content`, which it ignores), answer appended at the notebook's end as
"**Assistant**" with no authorship line. Don't build on it. Instead: an `@agent chat` cell opens a
separate conversation (a panel), so a whole back-and-forth can happen, like Deborah's sessions with
Claude. Once a decision is reached, PaleoPAL writes a simple markdown cell summarising the
discussion, plus the resulting code if any, below the `@agent chat` cell. Example to design
against: loaded LR04, ask for a plot, then ask what other parameters there are or how to do
something else (which may reach the not-covered path and matplotlib).
**Ending a chat (agreed 2026-11-05):** both sides can. PaleoPAL offers when it thinks there's
agreement ("Shall I add this to your notebook?", showing the summary and code it would write), and
the researcher can end it any time with a panel button ("Add summary to notebook"). Nothing is
written until the researcher agrees; the cells arrive like other PaleoPAL cells (authorship line,
label, one undo, nothing runs).
**What the chat answers from (agreed 2026-11-05):** the whole notebook, not just the cells above
(code included, with each cell's author), PaleoPAL's guide, the Pyleoclim parameter reference, and
the chat so far. Each reply says whether it came from the guide/documentation or from the model
alone (with the fewer-checks note). Proposed code is shown in the panel, goes through the checker,
and reaches the notebook only through the agreed summary.
**Target names (agreed 2026-11-05):** inside PaleoPAL, three concerns: **data** (SPARQL plus loading:
graph, LiPD, PyleoTUPS, own files), **analysis** (the workflow guides; today's code agent, which now
leads to the planning flow) and **chat** (the conversation). Outside, two ways to ask: a request
cell, or a chat. The old workflow agent is made redundant by the redesign. Rename the code when the
plan step (single front door) arrives, not before; researchers keep using `@agent code` until then,
plus the new `@agent chat`.
**Chat v1 (agreed 2026-11-05):** `@agent chat <question>` opens a panel with the first answer;
back-and-forth there, each reply labelled by source; summary offered by PaleoPAL or via the button;
written below the `@agent chat` cell as "Summary of our discussion" (asked, decided, why) plus a code
cell if code was agreed. The conversation isn't kept once the panel closes (the summary is the
record; also suits demo mode); closing without a summary asks first. Chat code gets the code-only
checks; workflow planning from the chat comes later. Out: kernel reads, editing cells from the
chat, several chats at once.
**Chat v1, piece 1 built 2026-11-05 (backend, not committed):** `agents/code/chat_session.py`,
endpoint `POST /api/agents/chat_session` (`action` reply | summarize; nothing stored), tests in
`test_chat_session.py`. The model answers and names the guide steps and parameters it relied on;
Python quotes their exact text and drops names not in the files. The model also reports whether it
went beyond them (`beyond_sources`); it can't be checked, so any doubt keeps a note. Proposed code
gets the code-only checks with up to 2 quiet repairs. `Series.plot` was added to the parameter
reference (`_ALSO_DESCRIBED` in the build script) until the visualization guide owns it. Live LR04
chat with `gpt-5.5`: plotted with `lr04.plot()`, listed the real parameters, saved via
`savefig_settings`, offered the summary on agreement.
**Chat v1, piece 2 built 2026-11-05 (extension 0.1.6; tried by Deborah, who likes the interaction):**
`vscode-extension/src/chatPanel.ts`. `@agent chat <question>` (and the menu's Chat) opens a panel
beside the notebook; the whole notebook is sent each turn; replies show their code (marked "Not
run…"), note and collapsible Sources; PaleoPAL's offer and the "Add summary to notebook" button
insert the summary cells below the `@agent chat` cell with one undo. VS Code can't keep a panel
open, so closing without a summary asks right after, while the conversation is still in memory.
The old `/agents/chat` call was removed from the extension (the backend route stays).
**Visualization guide (Deborah, 2026-11-05, after kernel reads):** plots deserve their own guide.
The plot rules (object's own `.plot()`, matplotlib only as continuation via `fig, ax`, no
dismantling, PSD log-log by default) don't change between analyses, so they'd live there once.
Plot types: series and intermediate series (`Series.plot`), spectrum (`PSD.plot`), wavelet
(`Scalogram.plot`), dashboard (`Series.summary_plot(psd, scalogram)`, needing two analyses), and
"plot on the same figure" (`ax=` on all of these; `MultipleSeries.plot` overlays). Checked in
Pyleoclim 1.3.1b0. A plot of the series is good practice as part of an analysis anyway. Needs
PaleoPAL to plan with two guides at once, the same problem data loading brings, so it's the smaller
place to solve it first.
**Order (Deborah, 2026-11-05):** chat v1 → kernel reads (and maybe the corpus) → visualization guide
→ data loading. Editing a step: remind Deborah when we get there.
**Chatbot / explanation (planned, never built):** a conversational mode
where a researcher asks "why did you choose this method?" or "explain this
part of the query". Deborah's idea: the same channel can ask the user
directly when the source of truth is ambiguous. (Ties to keeping
`ordering_rationale` etc. in the YAML — the rationale is what the
explanations are made of.) Note: the code agent already has a
clarification step (`detect_clarification_node` in
`agents/code/handlers.py`). Per Deborah: PaleoPAL was first built with a
web interface, where clarification never worked well. Correction from
reading the code (2026-10-01): the VS Code extension *does* have a
clarification flow — a webview panel with questions (choices or free
text) and Submit/Cancel, re-sending the request with the answers
(`showClarificationPanel` in `vscode-extension/src/clarifyPanel.ts`). How
well it works in practice is unknown.

**Data provenance decides whether PaleoPAL can interpret a DataFrame
(Deborah, 2026-10-01).** This is the provenance axis `data_loading.yml`
was meant to capture.
1. **From a SPARQL query** (on LiPD files via PyLiPD, or on the graph):
   column headers are the variables in the query's SELECT. Names alone
   aren't reliable (a user may write `?x`), and the graph structure only
   partly helps — meaning comes from context in the query. E.g. to get
   time, the query must FILTER a variable name on 'age' or 'year', so
   the FILTER clauses say what a column is.
2. **From PyLiPD / PyleoTUPS functions:** always the same column names.
   Descriptions of these DataFrames don't exist for all functions (some are
   in tutorials); they could be built from the tutorials and their
   rendered DataFrames — a new knowledge artifact.
3. **From the user's own file** (text, Excel): provenance unknown. Most
   users display the DataFrame, so PaleoPAL can guess from the displayed
   column names; ask when it can't.
Rule that follows: infer from provenance when known; otherwise guess from
what's visible in the notebook; ask only when neither is enough. It was discussed in earlier sessions
as part of Phase 3 (plan step). A hard requirement: a user must be able to
go back into a workflow and edit just one step, or ask for clarification
about one step — so workflows need addressable steps, and "one step"
sits between "snippet" and "whole workflow".

Earlier context: `~/Downloads/PaleoPAL_status_and_plan.md` (2026-09-01
web-session summary — repo audit, A/B results, proposed pipeline, phase
plan). It predates the agent-scope framing above and assumes every
request is a full workflow. Older web-session context may be missing;
when in doubt, ask Deborah.

**Hierarchical retrieval is the intended flow (Deborah, 2026-11-04).** First
find the relevant workflow file (e.g. the spectral analysis YAML), put it in
context together with the notebook history, then decide what to do next and
call the code agent or the workflow agent. Worked example: "run spectral
analysis on lr04" with no earlier analysis should be detected as needing the
whole spectral workflow, not an improvised script. In that test the notebook
held only the Pyleoclim import and the LR04 load. PaleoPAL should read those
cells, recognise both as done (today it re-imports in every generated cell),
find the instructions in the YAML, and only then use vector search to gather
code snippets. Agreed order (2026-11-04): build a small version of this flow
before the corpus cleanup.
**Who does what (agreed 2026-11-04):** the LLM interprets the request;
model-free Python reads the cells, looks up the YAML's steps, compares them
and picks the level; vector search gathers snippets for those steps; the LLM
writes the code, then the checker runs. Snippets show how to write a step and
cannot add steps. When the Python reader isn't sure what a cell does, it asks.
**When PaleoPAL builds a workflow, each step goes in its own cell (Deborah,
2026-11-04).** It still can't assume this of the user's own cells. All steps
arrive at once as ready-to-run code cells, not `@agent` instruction cells,
and nothing runs on its own. Each code cell has a **markdown cell above it**
explaining what the step does and why. This brings forward the "PaleoPAL
writes markdown" item. The extension sends markdown cells as "user" messages,
so PaleoPAL's own markdown must be marked (e.g. in cell metadata) or later
requests will read it as the researcher's words. **The authorship must also
be visible in the cells themselves** (Deborah, 2026-11-04), as good practice
for showing what the AI did.
**First version (agreed 2026-11-04), scope is the LR04 case only:** notebook
has an import and a loaded series, request is a spectral analysis. In: LLM
interprets the request; reader finds the import and series; Python finds the
missing steps from `spectral_full.yml`; vector search gathers snippets; LLM
writes the steps without repeating import or load; extension inserts a
markdown + code cell pair per step. Out for now: snippet-level requests,
edits, multi-series tracing, kernel reads, the repair loop, wavelet.
When the objective is unstated, a whole workflow stops at the spectrum and
**proposes** the significance test (Deborah, 2026-11-04); the detector reports
that step as `propose`.
**Progress:** the detector is built and tested but not connected
(`backend/agents/code/workflow_detector.py`, tests in
`test_workflow_detector.py`). It has its own reader, separate from
`extract_facts`; the two must merge so gap detection and the checks share one
logic. PyYAML is only installed indirectly, so add it to
`backend/requirements.txt` when connecting the detector.
The request interpreter is also built and not connected
(`request_interpreter.py`, tests in `test_request_interpreter.py`): the LLM
picks the analysis, series, objective and method from the workflow file's
lists, and Python rejects anything else. Tried on 10 phrasings with
`gpt-5.5`. **When connecting:** if `problems` is non-empty, ask the user; the
detector's single-series fallback must not run, or a request for a missing
`sst` would silently analyse `lr04`. When no series is named and exactly one
is loaded, use that one (Deborah, 2026-11-04).
Per-step snippet search is built and not connected (`step_snippets.py`, tests
in `test_step_snippets.py`): one query per method named in the YAML, keeping
only snippets that call that method. Tried on the copied index: no kept
snippet dismantled a series, but quality is uneven. Regrid has only 2 weak
results, one a `utils` call the checker discourages. The filter is loose, since
`.plot(` also matches plots of a series. Snippets can show extra steps, so the
writing prompt must say they don't add steps.
The writer is built and not connected (`workflow_writer.py`, tests in
`test_workflow_writer.py`). Python chooses the steps, defaults the method from
the YAML, and rejects replies that change the steps or repeat an import. A
model writes each explanation in its own words because that flows more naturally
(Deborah, 2026-11-04), speaking to the reader as "you". Required statements stay
fixed. Sources don't depend on the model: Python adds the exact YAML text and
names the examples given to the model, in a collapsible section (agreed by
Deborah; built). Deborah-approved source text is in the YAML for detrend,
standardize, visualize and Lomb-Scargle. WWZ and MTM have none yet, and Python
says so in the cell. This makes unsupported claims visible; it doesn't prevent
them. Example found 2026-11-04: `preserve_mean=True` (Pyleoclim's default is
False, per Deborah) appears in both detrend examples the model received.
**Don't limit arguments to the YAML (Deborah, 2026-11-04):** Pyleoclim defaults
may be computationally cheap but not scientifically correct, and examples are
meant to carry the expert choice of arguments. So examples do have authority
over arguments, though not over steps. That raises the bar for the corpus
rebuild: an indexed example can teach arguments, so its quality matters, not
just its uniqueness. Don't encode science-dependent arguments as YAML rules either,
since the right value depends on the application (Deborah, 2026-11-04); the
chatbot should explain a parameter and point to where it appears as an example.
Indexing check (2026-11-04): `index_notebooks.py` already embeds markdown context
with code, and 404 of the 430 indexed snippets have real markdown. But the writer
only sends the model the code, so that context isn't used yet. Keep markdown with
code in the corpus rebuild (Deborah).
**Connection:** `planning_flow.py` connects the pieces, called first from
`route_agent_request_with_custom_config` for code and workflow requests when
`USE_PLANNING_FLOW=true` (set only in `docker-compose.redesign.yml`). Requests
it doesn't cover return None and use the old pipeline. It returns `cells` plus
one combined `generated_code`. Extension 0.1.3 inserts `cells` with one undo, a
hidden `metadata.paleopal` label and the visible authorship line, and leaves
PaleoPAL's markdown out of the history it sends. Tested by Deborah 2026-11-04: 9
cells, one undo, the `sst` question; the label saves as cell `metadata.paleopal`
with the step id. **Who wrote a cell (agreed 2026-11-04, not built yet; needed for
"next step" and "edit a step"):** PaleoPAL reads every cell knowing its author. A
researcher's cell is their words and code. An unchanged PaleoPAL cell is its own
earlier note, which it can explain but which isn't an instruction. An edited
PaleoPAL cell counts as the researcher's: their edit wins and changed arguments
are deliberate. Detect edits with a fingerprint of the text stored in the label
and compared by the backend. On the next run, change the line to "Written by
PaleoPAL, edited by the researcher"; never remove it. Dropping PaleoPAL's markdown
from the history is a stopgap until then. Build it with Node 23
(`~/.nvm/versions/node/v23.7.0/bin`), since the default Node 10 is too old. Confirmed
from VS Code on 2026-11-04: the LR04 request got detrend, standardize, spectral
and plot, and the code ran and produced the plot (Deborah). `@agent code` is now
only the way in; later, the plan step as front door should remove agent choice.
**Repair loop built (2026-11-04):** problems go back to the model up to
`MAX_REFINEMENTS` times, quietly; after that the code is shown with the "still
learning" warning. Repairs append to `data/repair_history.jsonl` in the backend
data volume. Code-only checks now run on new code only (`check_new_code`), so a
researcher's earlier code isn't blamed on PaleoPAL. Seen with `gpt-5.5` fixing a
forced `plt.loglog` draft. **Build order agreed 2026-11-04, keeping the spectral
example:** next step, then kernel reads, editing a step, several series. Decide
in the next session whether data loading (its own YAML) jumps ahead; Deborah's
held-out tests come after, since most need data loading.
**Build order revised (Deborah, 2026-11-05), for the AGU focus on human
interaction:** (1) stop dropping requests without a word, including explain-and-wait
for an unnecessary regrid; (2) a first chatbot that explains PaleoPAL's own cells
and answers "what other parameters does this function take?"; (3) kernel reads,
and maybe the corpus. Editing a step is also wanted: remind Deborah when we get
to it, since she'd forgotten it. Data loading and the wavelet workflow move down
the list.
**"Next step" design (agreed 2026-11-04):** yes/no gap questions use the
extension's panel, resending the request with the answer. A researcher must be
able to find a record of these choices (Deborah); where is still open. The old
clarification step isn't reliable and needs its own work, so with the planning
flow on, the backend forces it off whatever `paleopal.enableClarification` says.
The panel itself doesn't depend on that setting. **Record of choices (agreed):**
a visible line in the affected cell's markdown, written by Python, with the
answer also stored in the cell label so it isn't asked again.
**Next step built 2026-11-04** (`plan_next_step` in `workflow_writer.py`;
extension 0.1.4; panel not yet tried by Deborah). A missing required step is
added with the reason; a missing recommended step asks only before the spectrum
is computed. On yes, a step that belongs before ones already run starts a new
chain from the series, leaving the user's cells alone. Regridding after a later
step is explained, not attempted, until the edit flow or kernel reads exist. Code
continues from the newest variable, and `correct_object` checks that variable:
checking the named series made repairs discard earlier detrending. A next-step
snippet needn't display its result. PaleoPAL's markdown is now sent as its own
note with its decisions; edit detection (the fingerprint) isn't built yet.
`ask_reason` on detrend approved by Deborah. Panel Yes/No tested by Deborah.
**Objective wording (Deborah, 2026-11-04):** requests about periodicities, cycles
or peaks count as peak detection, so the test is added unless the work is
described as preliminary; this nuance isn't settled, and the wording is in the
YAML's `asked_as`. A step's code calling another step's method is flagged and
repaired, after the model chained `signif_test` into the spectral step. A plain
"run spectral analysis on lr04" keeps proposing the test rather than adding it
(Deborah, 2026-11-04). A stated goal also brings its required step into a next-step
plan, and the checker doesn't demand steps a plan leaves for later.
**Parameter definitions (Deborah, 2026-11-04):** when a cell sets parameters, add
their definitions from the Pyleoclim docs to its markdown. A reference file built
once is enough for now, but definitions and defaults depend on the Pyleoclim in each
researcher's kernel, so in reality this must follow the kernel and be per-user.
Built: a collapsible "Parameters" section, from `workflows/pyleoclim_parameters.json`
(`scripts/build_pyleoclim_parameters.py`, run in the `pyleo` environment), including
arguments passed on to `pyleoclim.utils` and `settings` keys. Links go to Read the
Docs: a released version to its `v…` pages, a `b` version always to `latest`
(Deborah). The execution container has Pyleoclim 1.2.1, her kernel 1.3.1b0.
When the API check is revisited: `api_validation.py` reading an installed Pyleoclim sees
only a method's signature, so it rejects valid `**kwargs` like `bin(bin_size=...)`.
**Later activity, not now:** fix errors in the Pyleoclim documentation; don't work
around them in PaleoPAL.
**Wording in cells (Deborah, 2026-11-05):** researchers see "PaleoPAL's guide", not
"workflow file"; "Code examples I was shown"; "the latest Pyleoclim documentation" for a
`b` version until kernel reads give the real version.
**Old-pipeline fallback seen again (2026-11-05):** `@agent code plot the timeseries` isn't in
the spectral guide, so it fell to the old pipeline, which reloaded LR04, converted it to pandas and
plotted with matplotlib. Proposed next (after the chat): when no guide matches, answer like the chat,
model-only with the note and the code-only checks, instead of the old pipeline.
**No source (Deborah, 2026-11-05), two different cases:** (1) a workflow file exists but
doesn't cover this step: "No source text provided." (2) No workflow file fits the request
(e.g. a pandas question): the LLM answers, and PaleoPAL must say no guide matches and the
code comes from the underlying model only. Case 2 isn't built.
**Intro cell (Deborah, 2026-11-05, not built):** people rarely read docs, so PaleoPAL
explains itself in the notebook. Add it once per notebook, when it has no PaleoPAL cells,
**right after the request**, not at the top, since a researcher may call PaleoPAL halfway
through and wouldn't see it there. It tells them they can delete it.
**Filed for later (Deborah, 2026-11-04):** Varun's library of notebooks and functions is
reachable in Qdrant. Link the Sources section to it so people can retrieve what a cell
drew on.
**Still to fix (2026-11-04):** requests PaleoPAL doesn't act on are dropped without a word
(e.g. ARIMA, slicing), and asking for an unnecessary regrid should explain and wait.
The ARIMA and slicing example came from Claude's own test request, "use lomb-scargle
on lr04 and also fit an ARIMA model and slice to the last 500 kyr". PaleoPAL wrote
the spectral workflow and silently left out the other two parts.
Deborah (2026-11-05): ARIMA belongs with significance testing, not as a fit, so that
request was badly worded. (Fact: Pyleoclim 1.3.1b0's `PSD.signif_test` offers only
`ar1sim`, `ar1asym` and `uar1`; ARIMA appears only in `utils/tsmodel.py`.) Slicing
must be covered as a step of the spectral workflow, included only when the request
asks for it ("perform spectral analysis on the first 5000 years of the record").
PaleoPAL should read such a request as slice, then the workflow, not refuse part of
it. **Slicing goes first (Deborah, 2026-11-05):** preprocessing should only be done
on the part of the record being analysed, which includes detrending, removing
outliers, regridding and standardizing. ARIMA is tabled; Deborah isn't sure where
it would come from either.
**Slice built 2026-11-05.** The model reads the range from the request, e.g. "the first
5000 years" became `lr04.slice([0, 5])`, because it knew from memory that LR04 is in ky BP.
Until kernel reads exist, Python adds a fixed note under the slice cell, with the numbers
taken from the code: it says how the range was read, asks the researcher to check the units
and which end of the record was meant, and to change the numbers given to `timespan` if
wrong (wording approved by Deborah). **For kernel reads:** Pyleoclim Series carry their
time units (`time_unit`), so read them; also count the points left after slicing (0–5 ka
of LR04 is only 6 points, too few for a spectrum).
**Skipping a recommended step (Deborah, 2026-11-05):** each cell continues from the previous
cell's variable, so deleting or not running a recommended step (e.g. detrend) breaks the next
cell with a `NameError`. Stopgap built: Python adds a line under a recommended step whose
result the next cell uses, "If you'd rather skip this step, don't run this cell, and change
`lr04_detrended` to `lr04` in the next cell", with names from the code. The proper fix is the
edit flow (rewire the later cells); kernel reads can also spot a cell that wasn't run.
**Uncovered parts of a request (built 2026-11-05, temporary until the model-only path):** the
interpreter lists them in the researcher's words (`not_covered`; settings of a step don't count),
and Python puts a note first (after the intro): "I haven't done this part of your request, because
my guide to spectral analysis doesn't cover it yet: … I'd rather tell you than guess. Everything
below follows the guide." (wording approved by Deborah). Live with `gpt-5.5`: listed comparing with
insolation, an ARIMA fit and "tell me what causes them" (interpretation, issue #1); listed nothing
for a slice range, a linear detrend, an interpolation step or a significance test. Saving a figure
was first listed too, but Deborah pointed out it's a setting of the plot step (`savefig_settings`),
so the interpreter now gets each step's setting names from `pyleoclim_parameters.json`.
**Gap found:** the writer never sees parameter definitions, so it guessed
`savefig_settings={'path': './', 'filename': ..., 'format': 'pdf'}`, which raises a `TypeError`;
`{'path': 'lr04_spectrum.pdf'}` works. Patched with a rule in the writer prompt. The general fix,
not built: send the writer the definitions of the settings a request touches.
**Unnecessary regrid built 2026-11-05:** asking to regrid before Lomb-Scargle or WWZ gets a yes/no
panel question with the `regrid_unnecessary_for_tolerant_methods` `must_say` as the reason. Yes
regrids and records "I regridded because you confirmed it…"; no skips it and records "You chose
not to regrid…". Only that request's answer counts: the agreed "ask twice, then offer to keep the
answer for the session" rule isn't built. **Regrid already in the researcher's cells (Deborah,
2026-11-05):** with no method named, the default switches from Lomb-Scargle to MTM, with her
wording (`method_selection.when_already_regridded` in the YAML). The WWZ default for the
slope (scaling exponent) also switches to MTM on regridded data (Deborah, 2026-11-05). A named Lomb-Scargle
is kept without comment, and the researcher's own regrid is never flagged by the checker.
**Filed (Deborah, 2026-11-05): an optional plot of the series at the start of the
spectral workflow, if it hasn't been plotted yet.** Detrending isn't always
necessary, and people may want to look at the series before deciding on it. Deborah
expects this to come with kernel reads. Note that "already plotted" can be partly read
from cell text, but whether the plot was actually run and seen can't.
**For the chatbot, part two of the redesign
(Deborah):** a researcher should be able to ask where a piece of text or an
argument came from, so PaleoPAL must keep what each cell was given. For the demo: long series can take a long
time to compute (seen with `cenogrid_d13C` on 2026-11-04), so choose demo
records with that in mind; the file records a cost only for WWZ so far.
The chain was run by a test script, not the backend, on the LR04 request with
`gpt-5.5` (report: `~/Documents/PaleoPAL/smoke_tests/2026-11-04/first_flow_lr04.md`).
It wrote detrend, standardize, spectral, plot and the significance proposal,
with no checker findings, and the code ran in the `pyleo` environment.

**Plan step = the single front door (agreed 2026-10-01).** Every request
goes through one plan step that decides both *where it goes* (graph /
data / analysis — replacing manual agent selection) and, for analysis:
the level, the objective (default exploratory), which series, facts about
the data (from the kernel), and the user's earlier choices. Reason:
requests span concerns, e.g. "open `jh.lpd` and run a spectral analysis on
the sea surface temperature timeseries" = data loading + choosing a
variable inside the dataset + analysis, planned together.
Choosing a variable inside a dataset (agreed): if exactly one variable
matches, use it and say which ("using `SST` (Mg/Ca), age in years BP");
if several match (different proxies, calibrations, time axes or age
models), list them briefly and ask.

**Where a user starts (Deborah, 2026-10-01) — basis for planning
scenarios; start abstract:**
1. *From scratch.*
   - 1a. Blank notebook, no preamble, just a request — the user and
     PaleoPAL build things together.
   - 1b. Blank notebook with a preamble, which may state the scientific
     question and guide the analysis (PaleoPAL might even suggest one).
     Connects to GitHub issue #5 (notebook markdown as planning context).
   Expect a lot of back-and-forth; the planned workflow gets edited along
   the way. Idea: **the planner sorts out the data problem first, then
   plans the rest of the analysis.**
   - *Filed for later:* PaleoPAL only writes code cells today; it may need
     to write markdown too (create sections, state the intent).
2. *Data already loaded* (from the graph, LiPD files, or the user's own
   files) — planning starts at the analysis.
3. *Established workflow* — changing a few steps (the edit flow).
**Plan structure (agreed 2026-10-01): data phase → analysis phase.** The
batches are where the user *enters*: from scratch = both phases; data
loaded = analysis phase (data phase = recognising what's loaded); established
workflow = edit flow + downstream. `data_loading.yml` is the knowledge for
the data phase, as `spectral_full.yml` is for analysis.
**Data → analysis can repeat in one notebook:** data enters and is
analysed; later new data enters and is either analysed on its own or
combined with the earlier data and analysed together. Data → analysis
stays the planning unit each time.
- **Combined, same analysis** → redo A and B together with common
  parameters (`MultipleSeries`; rule `multiseries_common_parameters`),
  proposed through the edit flow since it changes A's earlier results.
- **Separate** → B gets its own data → analysis cycle, independent of A.
  Example (Deborah): the PaleoPCA paleobook
  (`backend/libraries/notebook_library/my_notebooks/paleobooks_gallery/PaleoPCA/notebooks/paleoPCA.ipynb`)
  — proxy PCA via Pyleoclim (`mgs_common.pca()`), then CESM model PCA
  via xarray + `eofs`, each its own cycle; then a "Model-Data
  Comparison" section brings the two *results* together.

**Coverage and fallback (Deborah, 2026-10-01).** The focus is LinkedEarth
tools first, so PaleoPAL may not do well on e.g. climate-model data yet.
Principle: **if it's not in the knowledge base (RAG/workflow files), use
the LLM's own answer — still inside PaleoPAL.** Example: "help me change
something in this DataFrame" is pandas — the LLM is good at it, but it
doesn't go through the RAG pipeline the checker is part of.
- **Naming (agreed 2026-10-01): "LLM-only" vs "LinkedEarth-covered"** —
  the coverage axis. Every request has two labels: how it's asked
  (conversational / code) and its coverage. "Standard method search" (the
  proposal's term) stays the name of one *task* type, usually LLM-only.
  **Reminder for Deborah:** put this terminology in the user docs when we
  write PaleoPAL tutorials.
- **Always tell the user** when an answer is pure LLM generation, not
  through the RAG pipeline: a gentle note that it has fewer checks than
  LinkedEarth workflows.
- No library-specific checks are attempted for fallback answers — too
  many libraries.
- **Don't call the fallback "general help"** (Deborah). Conversational
  requests can still go through the LinkedEarth pipeline: "not sure what
  to do with these data, help me plan next steps" (chatbot), or "do you
  have data covering the past 1000 years on the graph?" (a SPARQL query
  under the hood, but the answer is conversational). So *conversational
  vs code* and *covered by LinkedEarth knowledge vs LLM-only* are separate
  axes. Name for the fallback still to be chosen.
- **Model-data comparison, for now:** the data side gets its workflow file
  for processing; the rest falls back to the LLM.

No good real use cases exist yet: the paleobooks in this repo are the
closest to scientific workflows but are written after the fact, not as
the work happens. Plan: do our best abstractly, then Deborah does real
scientific work with PaleoPAL to see where it breaks.

**The redesign is deeper than adding pieces to the existing agents** — the
current three-agent split may not survive it. The direction is being
re-examined with Deborah (context from earlier web-interface sessions may
have been lost). Until that's settled, treat the Phase 1 plan below as
provisional.

## Locked-in design decisions — do not relitigate without discussion

- YAML workflow content (e.g. `spectral_analysis.yml` / `spectral_full.yml`)
  must be machine-consumable only. No human-only comments or structure in
  what PaleoPAL actually reads as prompt content.
- Preprocessing-step rationale (`ordering_rationale`) is structured as
  pairwise transitions (`step` → `after` → `reason`), not per-step
  annotations — the reasoning describes relationships between steps.
- `band_selection`-style context needs distinguish session/plan history
  (prior PaleoPAL turns) from notebook markdown (researcher narrative that
  may predate the session).
- Open design questions live in GitHub Issues, never as `TODO`/`OPEN` blocks
  inside YAML the model reads — unresolved uncertainty in the prompt is a
  measured cost to generation quality, not just clutter.
- Disclosure obligations (e.g. "state that regridding was skipped") cannot
  be enforced via prompting — confirmed architecturally immovable in A/B
  testing. They require post-generation enforcement.

## Current state (Phase 1)

- **Item 1 — done.** All TODOs in the spectral workflow YAML resolved.
- **Item 2 — in progress.** AST verification checks ported from the
  `~/paleopal-ab/` harness (`checks.py`) into a standalone module
  (`verification.py`): `extract_facts`, `run_checks`, `check_disclosures`
  ported near-as-is (pure functions, no harness state); a new `gate()`
  function added for live blocking semantics (prohibited → block + repair,
  discouraged → warn, advisory → surface) since the harness's `score()` was
  built for A/B aggregation, not live gating.
  - **Placed in this repo:**
    - `backend/agents/code/verification.py` — next to the code agent's
      handlers, which already parse fenced code from the LLM response and
      run a refine loop (`should_refine_code` / `refine_code_node`).
    - `backend/agents/code/api_validation.py` + `pyleoclim_api.json` —
      import dependency of `run_checks()`; the JSON must sit next to it.
    - `backend/workflows/spectral_full.yml` — deliberately outside
      `backend/libraries/` (everything there gets vector-indexed; rules must
      not compete with instances on similarity) and outside
      `backend/agents/workflow/` (that's the workflow-generation agent, a
      different sense of "workflow").
    - Not yet wired into the pipeline — nothing calls these modules yet.
  - **Scope problem (found 2026-10-01):** the checks were built in the A/B
    harness against whole-workflow tasks. Several assume the code should
    contain the full pipeline (`required_steps_present`,
    `regrid_before_even_spacing_method`, `preprocessing_order`). For a
    code-agent *snippet* request, where preprocessing was done earlier in
    the notebook, those checks would wrongly flag correct code. Resolved
    by the rule in the next bullet.
  - **Checker redesign (agreed 2026-10-01).** The 23 code checks split
    into 13 that need only the new code (parses, API exists, valid
    `method=`, matplotlib dismantling, rebinding, discarded results…) and
    10 that need workflow context (regrid before MTM, preprocessing
    order, required steps, significance for peaks, double detrending…). **Rule: run the
    checks on the workflow as it will be after the new code is added**
    (notebook + new code; for an edit, notebook with the edit applied),
    not on the new code alone. Same checks then work at every level. The
    same reader (`extract_facts`) also finds existing steps for gap
    detection.
  - **Requirement: trace each series** (Deborah, 2026-10-01 — several
    records in one notebook will be very common). Today's reader checks
    loosely ("any regrid call above the MTM call"), which wrongly passes
    regridding record A then running MTM on record B. The reader must
    follow each object's lineage (`ts_a` → `ts_a_even` → …) and judge
    each step against the history of the object it's applied to.
  - **Cell text vs kernel (agreed 2026-10-01).** Cell text traces each
    series' history; the kernel confirms current state where it can be
    asked directly (e.g. is it evenly spaced now). When they disagree,
    **flag it to the user**, never silently pick one. Both directions:
    - text shows a step the kernel lacks ("cell 5 regrids `ts_a`, but
      `ts_a_even` doesn't exist — did you run it?");
    - kernel has an object with no cell that creates it (deleted cell) →
      offer to add that cell back ("should I add that cell?").
    - **Recovering deleted code:** the kernel's input history (IPython
      keeps the source of every executed cell until restart) is the
      primary source — works for all code. Pyleoclim's `Series` log
      (added by Julien for convenience, **off by default**) could be
      turned on under PaleoPAL, but covers Pyleoclim only, so it's
      secondary. After a kernel restart the object is gone too, so there's
      nothing to reconcile.
    - Simpler path (Deborah): if the user deleted a step's cell and then
      asks for something that needs it (deleted regrid, then MTM), just
      re-offer the cell — it's needed for reproducibility anyway.
  - **General rule (agreed 2026-10-01): the cell text is the truth for
    which steps happened; the kernel only answers questions about the data
    itself** (e.g. was it evenly spaced to begin with). A step that exists
    only in the kernel counts as missing and goes through the normal gap
    rules (optionally noting "your session still has `ts_a_even`, but no
    cell creates it"). The kernel never substitutes for a step.
  - **Check-by-check review** (code-only checks):
    - *Group A — "will it run?"* (`code_parses`, `api_methods_exist`,
      `api_kwargs_valid`, `method_literal_valid`): **agreed as-is** —
      prohibited, PaleoPAL's new code only, quiet repair. Note for the
      data-loading work: the API checks only know Pyleoclim; PyLiPD /
      PyleoTUPS calls will need their own API lists or be skipped, or
      correct calls will look "unknown".
    - *Group B — matplotlib dismantling* (`object_not_dismantled`, rule
      `matplotlib_is_continuation_not_fallback`, severity discouraged).
      Matplotlib *after* Pyleoclim via returned `fig, ax` is correct;
      extracting `.time/.value/.frequency/.amplitude/.period` into `plt.*`
      is the violation.
    - **Gate change (agreed 2026-10-01): for PaleoPAL's own code, quietly
      repair every violation, whatever its severity** (prohibited,
      discouraged, advisory), and **record each repair in the internal
      repair-history library.** The ported
      `gate()` only repairs prohibited and merely warns on discouraged —
      which would let the original matplotlib problem through with a
      warning. Severity now only governs how PaleoPAL treats the *user's*
      gaps and choices. A user explicitly asking for matplotlib is a user
      choice → ask-and-wait path.
    - *Group C — how code treats objects* (`no_user_variable_rebinding`,
      `no_discarded_results`, `result_displayed`, `uses_core_api`):
      agreed as-is; quietly repaired in PaleoPAL's code.
    - **The user's own earlier code (agreed 2026-10-01):** the checker
      sees it too. PaleoPAL mentions a problem in the user's code gently,
      once, **only when it affects the current request** (e.g. "`ts` was
      regridded in cell 2 — is that the series you want analysed?").
      Never lecture about style. Principle: **we want users to learn.**
      **Exception — user's code breaks a *prohibited* rule that affects
      the request** (e.g. their cells standardize *then* regrid): propose
      the fix through the edit flow (before/after + why + ask), not just a
      mention.
    - *Group D* — `no_runtime_data_branching`, `cwt_not_first_choice`:
      keep, quietly repaired (user explicitly asking for CWT → user
      choice, ask-and-wait). `correct_object`: keep, but needs the
      intended series from the plan step — waits for that.
      `plot_in_loglog`: **fixed 2026-10-01.** `PSD.plot()` is already
      log-log by default (Deborah), so only an explicit `in_loglog=False`
      is flagged. **If the user set it to False, assume it's deliberate
      and leave it** — no ask-and-wait (Deborah). Mechanism: confirmed
      user choices go to `gate(findings, user_overrides=...)` and are
      reported as overridden, not repaired.
    - **`gate()` rewritten 2026-10-01:** repairs every violation in
      PaleoPAL's own code regardless of severity, except user overrides.
      Tests: `backend/agents/code/test_verification.py` (stdlib
      `unittest`; run `python agents/code/test_verification.py` from
      `backend/` in the `paleopal` env). `check_disclosures()` is kept
      but marked as being retired.
    - **Chatbot capability (Deborah):** answer "what parameters are
      available?" by producing a help cell (e.g. `help(psd.plot)`). A
      parameter the user then sets explicitly is a deliberate choice —
      acknowledge it, don't "correct" it.
  - **Check-by-check review** (workflow-context checks), agreed
    2026-10-01 — all run on notebook + new code, quietly repaired in
    PaleoPAL's code:
    - *Preprocessing* (`regrid_before_even_spacing_method`,
      `preprocessing_order`, `no_double_detrending`,
      `required_steps_present`): the gap rules seen from the other side —
      gap detection (before generating) and these checks (after) must
      share one piece of logic. User's own code breaking these → edit flow.
    - *Method choice* (`no_lomb_scargle_for_slope`,
      `method_suits_uneven_data`, `no_unnecessary_regrid`): user naming a
      workable-but-not-best method → do what they asked; alternatives only
      in extra-assist mode.
    - *Objective* (`significance_tested`, `beta_estimated`,
      `no_unrequested_significance`): depend on the objective. **When the
      request doesn't state an objective, treat it as exploratory**
      (Deborah): give the spectrum, say gently that peaks need a
      significance test before interpretation, offer to add it, wait for
      yes/no. Don't run the test unrequested.
  - **Prose checks / disclosures (agreed 2026-10-01).** The harness's
    `check_disclosures()` keyword-matches the model's prose (weak: "I ran a
    significance test" passes the exploratory check). **Replaced by:
    PaleoPAL adds required statements itself**, from the workflow YAML
    (`must_say` / rationale), in the same note as its other reasons —
    the model is no longer responsible for disclosure obligations. Accepted
    trade-off: slightly mechanical wording; saves tokens. Consequences:
    - `must_say` text must be written as the literal, gentle, user-facing
      sentence (today's `exploratory_result_is_not_interpretable.must_say`
      is phrased as an instruction, not user text).
    - The unnecessary-regrid case (the A/B's immovable failure) had no
      rule in the YAML — its wording lived in the harness's `tasks.yml`.
      Added rule `regrid_unnecessary_for_tolerant_methods` with Deborah's
      `must_say` wording (2026-10-01).
    - `exploratory_result_is_not_interpretable.must_say` rewritten as
      user-facing text, approved by Deborah (2026-10-01). Both disclosure
      rules now have final user-facing wording.
  - **Two kinds of problem, handled differently:**
    1. *Gaps in the user's notebook* → handled openly with the user, per
       the summary table above.
    2. *Mistakes in PaleoPAL's own generated code* (nonexistent method,
       matplotlib dismantling, skipped significance test…) → the gate
       sends the code back for repair before the user sees it.
       **Decided (Deborah, 2026-10-01): fix quietly** — showing the
       corrections would get confusing very quickly. Users don't see the
       internal back-and-forth at all.
       - **Keep the repair history for PaleoPAL, not the user:** build a
         history/library of these internal repairs that can feed back
         into improving PaleoPAL. Analogue: the web UI's "index as
         learned" action (`POST /messages/{id}/index-as-learned` in
         `backend/routers/messages.py`) stores user-approved code / SPARQL
         in Qdrant collections `learned_code` / `learned_sparql`. Not in
         the VS Code flow. Note: these are approved *examples*
         (instances) retrieved by similarity, not rules.
       - **When repair fails** (still violating a prohibited rule after
         `MAX_REFINEMENTS` = 3 tries): show the code with a clear warning
         naming the problem and what to do — never withhold it, never
         present it as fine. Friendly framing, e.g. "I'm still learning
         and can't get this right yet — but I'm learning!", then the
         specific warning.
  - **Depends on a `task` dict** (`objective`, `data_evenly_spaced`,
    `expected_object`, `expects_plot`, `must_mention`) that nothing
    currently assembles live — it's the plan step's job (Phase 3), pulled
    forward as a dependency. Do not guess these values in the verification
    module itself.
  - **Two open decisions (Deborah's call; ask Varun for context where
    useful). Do not resolve by guessing:**
    1. Where VERIFY hooks into the live pipeline. **Fact (Varun,
       2026-10-01):** in the VS Code extension flow, generated code arrives
       as text in the LLM response and is parsed out and inserted into a
       cell — the model does not call a tool that writes cells directly.
       So VERIFY sits after code is extracted from the response.
       **Decided (Deborah, 2026-10-01):** reuse the code agent's existing
       extraction (`generate_code_node` in `agents/code/handlers.py`) and
       pass `verification.py` a plain code string. The harness's
       `has_code_block`/`extract_code_blocks` were removed as redundant.
       We (Claude) own the wiring, including skipping `run_checks()` when
       the reply has no code — a prose-only reply can be the correct answer
       and must not be scored as missing steps. Note: today's
       `should_refine_code` also forces a refine when code is < 50 chars,
       which may punish the same correct no-code replies — look at this
       during wiring.
    2. How `pyleoclim_api.json` (used for `api_methods_exist`/
       `api_kwargs_valid` — the single highest-value check) stays in sync
       with the installed Pyleoclim version at runtime. **Fact (Varun,
       2026-10-01):** there is no automatic sync today — he updates the
       API docs by hand. Also: `api_validation.py` prefers introspecting
       installed pyleoclim, but pyleoclim is only installed in the isolated
       execution container (commented out of `backend/requirements.txt`),
       so the backend always uses the bundled snapshot. **Tabled
       (Deborah, 2026-10-01):** Pyleoclim isn't changing much right now;
       revisit as a final polish once a prototype fixes the main problem
       (generating the wrong code). Don't raise it again before then.
- **Item 3 — not started.** `data_loading.yml` for PyLiPD/PyleoTUPS.
- **Item 4 — not started.** Corpus dedupe/rebuild, on a separate dev Qdrant
  collection (not a git concern). Varun knows the current indexing setup.

Integration branch: `redesign/phase1` for Items 1–3.

## Open GitHub issues (from the former YAML `OPEN` section)

1. Interpretation knowledge (e.g. "a peak above red noise is significant")
   has no home in the schema — not a rule, method property, or step.
2. Coherence's input is a relation (`wavelet_coherence(target_series)`),
   not a type — schema can't express this yet.
3. Terminology collisions beyond "periodogram" — "wavelet", "coherence" —
   deferred until those workflow files exist.
4. `MultiplePSD.plot` has no `plot_beta`/`beta_kwargs` — confirmed Pyleoclim
   gap, workaround documented in the workflow YAML.
5. Notebook markdown as a third planning-context source (alongside kernel
   inspection and session history) — first check with Varun whether the
   extension already surfaces this. Doesn't block Phase 1.

## Rules of engagement (agreed with Deborah)

- **Go very, very slow.** Deborah understands RAG pipelines but didn't
  design this architecture, and sometimes steps away for a week. Explain
  what each step is and why before doing it; don't stack several moves
  into one turn.
- **One question at a time.** Never ask several questions in one message.
- **Resuming after a break.** When Deborah says we were interrupted and
  she's picking this back up, start with a short recap: where we are,
  what we're trying to do right now, and why it matters for the project
  as a whole (high level). Then wait for her go-ahead.

## Ways of working

- **Python: use the `paleopal` conda environment**
  (`~/anaconda3/envs/paleopal/bin/python`, Python 3.11). It's outdated:
  as of 2026-10-01 it lacks 15 of the 28 packages in
  `backend/requirements.txt` (LangChain/LangGraph, FastAPI, the LLM SDKs…).
  Update it when a task needs them — ask before installing.
- **Pushing:** this Claude session has no GitHub credentials; Deborah
  pushes from GitHub Desktop.
- **Gemini (tried 2026-11-04, not working yet):** the backend's default
  `gemini-2.5-pro` returns 404 for new users, and `gemini-3.1-pro-preview`
  returned free-tier quota errors on the first request, so the key may not
  be drawing on Deborah's credits. Results so far are all from `gpt-5.5`.
  Don't mix models when judging results.
- **Docker: never touch the existing stack Varun set up for Deborah.**
  The redesign gets its own stack: `docker-compose.redesign.yml` (images
  built 2026-11-04; Varun's Qdrant index copied read-only into
  `paleopal-redesign_qdrant-data` and verified by checksum; started and
  smoke-tested 2026-11-04 by calling the backend directly). The smoke test
  exercises the **old pipeline**: nothing calls the checker or reads the
  workflow YAML yet. For tests, send with clarification **off** (Deborah,
  2026-11-04; extension setting `paleopal.enableClarification`). The
  extension path reached the backend and returned code on 2026-11-04.
  Request "runn spectral analysis on lr04" produced far more than asked,
  rated "really not what we wanted" by Deborah: an unrequested 0-3000 ka
  slice, both Lomb-Scargle and WWZ, and a summary plot. The system prompt
  in `agents/code/handlers.py` tells the model to "Try to use the code
  snippets and examples to generate the code as much as possible", and the
  output cites "established LR04 spectral-analysis examples" (retrieved
  examples not yet inspected). Still unverified: running generated code,
  and whether the extension's clarification answers (`{id, answer}`) reach
  the SPARQL agent, which reads `question`/`response`. Always run it with
  `docker compose -f docker-compose.yml -f docker-compose.redesign.yml …`.
  Host ports: backend 18000, execution 18001, Qdrant 16333/16334. The
  frontend only starts with `--profile web`. The extension's
  `paleopal.backendUrl` must point to `http://localhost:18000`.
  Why it's needed: `docker-compose.yml` hard-codes container names
  (`paleopal-qdrant`, `-backend`, `-execution-service`, `-frontend`), the
  network name (`paleopal-network`) and host ports (6333/6334, 8000, 8001,
  3000), and the Compose project name comes from the folder — which is
  the same on every branch. So a plain `docker compose up` on this branch
  would **replace Varun's containers and reuse his volumes, including the
  Qdrant index.** Plan: an override file run under a separate project name
  (e.g. `-p paleopal-redesign`) that keeps the *service* names (so
  `qdrant`, `backend`, `execution-service` hostnames still work) but gives
  new container names, network, host ports and volumes. The execution
  service's `mem_limit: 24g` is a cap, not a reservation, but Docker
  Desktop currently has only about 8 GB in total, so don't run both stacks
  at once.
  The container names must differ from Varun's (Deborah confirmed that's
  what she meant by "the same name" — it can't be kept).
  The new stack starts with an empty Qdrant index, so the libraries must
  be rebuilt — which makes **the corpus cleanup (Phase 1 Item 4) a higher
  priority** (Deborah, 2026-10-01): rebuild clean rather than rebuild the
  broken corpus. For the rebuild (Deborah, 2026-11-04): `literature_methods`
  will be removed during this redesign; `learned_code` is an intentionally
  empty placeholder for a future "remember this and learn" feature.
- **Next session order (agreed 2026-10-01):** (1) build the redesign
  Docker stack; (2) copy Varun's Qdrant index once, read-only, into it;
  (3) **smoke test** — 2–3 requests to confirm the new stack works (not a
  baseline comparison: the alpha had no consistent scientific tests, so a
  before/after comparison wouldn't mean much); (4) corpus cleanup and
  rebuild; (5) demo story / planning scenarios.
- **Docker cleanup (Deborah, 2026-11-05):** she's new to Docker and asked to be reminded
  to clean up. Rebuilds leave images and build cache behind, and the 59 GB disk filled up on
  2026-11-05, which blocked rebuilds. Check `docker system df` after rebuilding or when
  finishing a session, say what's there, and ask before deleting. Never remove Varun's images
  or volumes.
- **Held-out scientific tests:** Deborah is designing high-level
  scientific tests separately, with another AI, so Claude doesn't see
  them in advance. **Don't go looking for them**; she'll bring them in
  when it's time to run them.

- Understand architectural reasoning before touching code — don't jump to
  implementation.
- When something is genuinely undecided (marked open above), flag it and
  ask Deborah rather than silently picking an answer. Architecture decisions
  are hers to make — recommend, don't defer them to someone else.
- Scientific claims (method tradeoffs, ordering rationale, etc.) need
  Deborah's confirmation before being asserted as fact in code or docs —
  she has caught real errors here before.