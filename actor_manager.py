import ray
from ray import serve
import click
from starlette.requests import Request
from typing import Dict
import signal
import sys

# Store actor refs and their corresponding handlers
actor_registry: Dict[str, ray.actor.ActorHandle] = {}

# Flag for graceful shutdown
running = True

def signal_handler(signum, frame):
    global running
    print("\nShutting down...")
    running = False
    # Clean up all actors
    for actor_id in list(actor_registry.keys()):
        stop_actor(actor_id)
    sys.exit(0)

@ray.remote
class WorkerActor:
    def __init__(self, actor_id: str):
        self.actor_id = actor_id
        self.state = {}

    async def handle_request(self, method: str, data: dict):
        return f"Actor {self.actor_id} processed {method} request with data: {data}"

    def get_status(self):
        return f"Actor {self.actor_id} is running"

class DynamicHandler:
    def __init__(self, actor_ref: ray.actor.ActorHandle):
        self.actor = actor_ref

    async def __call__(self, request: Request):
        data = await request.json() if request.method in ["POST", "PUT"] else {}
        return await self.actor.handle_request.remote(request.method, data)

def create_endpoint(actor_id: str, actor_ref: ray.actor.ActorHandle):
    HandlerDeployment = serve.deployment(
        name=f"handler-{actor_id}",
    )(DynamicHandler)
    
    serve.run(
        HandlerDeployment.bind(actor_ref), 
        route_prefix=f"/{actor_id}",
    )
    return HandlerDeployment

@click.group()
def cli():
    """CLI group that ensures Ray is initialized before any command"""
    if len(sys.argv) > 1 and sys.argv[1] == 'serve-forever':
        # For serve-forever, start a new Ray instance
        ray.init()
        serve.start()
    else:
        # For other commands, connect to existing Ray instance
        try:
            ray.init(address='auto')
        except Exception as e:
            print("Error: Could not connect to Ray cluster. Is serve-forever running?")
            sys.exit(1)

@cli.command()
@click.argument('actor_id')
def start_actor(actor_id: str):
    """Start a new actor and create its HTTP endpoint"""
    if actor_id in actor_registry:
        print(f"Actor {actor_id} already exists")
        return

    actor_ref = WorkerActor.remote(actor_id)
    actor_registry[actor_id] = actor_ref
    handler = create_endpoint(actor_id, actor_ref)
    
    print(f"Started actor {actor_id} with endpoint /{actor_id}")
    print(f"Status: {ray.get(actor_ref.get_status.remote())}")
    #ray.get(handler.remote())

def handy_start_actor(actor_id: str):
    """Start a new actor and create its HTTP endpoint"""
    if actor_id in actor_registry:
        print(f"Actor {actor_id} already exists")
        return

    actor_ref = WorkerActor.remote(actor_id)
    actor_registry[actor_id] = actor_ref
    handler = create_endpoint(actor_id, actor_ref)
    
    print(f"Started actor {actor_id} with endpoint /{actor_id}")
    print(f"Status: {ray.get(actor_ref.get_status.remote())}")

@cli.command()
def list_actors():
    """List all running actors"""
    if not actor_registry:
        print("No actors running")
        return

    for actor_id, actor_ref in actor_registry.items():
        status = ray.get(actor_ref.get_status.remote())
        print(f"Actor {actor_id}: {status}")

def stop_actor(actor_id: str):
    """Stop an actor and remove its HTTP endpoint"""
    if actor_id not in actor_registry:
        print(f"Actor {actor_id} not found")
        return

    serve.delete(f"handler-{actor_id}")
    ray.kill(actor_registry[actor_id])
    del actor_registry[actor_id]
    print(f"Stopped actor {actor_id} and removed its endpoint")

@cli.command()
@click.argument('actor_id')
def stop_actor_command(actor_id: str):
    """CLI command to stop an actor"""
    stop_actor(actor_id)

@cli.command()
def serve_forever():
    """Keep the server running and handle actors"""
    print("Server running. Press Ctrl+C to stop.")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    handy_start_actor("worker-1")
    # Keep running until stopped
    while running:
        signal.pause()

if __name__ == "__main__":
    cli()