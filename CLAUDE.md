# Claude Code

The rules for this repository are in AGENTS.md, shared with every other coding agent:

@AGENTS.md

In addition, when Claude Code leads a to-do, it follows `game/WORKFLOW.md`: it names the risk and writes the brief, starts the `researcher` and `coder` agents from `.claude/agents/` (the `reviewer` for risk medium and higher, the `tester` only when needed, S-205), and stops after three failed rounds of any loop to ask a person.
