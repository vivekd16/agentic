Your agent automatically exposes a **REST API** that you can use to interact with it
programmatically. The AgentRunner runs a _FastAPI_ service that exposes an interface to your agent.

Some of the main endpoints include:

    POST /login             Generate a JWT to access the other endpoints
    POST /runs              Start a new run (session) for your agent
    GET /stream/<run_id>    Stream events (SSE) from a run until the end of a turn


