# toolbreach

Red-team your own authorized tool-using LLM agents in CI. toolbreach owns the
**tool channel**: it instruments your agent's tools in-process, injects through
tool returns, detects breaches at the tool boundary, and turns every confirmed
finding into a regression test that Replay enforces on each PR.

Status: pre-alpha, under active construction. See [PLAN.md](PLAN.md).

## Responsible use

A Run only starts against a target you have declared an **Authorization** for —
one you own or are explicitly permitted to test. See DISCOVERY.md Q5.

## License

Apache-2.0.
# agent-redteam
