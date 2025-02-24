from agentic.actor_agents import RayFacadeAgent
from pydantic import BaseModel

class ResponseModel(BaseModel):
    response: str
    number: int

def test_response_model():
    
    agent = RayFacadeAgent(
        name="Test Agent",
        instructions="Make a joke about the input, and return a random number",
        model="gpt-4o-mini",
        result_model=ResponseModel,
    )
    result  = agent.grab_final_result("an old cat")
    assert isinstance(result, ResponseModel)
    print(result)
