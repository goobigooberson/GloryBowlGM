# Main session hand-off (Oct 30, 2026)

For a fresh main (coordinator) session. Read `CLAUDE.md` and
`docs/current-state.md` first; this file only adds what the coordinator needs.

## Your role

- Blake's main session: you start side sessions for engine work (each in its
  own worktree), review their branches, merge them into `main`, and run the
  final checks. Blake makes design calls; you make technical ones.
- Merging overnight or while Blake is away needs his OK for that occasion.
- Keep this session's context small. When it gets large (roughly 300k
  tokens), write a new hand-off like this one and have Blake start a new
  session.

## Where things stand

- `main` at 5f06216 (+ the Oct 30 docs commit): all work is merged. The final
  checks passed on 5f06216: integration had 0 problems, screens ran 1,623
  steps with 0 problems, all must-be-zero measures were fine, and nothing
  changed beyond noise. The scoreboard baseline was saved there.
- Idle, already-merged side sessions whose worktrees can be removed (archive
  them only on Blake's yes): fa-commitment (`claude/fa-commitment-b89ef2`) and
  team-finances (`claude/team-finances-352ec9`). Before deleting a worktree,
  remove its data link first: `cmd /c rmdir <wt>\tools\data\nflverse`.
- Local uncommitted `.claude/launch.json` holds the layout session's test
  entries; leave it alone. Untracked `docs/for-gemini/` and its zip belong to
  Blake.

## Waiting on Blake

- AI player portraits: feasibility given, not started. Plan: local image model
  on his RTX 5080 (SDXL or FLUX.1 schnell, both commercial-friendly), prompts
  built from each player's appearance traits, a background queue, and a
  default face while images generate. Blake still has to pick the art style,
  whether players wear jerseys, and whether to install ComfyUI.

## Ready next (Blake picks the order)

- Finances: stadium projects (new stadiums, renovations), and tying owner
  profits to AI free-agency spending.
- Coaches benching players who play badly, and coach personalities.
- The known realism gaps listed in `current-state.md`.

## Working habits (to save usage)

- Side-session briefs: short, name the files and what done looks like, and
  "report once when done or blocked."
- Don't reply to routine notes. If a branch already contains the latest main
  and passed its checks, merge it without re-checking. Re-check only when a
  merge combines new work. Save one baseline per batch.
- Use subagents for one-off reading-heavy jobs.
