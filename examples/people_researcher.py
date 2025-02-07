from typing import Callable, Any
import asyncio
from agentic.tools import LinkedinDataTool

from agentic import Agent, AgentRunner, PauseAgentResult


def invoke_async(async_func: Callable, *args, **kwargs) -> Any:
    return asyncio.run(async_func(*args, **kwargs))


linkedin = LinkedinDataTool()


def search_profiles(name: str, company: str = ""):
    """Searches for linkedin profiles."""
    return invoke_async(linkedin.linkedin_people_search, name=name, company=company)


def get_profile(url: str):
    return invoke_async(linkedin.get_linkedin_profile_info, url)


def get_human_input(request_message: str):
    return PauseAgentResult(request_message)


from agentic import Agent, PauseToolResult

people_researcher = Agent(
    name="Person Researcher",
    welcome="I am the People Researcher. Tell me who you want to know about.",
    instructions="""
You do research on people. Given a name and a company:
1. Search for matching profiles on linkedin.
2. If you find a single strong match, then prepare a background report on that person.
3. If you find multiple matches, then request human input. If the response
identifies a profile then go back to step 2.
If you are missing info, then seek clarification from the user.
""",
    tools=[
        search_profiles,
        get_human_input,
        Agent(
            name="Person Report Writer",
            instructions="""
        You will receive the URL to a linkedin profile. Retreive the profile and
        write a background report on the person, focusing on their career progression
        and current role.
        """,
            tools=[get_profile],
        ),
    ],
)

if __name__ == "__main__":
    AgentRunner(people_researcher).repl_loop()
