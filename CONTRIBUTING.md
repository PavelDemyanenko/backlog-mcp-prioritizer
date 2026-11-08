# Contributing

Issues and pull requests are welcome.

## Before you open a PR

```bash
mvn verify                                                         # needs Docker (Testcontainers + WireMock)
python3 -I -m unittest discover -s skills/backlog-prioritization-engine/scripts
python3 -I -m unittest discover -s evals/golden
python3 -I evals/golden/build.py --check
```

If you change the Docker image: `mvn -DskipTests package && docker build -t backlog-mcp-prioritizer . && python3 e2e/docker_smoke.py backlog-mcp-prioritizer`.

If you change the skill or the calculator, run a live eval and attach its `report.md` to the PR
(costs LLM tokens, see [evals/golden](evals/golden/README.md)):
`python3 -I evals/golden/run_eval.py --agent claude --runs 3`.

## Ground rules

- **Read-only and no raw descriptions.** The server never writes to YouTrack and never returns issue descriptions.
- **Deterministic rules.** Anything that can be computed goes into `priority.py` with tests; prompts only ask for judgment.
- **Contract changes** update [docs/tools.md](docs/tools.md) and the E2E assertions in the same PR.
- **New rule or trade-off** → a short ADR in [docs/adr](docs/adr) (MADR format; the `adr-custodian` skill can draft it).
- **stdout is the MCP stream.** Nothing may print to it.
