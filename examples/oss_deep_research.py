# Our version of the LangChain "Deep Research" agent, which is itself a version of
# the OpenAI "Deep Researcher".
# This code was converted from: https://github.com/langchain-ai/open_deep_research. All
# credit to LangChain for the original.

import asyncio
from typing import Generator
from pprint import pprint
from typing import Any, Generator

from agentic.common import Agent, AgentRunner
from agentic.actor_agents import RayFacadeAgent
from agentic.events import Prompt

from agentic.agentic_secrets import agentic_secrets
from agentic.models import GPT_4O_MINI, CLAUDE, GPT_4O
from agentic.events import Event, FinishCompletion, ChatOutput
from agentic.tools.tavily_search_tool import TavilySearchTool

from oss_deep_util import cached_call, Queries, Sections, Section, format_sections

PLANNER_MODEL = GPT_4O_MINI
WRITER_MODEL = GPT_4O_MINI

class WorkflowAgent(RayFacadeAgent):
    def __init__(self, name: str="OSS Deep Research", model: str=GPT_4O_MINI):
        super().__init__(
            name, 
            welcome="I am the OSS Deep Research agent. Please provide me with a topic to research.",
            model=model,
        )
        self.tavily_tool = TavilySearchTool(api_key=agentic_secrets.get_required_secret("TAVILY_API_KEY"))
        self.add_tool(self.tavily_tool)
        
        # Generates web queries to popular initial context from which to generate the report plan
        self.query_planner = Agent(
            name="Report Query Planner",
            instructions="{{REPORT_QUERY_PLANNER}}",
            model=PLANNER_MODEL,
            result_model=Queries
        )

        # Generates the report plan, takes init query results as input
        self.section_planner = Agent(
            name="Section Planner",
            instructions="{{REPORT_SECTION_PLANNER}}",
            model=PLANNER_MODEL,
            result_model=Sections
        )
        
        # Generates web queries to gather content for each section
        self.section_query_planner = Agent(
            name="Section Query Planner",
            instructions="{{SECTION_QUERY_PLANNER}}",
            model=WRITER_MODEL,
            result_model=Queries
        )
        
        # Writes the section content
        self.section_writer = Agent(
            name="Section Writer",
            instructions="{{SECTION_WRITER}}",
            model=WRITER_MODEL
        )

        # Revises each section after the full report draft is written
        self.final_section_writer = Agent(
            name="Final Section Writer",
            instructions="{{FINAL_SECTION_WRITER}}",
            model=WRITER_MODEL
        )

    def process_section(self, section: Section, report_context: str = None) -> Generator:
        """Handle the complete processing of a single section"""
        # Generates web queries to gather content for each section
        queries = yield from self.section_query_planner.final_result(
            "Generate search queries on the provided topic.",
            request_context={"section_topic": section.description}
        )

        # Get web content
        web_context = self.query_web_content(queries)

        # Write the section
        section.content = yield from self.section_writer.final_result(
            "Generate a report section based on the provided sources.",
            request_context={
                "section_title": section.name,
                "section_topic": section.description,
                "section_content": section.content,
                "web_context": web_context
            }
        )

    def next_turn(
        self,
        request: str|Prompt,
        request_context: dict = {},
        request_id: str = None,
        continue_result: dict = {},
        debug = "",
    ) -> Generator[Event, Any, Any]:
        """Main workflow orchestration"""

        topic = request.payload if isinstance(request, Prompt) else request
        
        # Initial research queries
        queries = yield from self.query_planner.final_result(
            "Generate search queries that will help with planning the sections of the report.",
            request_context={"topic": topic}
        )
        yield ChatOutput(self.query_planner.name, {"content": f"Initial research queries: {queries}"})

        # Get initial web content
        content = cached_call(self.query_web_content, queries)

        # Plan the report sections
        sections = yield from self.section_planner.final_result(
            """Generate the sections of the report. Your response must include a 'sections' field containing a list of sections.
            Each section must have: name, description, plan, research, and content fields.""",
            request_context={
                "web_context": content, 
                "topic": topic
            }
        )

        # Process each section initially
        for section in sections.sections:
            yield from self.process_section(section)

        # Format complete report
        draft_report = format_sections(sections.sections)

        # Rewrite the report sections with hindsight of the entire content of the report
        finals = []
        for section in sections.sections:
            report_section = yield from self.final_section_writer.final_result(
                "Generate a report section based on the provided sources.",
                {
                    "section_title": section.name,
                    "section_topic": section.description, 
                    "report_context": draft_report,
                    "section_content": section.content
                },
            )
            finals.append(report_section)

        return "\n".join(finals)

    def query_web_content(self, queries: Queries) -> str:
        async def _query_web_content(queries: Queries) -> str:
            all_results = []
            for query in queries.queries:
                res = await self.tavily_tool.perform_web_search(query.search_query, include_content=True)
                content = self.tavily_tool._deduplicate_and_format_sources(res, 10000)
                all_results.append(content)
            return "\n".join(all_results)
        return asyncio.run(_query_web_content(queries))



if __name__ == "__main__":
    agent = WorkflowAgent(name="OSS Deep Research", model=GPT_4O_MINI)
    AgentRunner(agent).repl_loop()
