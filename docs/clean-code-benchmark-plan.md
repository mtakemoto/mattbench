# Coding benchmark plan: readable production code

**Planned — 2026-10-11:** A proposed series for comparing a model's default coding style with an explicit maintainability prompt. No new case here has been implemented or run. The audience is the owner and future fixture/scorer authors.

## Goal and source material

The owner's reported concern is code that behaves correctly but reads like a tutorial: line-by-line narration, sprawling functions, repeated rules, and unfinished refactoring. The benchmark should test whether a teammate could understand and safely change the result. Martin Fowler's discussion of [Kent Beck's simple-design rules](https://martinfowler.com/bliki/BeckDesignRules.html) gives a useful framing: passing tests, clear intent, no duplicated logic, and only necessary structure. [Fowler's refactoring overview](https://martinfowler.com/books/refactoring.html) treats behavior-preserving change and tests as central. These are sources for the rubric, not a mandate to maximize class or helper counts.

The published exercises below come from their authors' repositories. They are proposed starting points; no upstream code is copied into mattbench yet. Before vendoring a fixture, pin an upstream commit, inspect its license and test coverage, preserve attribution, and keep an untouched reference snapshot for equivalence checks. Public kata solutions are widely available, so include a small private, structurally similar fixture before claiming generalization.

## Proposed question sequence

Run each question as two separate fresh-sandbox attempts: **Base**, which gives only the task and repository conventions, and **Maintainable**, which adds the style instruction below. Both see the same behavioral requirements and tests. The later exercises are worth more than the tiny parity question for maintainability conclusions.

| Order | Source and candidate question | Behavioral gate | Style signal |
|---|---|---|---|
| 1. Small implementation | Our [even/odd case](coding-even-odd-benchmark.md), adapted from [Codewars Even or Odd](https://www.codewars.com/kata/53da3dbb4a5168369a0000fe): “Implement the specified classifier and CLI in the supplied Python file. Add focused tests.” | Exact parity, invalid input, and CLI output checks | Direct, named code; no line-by-line tutorial comments; no needless class or framework for one operation |
| 2. Behavior-preserving refactor | [Tennis Refactoring Kata](https://github.com/emilybache/Tennis-Refactoring-Kata): “Refactor the supplied scoring implementation for a teammate to maintain. Preserve its public API and every existing score result.” | Original tests and hidden score matrix stay green | Names reveal score states, branching is understandable, duplicated scoring rules are reduced, no speculative abstraction |
| 3. Extend a rule set | [ExpenseReport Refactoring Kata](https://github.com/emilybache/ExpenseReport-Refactoring-Kata): “Add the requested Lunch category with its stated limit, preserving existing report behavior. Leave the next category easy to add.” The upstream repo describes the Lunch request and includes a Python regression-test starting point. | Existing categories and new boundary cases pass | One source of truth for category policy, cohesive calculations and formatting, no copied conditional branch with changed constants |
| 4. Separate calculation from presentation | [Supermarket Receipt Refactoring Kata](https://github.com/emilybache/SupermarketReceipt-Refactoring-Kata): “Add the requested HTML receipt while preserving totals and discounts in the text receipt.” The upstream exercise explicitly asks to minimize duplication between report formats. | Both receipt outputs and discount totals match pinned scenarios | Pricing and discounts are shared; renderers own presentation; dependencies point toward reusable business logic |
| 5. Larger held-out refactor | [Gilded Rose Refactoring Kata](https://github.com/emilybache/GildedRose-Refactoring-Kata): “Add the specified new item behavior after making the legacy update path understandable. Preserve all existing item behavior.” | Characterization and new-item tests pass | Incremental refactoring, clear rule boundaries, restrained comments, no wholesale rewrite without behavioral evidence |

The [Tennis repository](https://github.com/emilybache/Tennis-Refactoring-Kata) says its tests are fast and fairly comprehensive. The [ExpenseReport repository](https://github.com/emilybache/ExpenseReport-Refactoring-Kata) describes its existing smell-heavy code and Lunch feature. The [Supermarket Receipt repository](https://github.com/emilybache/SupermarketReceipt-Refactoring-Kata) asks for tests, refactoring, and a second output format. The [Gilded Rose README](https://github.com/emilybache/GildedRose-Refactoring-Kata/blob/main/README.md) recommends tests and small refactoring steps. These source claims were checked on 2026-10-11; pin exact revisions during implementation.

## Prompt comparison

**Base task wrapper:** “Make the requested change in this repository. Preserve the public behavior and run the relevant tests. Summarize what changed.”

**Maintainable addendum:** “Write code a teammate can modify without a guided tour. Choose names that state intent. Keep each function or class responsible for a coherent job. Put each business rule in one place. Prefer a simple direct design and extract a helper only when it removes duplication or makes a concept clearer. Comments should explain a non-obvious reason or constraint, not narrate the next line. Follow existing project conventions and leave unrelated code alone.”

Do not put “SOLID,” “DRY,” or the rubric headings into only one candidate prompt and then award points for repeating those words. The addendum gives operational guidance; the reviewer judges the diff. For the parity case, a single clear function may be the strongest design. For the receipt case, separation of calculation and rendering has a concrete maintenance payoff. [Fowler's simple-design discussion](https://martinfowler.com/bliki/BeckDesignRules.html) also cautions against extra structure that serves no current need.

## Proposed scoring

**First gate: behavior and scope.** Run frozen tests and characterization checks inside the disposable sandbox; fail an attempt that changes tests to make them pass, changes unrelated files, alters public interfaces without need, or executes outside the sandbox. Report behavior separately from style. Compare style only among behaviorally valid solutions, with failing solutions still visible in the dashboard.

**Blind style review:** Show the changed files and context to a reviewer without model or prompt labels. Score each dimension 0–2 with a short cited example from the diff. Total style score is 0–12; record reviewer notes and disagreements. An automated linter can flag syntax or obvious dead code, but it cannot certify maintainability.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Intent and names | Reader must reverse-engineer purpose | Mostly understandable, some generic names | Main concepts and conditions are clear from names and structure |
| Cohesion and boundaries | Unrelated jobs are entangled | Some separation with awkward coupling | Responsibilities match reasons the code would change |
| Duplication | Same rule lives in multiple changed places | Some duplication remains or abstraction is awkward | Shared policy has one clear source, without hiding unrelated cases |
| Comments and explanation | Narrates obvious lines or hides unclear code | Mixed useful and redundant comments | Comments explain only meaningful why, invariant, or external constraint |
| Refactoring and efficiency | Repeated work, dead branches, or an obvious scalability error remain | Correct but still awkward or wasteful in places | Straightforward flow with appropriate work for the input size |
| Proportion and local fit | Tutorial scaffolding, needless layers, or broad rewrite | Mostly fits, with avoidable complexity | Smallest maintainable change consistent with repo conventions |

Record changed lines, added abstractions, comment count, and test-run history as **diagnostics only**. Do not reward fewer lines or fewer comments by themselves; a short opaque solution and an over-engineered SOLID demonstration can both score poorly. If runtime or asymptotic work matters for a fixture, set an explicit performance threshold in that fixture's behavior gate instead of rewarding speculative micro-optimization.

## Pilot and reporting plan

1. Start with parity and Tennis; check that the rubric can distinguish good direct code from comment-heavy or over-factored code. Calibrate with two human-scored example diffs before running a model comparison.
2. Run Base and Maintainable in independent fresh checkouts for the same model, with pinned source commit, tests, language/runtime, time and model-call limits. Keep the same available tools and inference settings. Counterbalance prompt order when repeating runs.
3. Show behavior pass rate and style score side by side in the UI, then dimension scores and reviewer notes under the run. Never roll behavior and subjective style into one unlabeled number. Report token/call/time/cost change caused by the style addendum.
4. Use ExpenseReport and Supermarket Receipt as the more informative first-round cases. Keep Gilded Rose and a private analogous fixture for a later held-out round. Repeat finalist runs and report spread; one tiny example cannot establish a style tendency.

**Unknown until implemented:** whether published kata baseline tests cover every behavior we need, the review time per diff, and how consistent blinded style scores will be. Those are pilot measurements, not assumptions.

## Harness integration concern

**Observed — repository inspection, 2026-10-11:** The current `run-inspect-suite.py` and web launcher explicitly know about smoke and HA. Copying those branches for each coding case would make “run everything” and the case picker easy to desynchronize. [Inspect's task and eval-set documentation](https://inspect.aisi.org.uk/eval-sets.html) supports enumerated tasks and dynamic task construction; its [task documentation](https://inspect.aisi.org.uk/tasks.html) also describes dataset-backed task definitions. A cleaner next implementation is one pinned case registry containing category, runner kind, fixture, call limit, and grader version, with both the UI and suite runner reading it. Inspect can then execute the resolved task set while the HA adapter still creates a fresh synthetic instance per case. Check these APIs against our pinned Inspect version before changing the runner; the current online docs may describe a newer release.
