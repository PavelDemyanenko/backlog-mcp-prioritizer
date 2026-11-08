# YouTrack sandbox (real API, local only)

WireMock fixtures are hand-written. This sandbox runs a real YouTrack (JetBrains image, free tier),
seeds it with the Golden Dataset and runs the same contract (`GoldenBacklogContract`) against it.

```bash
docker compose -f docker-compose.e2e.yml --profile sandbox up -d --wait youtrack   # ~45 s, ~2 GB RAM
python3 -I e2e/youtrack-sandbox/seed.py            # project GOLD, 24 backlog + 9 In Progress, token -> .env
source e2e/youtrack-sandbox/.env
mvn verify -Dit.test=YouTrackSandboxIT -Dtest=NoSuchTest -Dsurefire.failIfNoSpecifiedTests=false
docker compose -f docker-compose.e2e.yml --profile sandbox stop                    # keeps data
```

- UI: http://127.0.0.1:8088 (admin / admin). Bound to 127.0.0.1 only; synthetic data only.
- `seed.py --reset` deletes and recreates project GOLD.
- To point the MCP server or an agent at it: `YOUTRACK_BASE_URL=$YOUTRACK_SANDBOX_URL YOUTRACK_TOKEN=$YOUTRACK_SANDBOX_TOKEN`.
- Not part of CI: the image is ~2 GB and starts in about 45 s.
- After `docker compose -f docker-compose.e2e.yml down` (which removes the network), start the
  sandbox with `--force-recreate`; data and the token survive in the volumes.
- Run the agent evals against it: `run_eval.py --agent claude --youtrack-url "$YOUTRACK_SANDBOX_URL"`.

Known differences from the WireMock fixtures: real responses include every project field
(Assignee, Fix versions, …) and "Story points" is a float field here (`5.0`).
