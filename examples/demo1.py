import asyncio
from typing import Callable, Any

from agentic.tools import LinkedinDataTool
from agentic.tools import GoogleNewsTool

from agentic import Agent, AgentRunner, PauseForInputResult, RunContext

def invoke_async(async_func: Callable, *args, **kwargs) -> Any:
    return asyncio.run(async_func(*args, **kwargs))

linkedin = LinkedinDataTool()
def search_profiles(name: str, company: str = ""):
    """ Searches for linkedin profiles. """
    return invoke_async(linkedin.linkedin_people_search, name=name, company=company)

def get_profile(url: str):
    return invoke_async(linkedin.get_linkedin_profile_info, url)

gnt = GoogleNewsTool()

def query_news(topic: str):
    return gnt.query_news(topic)

def get_human_input(run_context: RunContext):
    if run_context.get("topic"):
        return run_context.get("topic")
    return PauseForInputResult({"topic" : "What is the news topic?"})

reporter = Agent(
    name="News Reporter",
    instructions=f"""
Call Google News to get headlines on the indicated news topic.
""",
    model="groq/llama-3.3-70b-versatile",
    tools=[query_news],
)
producer = Agent(
    name="Producer",
    welcome="I am the news producer. Tell me the topic, and I'll get the news from my reporter.",
    instructions="You are a news producer. Call the human to get the topic, then call the reporter with the indicated topic.",
    model="groq/llama-3.3-70b-versatile",
    tools=[get_human_input, reporter],
)

if __name__ == "__main__":
    AgentRunner(producer).repl_loop()
