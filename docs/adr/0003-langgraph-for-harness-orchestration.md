# LangGraph for the harness's own orchestration

The harness runs its Planner, Attackers and Judge as a LangGraph graph rather than a hand-rolled asyncio loop. The Planner fans out to Attacker subgraphs with `Send`, and each Attacker is a loop subgraph with conditional edges for Checks and the Judge. Research (RESEARCH §04) recommended plain asyncio as lighter and simpler for a short-lived CI Run. We chose LangGraph anyway, so the maintainer gets deep experience with the framework, and because the project also serves as a portfolio piece (DISCOVERY Q1).

## Consequences

- `langgraph` (and transitively `langchain-core`) becomes a core dependency. Pin the minor version.
- Budget enforcement can't rely on TaskGroup cancellation. A shared Budget object must be checked in every node, and it must end the graph through a conditional edge.
- Result order from parallel `Send` branches is not guaranteed. The state reducer must sort Breaches by Objective so reports and Replay are deterministic.
- Checkpointing is optional, but it could later let a long Explore Run resume.
