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

## Agents and their scope (Deborah, 2026-10-01)

PaleoPAL has several distinct problems; earlier redesign work mixed them
together. Keep them separate. Today there are three agents:

1. **SPARQL** — queries the knowledge graph. Performing well. Do not try to
   improve it now; first see whether changes help the other agents.
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

**Mode (agreed 2026-10-01): design first, no code changes** until the
design below is worked out with Deborah, one piece at a time, and written
into this file as we go.

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
  the user agrees. Unverified: whether the extension can replace an
  existing cell's contents (vs only insert) — check extension code or ask
  Varun when we get there.
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

**Chatbot / explanation (planned, never built):** a conversational mode
where a researcher asks "why did you choose this method?" or "explain this
part of the query". Deborah's idea: the same channel can ask the user
directly when the source of truth is ambiguous. (Ties to keeping
`ordering_rationale` etc. in the YAML — the rationale is what the
explanations are made of.) Note: the code agent already has a
clarification step (`detect_clarification_node` in
`agents/code/handlers.py`). Per Deborah: PaleoPAL was first built with a
web interface; clarification works there but never worked well, and was
never implemented in the notebook/VS Code flow.

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
      `plot_in_loglog`: **bug — fix later.** `PSD.plot()` is already
      log-log by default (Deborah); the check currently requires an
      explicit `in_loglog=True` and so flags correct `psd.plot()`. It
      should only flag `in_loglog=False`. A user override follows the
      ask-and-wait rules. (The rule predates checking the default.)
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
         into improving PaleoPAL. Analogue: the web UI already records
         user corrections for PaleoPAL to take into account later (not
         yet reviewed in code; not in the notebook flow).
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

- Understand architectural reasoning before touching code — don't jump to
  implementation.
- When something is genuinely undecided (marked open above), flag it and
  ask Deborah rather than silently picking an answer. Architecture decisions
  are hers to make — recommend, don't defer them to someone else.
- Scientific claims (method tradeoffs, ordering rationale, etc.) need
  Deborah's confirmation before being asserted as fact in code or docs —
  she has caught real errors here before.