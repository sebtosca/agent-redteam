# Separate Replay and Explore modes

Runs come in two modes. Replay re-runs the saved Regression Cases and gates CI on every PR. Explore searches for new Breaches on a schedule or on demand. Explore is slow, costly and nondeterministic, so it can't gate a PR. A pure regression suite never finds anything new. Splitting the two keeps CI fast and repeatable while discovery keeps running. The link between them is that Explore proposes Regression Cases and Replay enforces them.
