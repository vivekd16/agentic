from agentic.tools.browser_use import BrowserUseTool

from agentic.common import Agent, AgentRunner

agent = Agent(
    name="Agentic Operator",
    welcome="Welcome the Operator Agent. What task would you like me to perform?",
    instructions="You have a browsing tool function which can browse websites and take actions.",
    model="gemini/gemini-2.0-flash",
    tools=[
        BrowserUseTool(
            chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            model="gemini/gemini-2.0-flash",
        ),
    ],
)

if __name__ == "__main__":
    AgentRunner(agent).repl_loop()
