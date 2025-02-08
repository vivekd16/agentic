# Agent Memory

_Memory_ for your agent is a large topic. Let's start with just "session history" because it
is the easiest thing to understand.

By default your agents have "persistent session memory", which just means that if you send
them multiple inputs, they will by default remember the message history across those
prompts:

```
    agent = Agent(...)
    runner = AgentRunner(agent)
    runner.run_sync("My name is Scott")
    > nice to meet you, Scott
    runner.run_sync("what is my name?")
    > your name is Scott
```

You can delete the previous history to "clear" a session with `reset_memory`.

```
    runner.reset_session();
    runner.run_sync("what is my name?")
    > sorry, I do not know your name. Can you tell me what it is?
```
