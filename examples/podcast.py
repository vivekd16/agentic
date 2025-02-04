from agentic import Agent, demo_loop
from agentic.tools.text_to_speech_tool import TextToSpeechTool
from agentic.tools.auth_rest_api_tool import AuthorizedRESTAPITool

producer = Agent(
    name="Podcast Producer",
    welcome="I am a podcast producer. I can produce a daily news podcast.",
    instructions="{{PRODUCER}}",
    model="gpt-4o-mini",
    functions=[TextToSpeechTool()],
)
producer.add_child(
    name="AI News Reporter",
    instructions="{{REPORTER}}",
    model="openai/gpt-4o",    
)
producer.add_child(
    name="Transistor",
    instructions="{{TRANSITOR}}",
    functions=[AuthorizedRESTAPITool()],
    memories=["Default show ID is 60214"],
)
if __file__ == "__main__":
    demo_loop(producer)
