import pytest
from agentic import Agent, AgentRunner


def test_agent():
    agent = Agent(
        name="Basic Agent",
        welcome="I am a simple agent here to help.",
        instructions="You are a helpful assistant.",
        tools=[],
    )
    assert agent.name == "Basic Agent"
    assert agent.welcome == "I am a simple agent here to help."
    assert agent.instructions == "You are a helpful assistant."

    agent_runnner = AgentRunner(agent)
    response = agent_runnner.run_sync("please tell me hello")
    assert "hello" in response.lower(), response


def test_agent_as_tool():
    agent = Agent(
        name="Agent A",
        instructions="Print this 'I am agent 1'. \nThen call agent B",
        tools=[
            Agent(
                name="Agent B",
                instructions="Print 'I am agent 2'.",
            )
        ],
    )

    agent_runnner = AgentRunner(agent)
    response = agent_runnner.run_sync("run your instructions")
    assert "agent 2" in response.lower(), response


read_file_was_called: bool = False


def test_simple_tool_use():
    global read_file_was_called

    def read_file() -> str:
        """Reads the current file"""
        global read_file_was_called
        read_file_was_called = True
        return "Hello world, i am in a file."

    agent = Agent(
        name="Agent A",
        instructions="You are helpful assistant.",
        tools=[read_file],
    )

    agent_runnner = AgentRunner(agent)
    response = agent_runnner.run_sync("read the file")
    assert read_file_was_called, "Verify tool function was invoked"
    assert "world" in response.lower(), response
