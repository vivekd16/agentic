from agentic import ActorAgent, AgentRunner


def main():
    agent = ActorAgent(
        name="MyAgent",
        instructions="You are a helpful assistant.",
        welcome="Please echo some random text for me, using the provided function.",
        model="gpt-4o-mini",
    )
    agent.connect_mcp_sync("uv", ["run", "python", "examples/mcp_echo.py"])

    AgentRunner(agent).repl_loop()


if __name__ == "__main__":
    main()
