import typer
from agentic.secrets import agentic_secrets as secrets

app = typer.Typer()

@app.command()
def list():
    """List all secrets."""
    typer.echo(secrets.list_secrets())

@app.command()
def set(name: str, value: str):
    """Set a secret."""
    typer.echo(secrets.set_secret(name, value))

@app.command()
def get(name: str):
    """Get a secret."""
    typer.echo(secrets.get_secret(name))

if __name__ == "__main__":
    app()
