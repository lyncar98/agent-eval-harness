# Contributing

Thanks for considering a contribution. This project is a companion to an article
on production-grade agent evaluation; the goal is clarity and correctness over
breadth.

## Ground rules

- **Tests must pass offline.** CI runs with no API key. New model-grader behavior
  must be testable against the deterministic stub judge (`HeuristicJudge`).
- **Never commit secrets.** `.env` is git-ignored. Don't add keys to code, tests,
  or fixtures. See [`SECURITY.md`](./SECURITY.md).
- **Keep graders pure.** Every grader is a configured callable
  `(GraderContext) -> {name, family, score, passed, reason}`. No hidden I/O in
  code graders.
- **Outcome over trajectory.** New trajectory checks should default to
  diagnostic (`gating=false`) unless order genuinely is the policy.

## Dev setup

```bash
python -m pip install -e ".[dev]"
pytest -q
python -m agent_eval.examples.quickstart
```

To exercise a live judge:

```bash
pip install -e ".[anthropic]"
echo 'claude_api_key=sk-ant-...' > .env       # git-ignored
python -m agent_eval.examples.quickstart --judge anthropic
```

## Adding a grader

1. Add a factory in `src/agent_eval/graders/code.py` or `model.py`, decorated
   with `@register("name", "family", online_safe=...)`.
2. Re-export it from `src/agent_eval/graders/__init__.py`.
3. Add a test in `tests/`. If it can run on a bare chat-turn payload, mark it
   `online_safe` and confirm it's in `ONLINE_SAFE`.

## Discussions

If you'd build the trajectory-vs-outcome trade-off or the online sample rate
differently, open a Discussion. There's no good public benchmark for production
agent reliability yet — sharing what we ship is how the field improves.
