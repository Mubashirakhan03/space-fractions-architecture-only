# Study results — Agent B (architecture only), three runs

**Question:** what does an LLM coding agent build from the architecture alone, and are its deviations from the
architecture visible to a reader? (Task 2 report, OP2: design–code conformance.)

**Setup** (protocol: [`EXPERIMENT.md`](EXPERIMENT.md) § Study protocol). Agent B frozen at tag `agent-b-frozen`;
model `deepseek-v4-pro` (DeepSeek official API); the same two input files as Agent A; switch *record deviations*
**OFF** (the agent was never asked to give reasons); each run in a new empty folder; limit $0.22 and 80 requests per
run (never reached); 2026-11-09, 12:08–13:00 UTC (off-peak). No change to the agent between runs, no hand edits.
Evidence: [`../evidence/`](../evidence/README.md). Generated projects: `examples/arch_only_b1` … `b3`.

## 1. The runs

| | b1 | b2 | b3 |
|---|---|---|---|
| Status / harness verification | completed / PASSED | completed / PASSED | completed / PASSED |
| Fix rounds used | 0 / 3 | 0 / 3 | 0 / 3 |
| LLM requests | 12 | 19 | 15 |
| Cost (estimated) | $0.047 | $0.043 | $0.045 |
| Duration | 189 s | 230 s | 221 s |
| Python files / source lines (without tests) | 12 / 1,080 | 21 / 1,169 | 16 / 991 |
| Agent's own tests (all pass) / test lines | 11 / 165 | 30 / 310 | 32 / 308 |
| Bot play: steps / distinct screens / Tk callback errors | 80 / 52 / 0 | 80 / 43 / 0 | 80 / 37 / 0 |

Account balance: $0.77 before, $0.63 after the three runs. Verification only checks that the program runs
(deliverables, compile, own tests, imports, `main.py` opens a window for 3 s); all three passed on the first try.

## 2. Architecture elements (functionality)

Automatic first pass in [`../evidence/CONFORMANCE.md`](../evidence/CONFORMANCE.md) (string matching in code + what
was on screen during the bot's play-through), checked by hand for the points below.

- All three apps implement the **use cases** Play Game, View Score, View Help and Update Questions, the **states**
  Playing / Paused / GameOver, the **classes** Game, Question, User, Admin, a main menu and a series of fraction
  questions; all were seen on screen. An animated intro exists in all three.
- **Components:** GameComponent, QuestionComponent and UserComponent appear by name in all three; AdminComponent only
  in b2.
- Differences that the harness did *not* catch (it only checks that the app runs):

| Run | Observation (evidence) |
|---|---|
| b1 | The intro says "press any key or click to continue", but the click handler is bound to a frame that the canvas covers completely, so **a click does nothing**; only a key press continues (`spacefractions/ui.py` `IntroMovieView`; `evidence/b1/game_play_log.jsonl` step 1). Admin requires a login; the default credentials are written in the README (`admin` / `admin123`). |
| b2 | Answer radio buttons all **look selected** before an answer is picked (`tk.StringVar(value="")` equals Tk's tristate value; `evidence/b2/game_step_003_screen.png`). Admin can **add and delete, but not edit** questions. Admin needs no login. |
| b3 | `UserComponent` (salted-hash login) is created but **never used**: the Admin screen ("Update Questions") is open to everyone — the component exists by name only (`spacefractions/ui.py`). Question screens show radio buttons *and* an empty text field. |

- The agent's tests check the behaviour of its own code. **No test refers to the architecture** (no component,
  connector, data store or technology of the design is tested).

## 2b. Structure: component links in the design vs. imports in the code (reflexion model)

The ComponentDiagram (`Architecture_View.md` § 9) has four components and three links: **Game–Question,
Game–User, Game–Admin** (Game is the hub). `scripts/evidence/conformance.py` extracts the imports between the
modules of each package (tests and `main.py` excluded; imports inside functions included), maps each module to a
component by its own docstring (e.g. a docstring starting "GameComponent: …"), else by its package's docstring, else by its
name, and compares the result with the diagram. Full tables with module-level evidence:
[`../evidence/CONFORMANCE.md`](../evidence/CONFORMANCE.md) § Structure.

| | b1 | b2 | b3 | Agent A, run 9 |
|---|---|---|---|---|
| Module layout | layered: `service` = Game, `repository` = Question, `auth` = User, shared `models` | packages `game/` (contains `Question`), `persistence/` = Question, `user/`, `admin/` | flat `game_component`, `question_component`, `user_component` + `db`, `models`, `state_machine` | packages `game/`, `question/`, `user/`, `admin/`, `store/`, `ui/` |
| Game–Question | absence (only `ui` uses both) | convergence (Question→Game) ² | absence (only `ui` uses both) | convergence (Game→Question) |
| Game–User | absence ³ | convergence (User→Game, type hint only) | absence (only `ui` uses both) | convergence (User→Game) |
| Game–Admin | absence (no Admin component) | convergence (Admin→Game) ² | absence (no Admin component) | absence (only `ui` uses both) |
| Divergences (link in code, not in design) | User→Question (`auth` → `repository`) | Question→User (`persistence.repository` → `user.user`, inside a function) | none | Admin→Question, User→Question |
| Components in code, not in design | `ui` (hub), `models` | `ui` (hub) | `ui` (hub: the only module that links components), `db`, `models`, `state_machine` | `ui` (hub), `store` |
| Mapping rule | docstrings | docstrings | docstrings | package names (A's docstrings name no component) |

² b2 put the `Question` class inside `game/` (Question merged into Game). Both "convergences" are imports of
`game.question` (by `admin.admin` and by `persistence.repository`), so they come from where the class was put, not
from a Game–Question or Game–Admin connector.
³ In b1 the Game module imports neither Question nor User; `ui` uses `service` and `repository`, and `main.py`
(outside the package) creates the `AuthService` and passes it to the UI — the composition root wires everything.

- **b1:** layered instead of a Game hub. Game depends only on the shared models; the UI (with `main.py`) connects
  the components; a new link `auth` → `repository` (User → Question) exists that the design does not have.
- **b2:** closest to the diagram on paper, but because `Question` lives in `game/`, the links run *towards* Game
  instead of from it; one undesigned link Question → User.
- **b3:** the three components do not import each other at all; every link goes through `ui.py` (a hub the design
  does not have). AdminComponent does not exist.
- **Agent A, run 9** (for comparison): Game–Question and Game–User converge; Game–Admin is missing (only `ui` uses
  both); two undesigned links to Question.
- **Recorded?** Every run's README has a component → module table (b1, b2) or list (b3), and b2/b3 say the code
  "mirrors" the architecture. No run records that the links differ from the component diagram, or that a UI hub
  was added.
- Limits: imports are a proxy for connectors (a call through an injected object, as in b1's UI → `auth`, is not an
  import); the mapping uses the agent's own docstrings, i.e. its own claims about which module is which component.

## 3. Technology deviations: visible or hidden?

The architecture describes a web/cloud microservice system: Node.js, Express.js, RESTful API, PostgreSQL, Redis,
RabbitMQ, Elasticsearch, OAuth2, Prometheus, Jenkins, Docker, Terraform (12 choices). A desktop application with the
Python standard library cannot use them, so every one is a deviation.

| | b1 | b2 | b3 | Agent A, run 9 (for comparison) |
|---|---|---|---|---|
| Tech-stack choices used | 0 / 12 | 0 / 12 | 0 / 12 | 0 / 12 |
| … named in the delivered documents (README, AGENT_NOTES) | **0 / 12** | **0 / 12** | **0 / 12** ¹ | 12 / 12 (deviation table in `DESIGN_DECISIONS.md`, with reasons) |
| Data store | SQLite | SQLite | SQLite | SQLite |
| "PostgreSQL → SQLite" stated anywhere a reader would see it | no | no | no | yes (required by A's prompt) |
| "web / microservices → desktop" stated | no | no | yes (one general line in AGENT_NOTES) | yes |

¹ b3 names no single technology, but `examples/arch_only_b3/AGENT_NOTES.md` line 6 says: "Desktop Tkinter app (per
harness rules), not the web/server stack listed in the spec's tech_stack." This is one general acknowledgement of
the web → desktop deviation, with a reason (the harness rules).

- All three runs chose **SQLite** on their own (the model no longer receives the old harness hint "persistence:
  SQLite file"). None of them says that the architecture asks for PostgreSQL (PostgreSQL → SQLite is stated in no
  run).
- Note: this choice was **constrained**. The standard-library rule (a fixed condition of the professor's task) left
  SQLite (`sqlite3`) as the only real database available, so "all three chose SQLite" says little about the agent's
  judgement; the finding is that none of them *said* it replaced PostgreSQL. b1's plan even calls its SQLite table
  a direct mirror of the architecture's `JSONB` table (`examples/arch_only_b1/agent_run/plan.md`).
- The only place where b2 admits a change is its internal plan ("introductory movie substitute — animated welcome
  frame"), which is not part of the delivered project.
- Agent A recorded its deviations because its prompt *required* a `DESIGN_DECISIONS.md` with a deviation table; when
  that requirement is removed (Agent B), no run explained a deviation per technology; one run (b3) wrote one general
  line attributing the desktop choice to the harness rules. The individual deviations stay hidden from a reader of
  the code and its documents.

## 4. What this suggests for OP2 (pilot evidence, n = 3)

1. From the architecture alone the agent built a working desktop game in every run: the functional elements
   (use cases, states, domain classes, main features) are there and the app runs without errors.
2. The architectural decisions (technology stack, data store, distribution) were dropped in 3 of 3 runs. Without
   an explicit instruction, no run explained a deviation per technology; one run (b3) wrote one general line
   attributing the desktop choice to the harness rules.
3. The *structure* of the design (component links) was not kept either, and in different ways in each run (§ 2b),
   while every run's README claims a component mapping or says it "mirrors" the architecture. No run recorded these
   structural differences.
4. The agent's tests and the harness's "does it run" check say nothing about conformance: all runs passed, while
   real gaps (unused UserComponent → unprotected admin, missing Edit, a dead click) stayed undetected.
5. Element names in the code are weak evidence of conformance (b3's `UserComponent` exists but is not wired in).

## 5. Limitations

- Three runs, one model, one architecture document: a pilot, not a statistical result.
- The conformance table is automatic string matching; the observations in § 2 were checked by hand in the code, but
  the review is not exhaustive.
- The play bot is generic (it does not understand the game); a screen it never reached is "not seen", not "absent".
  It was developed on Agent A's game and on b1, then frozen; the final play-throughs all used the same bot.
- Cost limit $0.22 per run (Agent A used $1.00); no run came close (max $0.047), so it did not shape the result.
- The harness still writes its own input analysis into `RUN_REPORT.md` after the run; the model never sees it.
