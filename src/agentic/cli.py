import typer
import os
import requests
from bs4 import BeautifulSoup
from rich.markdown import Markdown
from rich.console import Console
from typing import Optional, List

from .file_cache import file_cache
from .colors import Colors

from agentic.agentic_secrets import agentic_secrets as secrets
from agentic.settings import settings


import shutil
from pathlib import Path
from importlib import resources
from typing import Optional
from rich.status import Status

GPT_DEFAULT_MODEL = "openai/gpt-4o-mini"


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
def get_all_secrets():
    """Get all secrets."""
    typer.echo(secrets.get_all_secrets())


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
    from .llm import llm_generate, LLMUsage, CLAUDE_DEFAULT_MODEL, GPT_DEFAULT_MODEL

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
    from .llm import llm_generate, LLMUsage, CLAUDE_DEFAULT_MODEL, GPT_DEFAULT_MODEL

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
    from .llm import llm_generate, LLMUsage, CLAUDE_DEFAULT_MODEL, GPT_DEFAULT_MODEL

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


def copy_examples(src_path: Path, dest_path: Path, console: Console) -> None:
    """Copy example files from source to destination, maintaining directory structure."""
    try:
        if not dest_path.exists():
            dest_path.mkdir(parents=True)

        # Copy all files and directories
        for item in src_path.iterdir():
            target = dest_path / item.name

            if item.is_file():
                shutil.copy2(item, target)
                console.print(f"✓ Copied: {item.name}", style="green")
            elif item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
                console.print(f"✓ Copied directory: {item.name}", style="green")

    except Exception as e:
        console.print(f"Error copying examples: {str(e)}", style="red")
        raise typer.Exit(1)


@app.command()
def init(
    path: str = typer.Argument(
        ".", help="Directory to initial your project (defaults to current directory)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files in the destination directory",
    ),
):
    """Initialize a new project by copying example files from the package."""
    console = Console()
    dest_path = Path(path + "/examples").resolve()
    os.mkdir("agents")
    os.mkdir("tools")
    os.mkdir("tests")
    os.mkdir("runtime")

    # Check if destination exists and is not empty
    if dest_path.exists() and any(dest_path.iterdir()) and not force:
        console.print(
            "⚠️  Destination directory is not empty. Use --force to overwrite existing files.",
            style="yellow",
        )
        raise typer.Exit(1)

    with Status("[bold green]Copying example files...", console=console):
        try:
            # Get the package's examples directory using importlib.resources
            # Replace 'your_package_name' with your actual package name
            with resources.path("agentic_examples", "") as examples_path:
                copy_examples(examples_path, dest_path, console)

            console.print("\n✨ Examples copied successfully!", style="bold green")
            console.print(f"📁 Location: {dest_path}", style="blue")

        except ModuleNotFoundError:
            console.print(
                "Error: Could not find examples directory in package.", style="red"
            )
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"Error initializing project: {str(e)}", style="red")
            raise typer.Exit(1)


# make a "run" command which executes a shell with all the args
@app.command()
def run(args: List[str]):
    """Copies secrets into the Environment and Runs a shell command"""
    secrets.copy_secrets_to_env()
    os.execvp("sh", ["sh", "-c", " ".join(args)])


if __name__ == "__main__":
    app()
