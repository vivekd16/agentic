from agentic import Agent, demo_loop
from agentic.tools.text_to_speech_tool import TextToSpeechTool
from agentic.tools.auth_rest_api_tool import AuthorizedRESTAPITool

producer = Agent(
    name="Podcast Producer",
    welcome="I am a podcast producer. I can produce a daily news podcast.",
    instructions="""
1. Call the AI News Reporter to get the daily news report.
2. Now convert the report into speech, choosing one of the available voices at random.
3. now call the Transistor agent, ask it to create and then publish a new episode using the audio link and naming the episode "Latest AI news from <date>" and add the date.
4. Print the episode ID returned
""",    
    model="gpt-4o-mini",
    functions=[TextToSpeechTool()],
)
producer.add_child(
    name="AI News Reporter",
    instructions="{{PRODUCER}}",
    model="openai/gpt-4o",    
)
producer.add_child(
    name="Transistor",
    instructions="{{REPORTER}}",
    functions=[AuthorizedRESTAPITool()],
    memories=["Default show ID is 60214"],
)
if __file__ == "__main__":
    demo_loop(producer)
