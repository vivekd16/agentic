import typer
from agentic.secrets import agentic_secrets as secrets
import os

app = typer.Typer()

@app.command()
def list():
    """List all secrets."""
    typer.echo("\n".join(sorted(secrets.list_secrets())))

@app.command()
def set(name: str, value: str):
    """Set a secret."""
    typer.echo(secrets.set_secret(name, value))

@app.command()
def get(name: str):
    """Get a secret."""
    typer.echo(secrets.get_secret(name))

@app.command()
def delete(name: str):
    """Delete a secret."""
    typer.echo(secrets.delete_secret(name))

if __name__ == "__main__":
    app()

@app.command()
def ui():
    """ Runs the agentic UI """
    os.execvp("streamlit", ["streamlit", "run", "src/agentic/ui/chat.py"])
