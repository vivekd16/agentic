import typer
import os
import requests
from bs4 import BeautifulSoup
from rich.markdown import Markdown
from rich.console import Console
from typing import Optional, List, Dict

from .file_cache import file_cache
from .colors import Colors

from agentic.agentic_secrets import agentic_secrets as secrets
from agentic.settings import settings


import shutil
from pathlib import Path
from importlib import resources
from typing import Optional
from rich.status import Status

from weaviate import WeaviateClient
from weaviate.embedded import EmbeddedOptions
from chonkie import SemanticChunker
from fastembed import TextEmbedding
import pypdf
import tempfile
from weaviate.classes.config import (
    DataType,
    Property,
    Configure,
    VectorDistances
)
import hashlib
from weaviate.classes.query import Filter

from agentic.utils.file_reader import read_file, get_last_path_component
from datetime import datetime

from agentic.utils.summarizer import generate_document_summary
from agentic.utils.fingerprint import generate_fingerprint

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
def list_settings():
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
    os.mkdir("evals")

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


@app.command()
def index_file(
    index_name: str,
    file_path: str,
    embedding_model: str = typer.Option(
        "BAAI/bge-small-en-v1.5",
        help="FastEmbed model name for text embedding"
    ),
    chunk_threshold: float = typer.Option(
        0.5,
        min=0.1,
        max=1.0,
        help="Semantic similarity threshold for chunking"
    ),
    chunk_delimiters: str = typer.Option(
        ". ,! ,? ,\n",
        help="Comma-separated delimiters for fallback chunk splitting"
    ),
    distance_metric: VectorDistances = typer.Option(
        VectorDistances.COSINE,
        help="Distance metric for vector comparison"
    )
):
    """Index a file using configurable Weaviate Embedded and chunking parameters"""
    console = Console()
    
    try:
        with Status("[bold green]Initializing Weaviate..."):
            client = WeaviateClient(
                embedded_options=EmbeddedOptions(
                    persistence_data_path=str(Path.home() / ".cache/weaviate"),
                    additional_env_vars={
                        "LOG_LEVEL": "error"
                    }
                )
            )
            client.connect()
            
        if not client.collections.exists(index_name):
            client.collections.create(
                name=index_name,
                properties=[
                    Property(name="document_id", data_type=DataType.TEXT,
                            index_filterable=True),  # For efficient deletion
                    Property(name="content", data_type=DataType.TEXT,
                            index_searchable=True,  # Enable BM25 text search
                            index_filterable=False),
                    Property(name="chunk_index", data_type=DataType.INT,
                            index_filterable=True,  # Enable numeric filtering
                            index_range_filter=True),  # Enable range queries
                    # Add metadata properties
                    Property(name="filename", data_type=DataType.TEXT,
                            index_filterable=True),
                    Property(name="timestamp", data_type=DataType.DATE,
                            index_filterable=True),
                    Property(name="mime_type", data_type=DataType.TEXT,
                            index_filterable=True),
                    Property(name="source_url", data_type=DataType.TEXT,
                            index_filterable=True),
                    Property(name="summary", data_type=DataType.TEXT,
                            index_searchable=True,
                            index_filterable=True),
                    Property(name="fingerprint", data_type=DataType.TEXT,
                            index_filterable=True),
                ],
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=distance_metric,
                    vector_cache_max_objects=10_000,
                    ef_construction=128,
                    max_connections=16,
                ),
                inverted_index_config=Configure.inverted_index(
                    bm25_b=0.75,          # BM25 ranking parameters
                    bm25_k1=1.2
                )
            )
            
        with Status("[bold green]Initializing FastEmbed..."):
            embed_model = TextEmbedding(model_name=embedding_model)
            
        with Status("[bold green]Initializing Chonkie..."):
            chunker = SemanticChunker(
                threshold=chunk_threshold,
                delim=chunk_delimiters.split(",")
            )
            
        with Status(f"[bold green]Processing {file_path}...", console=console):
            try:
                text, mime_type = read_file(str(file_path))
                is_url = file_path.startswith(("http://", "https://"))
                
                # Generate fingerprint from content
                fingerprint = generate_fingerprint(text)
                
                metadata = {
                    "filename": Path(file_path).name if not is_url else get_last_path_component(file_path),
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "mime_type": mime_type,
                    "source_url": file_path if is_url else "None"
                }
                
                document_id = hashlib.sha256(
                    metadata["filename"].encode()
                ).hexdigest()
                
            except Exception as e:
                console.print(f"Error reading file: {str(e)}", style="red")
                raise typer.Exit(1)
            
        collection = client.collections.get(index_name)
        # Check for existing fingerprint
        with Status("[bold green]Checking document version...", console=console):
            # Check for existing documents with same filename
            existing_docs = collection.query.fetch_objects(
                limit=1,
                filters=Filter.by_property("document_id").equal(document_id)
            )
            if existing_docs.objects:
                existing_fp = existing_docs.objects[0].properties["fingerprint"]
                
                if existing_fp == fingerprint:
                    # Case 1: Same filename, same content
                    console.print(f"[yellow]⏩ Document '{metadata['filename']}' unchanged[/yellow]")
                    client.close()
                    raise typer.Exit(1)
                else:
                    # Case 2: Same filename, changed content
                    console.print(f"[yellow]🔄 Updating changed document '{metadata['filename']}'[/yellow]")
                    collection.data.delete_many(
                        where=Filter.by_property("document_id").equal(document_id)
                    )
            else:
                # Check if content exists under different filename
                existing_content = collection.query.fetch_objects(
                    limit=1,
                    filters=Filter.by_property("fingerprint").equal(fingerprint)
                )
                if existing_content.objects:
                    # Case 3: New filename, same content
                    console.print(f"[yellow]⚠️ Content already exists under different filename[/yellow]")
                    client.close()
                    raise typer.Exit(1)

        with Status("[bold green]Generating document summary...", console=console):
            summary = generate_document_summary(
                text=text[:12000], 
                mime_type=mime_type,
                model=GPT_DEFAULT_MODEL
            )
        
        chunks = chunker(text)
        
        chunks_text = [chunk.text for chunk in chunks]
        if not chunks_text:
            raise ValueError("No text chunks generated from document")
        
        batch_size = 128  # Optimal for FastEmbed
        embeddings = []
        with Status("[bold green]Generating embeddings..."):
            for i in range(0, len(chunks_text), batch_size):
                batch = chunks_text[i:i+batch_size]
                embeddings.extend(list(embed_model.embed(batch)))  # Explicit conversion
        
        # Index in Weaviate with batch optimization
        with Status("[bold green]Indexing chunks..."), collection.batch.dynamic() as batch:
            for i, chunk in enumerate(chunks):
                vector = embeddings[i].tolist()
                batch.add_object(
                    properties={
                        "document_id": document_id,
                        "content": chunk.text,
                        "chunk_index": i,
                        # Add metadata
                        "filename": metadata["filename"],
                        "timestamp": metadata["timestamp"],
                        "mime_type": metadata["mime_type"],
                        "source_url": metadata["source_url"],
                        "summary": summary,
                        "fingerprint": fingerprint,
                    },
                    vector=vector
                )
                
        console.print(f"[bold green]✅ Indexed {len(chunks)} chunks in {index_name}")
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()
            if hasattr(client, '_embedded_db'):
                client._embedded_db.stop()
            tempfile.tempdir = None
            import gc; gc.collect()


if __name__ == "__main__":
    app()
