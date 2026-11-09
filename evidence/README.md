# Evidence — Agent B study runs (architecture only)

Everything recorded for the three study runs `b1`, `b2`, `b3` of Agent B (frozen at tag `agent-b-frozen`,
switch *record deviations* OFF, model `deepseek-v4-pro`, 2026-11-09, off-peak), plus the same play-through of
Agent A's final game (`a_run9`) for comparison. Results: [`../docs/STUDY_RESULTS.md`](../docs/STUDY_RESULTS.md).
Automatic conformance table: [`CONFORMANCE.md`](CONFORMANCE.md).

Nothing in the generated code was edited by hand. The generated projects are in
`examples/arch_only_b1`, `examples/arch_only_b2`, `examples/arch_only_b3` (each with `agent_run/transcript.jsonl` =
every request and response, `RUN_REPORT.md`, `plan.md`, `spec.json` and the original inputs).

## Per run (`b1/`, `b2/`, `b3/`)

| File | What it is |
|---|---|
| `agent_gui.mp4` | Screen video of the agent's own GUI during the whole run (2 frames/s) |
| `agent_gui_NNN_*.png` | Screenshots: settings before start, every phase (plan, implement, verify, report), every 30 s, the end, the result dialog |
| `agent_events.jsonl` | Every GUI event with a timestamp: tool calls, tool results, todos, token usage and cost, verify reports |
| `agent_gui_log.txt`, `agent_gui_todos.txt`, `agent_gui_report.txt` | The GUI's Log, Todos and Report tabs at the end of the run |
| `game_play.mp4` + `game_play.srt` | Video of the generated game being played by the bot; the `.srt` subtitle file (open it with the video, e.g. in VLC) shows every action and dialog |
| `game_step_NNN_screen.png` | Screenshot of every screen the bot saw (one per step) |
| `game_play_log.jsonl` | Per step: the texts and buttons on screen, what the bot did, every message box, any Tk callback error |
| `game_play_summary.json` | Steps, distinct screens, callback errors, dialogs |
| `game_play_setup.json` | Settings of the play-through (login data the bot found in the generated README) |
| `game_play_stdout.txt`, `game_play_stacks.txt` | Console output of the game; stack dumps (only used to debug the bot) |

`a_run9/` has the same `game_*` files for Agent A's final game (`examples/space_fractions_run9_final`).

## How the recordings were made (`scripts/evidence/`)

- `record_agent_run.py` starts the agent's GUI, fills in the settings (output folder, $0.22 limit, 80 requests,
  switch OFF), presses *Generate* and answers the paid-run confirmation with *yes* (logged). The API key is not
  typed into the GUI; it comes from `.env`, so it never appears in a video or screenshot.
- `play_game.py` plays a generated app with a **generic bot** that knows nothing about the app: every 1.8 s it looks
  at the widgets on screen and does one thing a user could do (type into an empty field, pick a radio button,
  select the first row of a list, click a button / clickable label / canvas, press Space when the screen listens for
  keys), preferring things it has not tried yet. It answers simple fraction tasks it can read on screen, uses login
  data written in the generated README, answers message boxes with OK / Yes, and plays on a temporary **copy** of
  the project (its database never touches the generated folder or the user's home folder). 80 steps or 300 s per
  game, the same for every game.
- `winrec.py` records a window with Windows `PrintWindow` and ffmpeg (works when other windows cover it).
- `conformance.py` writes `CONFORMANCE.md`; `balance.py` prints the DeepSeek balance (uses no tokens).

The bot was developed on Agent A's game and on b1 (b1's intro only reacts to a key press, see the results), then
frozen; all four final play-throughs (`b1`, `b2`, `b3`, `a_run9`) use the same final bot. The agent itself was not
changed.
