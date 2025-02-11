import typer
import os
import requests
from bs4 import BeautifulSoup
from rich.markdown import Markdown
from rich.console import Console
from typing import Optional

from .llm import llm_generate, LLMUsage, CLAUDE_DEFAULT_MODEL, GPT_DEFAULT_MODEL
from .file_cache import file_cache
from .colors import Colors

from agentic.agentic_secrets import agentic_secrets as secrets
from agentic.settings import settings


# Create a state class to hold global options
class State:
    def __init__(self):
        self.no_cache: bool = False


state = State()

# Create the app with a callback
app = typer.Typer()


def quiet_log(*args):
    print(Colors.DARK_GRAY + " ".join(map(str, args)) + Colors.ENDC)


# Add the callback to process global options
@app.callback()
def main(
    no_cache: bool = typer.Option(
        False, "--nocache", help="Disable caching for all commands"
    )
):
    """
    Agentic CLI with various commands for managing secrets and running services.
    """
    state.no_cache = no_cache


@app.command()
def list():
    """List all settings."""
    typer.echo("\n".join(sorted(settings.list_settings())))


@app.command()
def list_secrets():
    """List all secrets."""
    typer.echo("\n".join(sorted(secrets.list_secrets())))


@app.command()
def set(name: str, value: str):
    """Set a setting value."""
    typer.echo(settings.set(name, value))


@app.command()
def set_secret(name: str, value: str):
    """Set a secret."""
    typer.echo(secrets.set_secret(name, value))


@app.command()
def get(name: str):
    """Get a setting."""
    typer.echo(settings.get(name))


@app.command()
def get_secret(name: str):
    """Get a secret."""
    typer.echo(secrets.get_secret(name))


@app.command()
def delete(name: str):
    """Delete a setting."""
    typer.echo(settings.delete_setting(name))


@app.command()
def delete_secret(name: str):
    """Delete a secret."""
    typer.echo(secrets.delete_secret(name))


@app.command()
def ollama():
    """List the latest popular models from Ollama. Use "ollama pull <model> to download."""
    # Download the web page from ollama.com/library
    url = "https://ollama.com/library"
    response = requests.get(url)
    html_content = response.content

    def extract_models(html_page: bytes) -> tuple[str, LLMUsage]:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        usage = LLMUsage()
        response = llm_generate(
            """
Get the names and descriptions from the top 20 models in this list:
{{models}}
            """,
            models=(soup.get_text() or ""),
            usage=usage,
        )
        return response, usage

    typer.echo("Current popular Ollama models:")

    usage: LLMUsage | None = None
    if state.no_cache:
        listing, usage = extract_models(html_content)
    else:
        listing = file_cache.get(
            url, ttl_seconds=60 * 12, fetch_fn=lambda: extract_models(html_content)
        )

    console = Console()
    md = Markdown(listing or "")
    console.print(md)
    if usage:
        quiet_log(usage)


@app.command()
def ui():
    """Runs the agentic UI"""
    os.execvp("streamlit", ["streamlit", "run", "src/agentic/ui/chat.py"])


@app.command()
def claude(prompt: str):
    """Runs a completion with Anthropic's Claude sonnet model"""
    usage = LLMUsage()
    typer.echo(llm_generate(prompt, model=CLAUDE_DEFAULT_MODEL, usage=usage))
    quiet_log(usage)


@app.command()
def gpt(
    prompt: str,
    model: str = typer.Option(
        GPT_DEFAULT_MODEL, "--model", help="The model to use for completion"
    ),
):
    """Runs a completion with OpenAI's GPT-4o-mini model"""
    usage = LLMUsage()
    typer.echo(llm_generate(prompt, model=model, usage=usage))
    quiet_log(usage)


@app.command()
def models():
    typer.echo(
        "Visit https://docs.litellm.ai/docs/providers for the full list of models"
    )
    typer.echo(
        """
Popular models:
    openai/o1-mini
    openai/o1-preview
    openai/gpt-4o
    openai/gpt-4o-mini
    anthropic/claude-3-5-sonnet-20240620
    anthropic/claude-3-5-haiku-20241022
     """
    )


@app.command()
def repl(filename: str = typer.Argument(default="", show_default=False)):
    """Runs the agentic REPL"""
    cmd = ["python", "src/agentic/repl.py"]
    if filename:
        cmd.append(filename)
    os.execvp("python", cmd)


if __name__ == "__main__":
    app()
