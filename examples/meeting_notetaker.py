import asyncio
from typing import Any, Dict, List, Optional
from agentic.common import Agent, AgentRunner
from agentic.tools.meeting_tool import MeetingBaasTool

meeting_manager = Agent(
    name="Meeting Manage Agent",
    welcome="I am the Meeting Manager. I can help you join meetings, get transcripts, generate summaries and get info about meetings.",
    instructions="""  
            You help manage meetings. You can:  
            1. Join new meetings to record and transcribe them.  
            2. List existing meetings.  
            3. Check the status of meetings.  
            4. Retrieve detailed summaries and transcripts by calling the Meeting Summarizer.  
            5. Answer questions about meeting content.  

            When joining a meeting:  
            - Ask for the meeting URL if not provided.  
            - Join the meeting and track its status.  
            - Once complete, offer to generate a summary.  
            """,
    tools=[MeetingBaasTool()],
    model="openai/gpt-4o-mini"
)


if __name__ == "__main__":
    AgentRunner(meeting_manager).repl_loop()