# Grey-box testing with Instrumented Tools, not pure black-box

The harness needs a Target Profile (system prompt, tool schemas, Policy) and an in-process Python SDK that wraps the Target's tools, rather than attacking an opaque HTTP endpoint. Attacks on tool-using agents mostly arrive through untrusted tool output, and the most serious Breaches are tool calls. Both require observing and replacing tool I/O, which a black-box harness cannot do. In exchange, the Target owner has to add an integration step, and Targets that can't be instrumented only get chat-level attacks.
