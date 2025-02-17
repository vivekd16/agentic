from pathlib import Path
from datetime import datetime
import hashlib
from typing import Dict, Any

from weaviate import WeaviateClient
from weaviate.embedded import EmbeddedOptions
from weaviate.classes.config import (
    DataType,
    Property,
    Configure,
    VectorDistances
)
from weaviate.classes.query import Filter
from chonkie import SemanticChunker
from fastembed import TextEmbedding

from agentic.utils.file_reader import get_last_path_component
from agentic.utils.fingerprint import generate_fingerprint

def init_weaviate() -> WeaviateClient:
    """Initialize and return Weaviate client"""
    client = WeaviateClient(
        embedded_options=EmbeddedOptions(
            persistence_data_path=str(Path.home() / ".cache/weaviate"),
            additional_env_vars={"LOG_LEVEL": "error"}
        )
    )
    client.connect()
    return client

def create_collection(
    client: WeaviateClient,
    index_name: str,
    distance_metric: VectorDistances = VectorDistances.COSINE
) -> None:
    """Create Weaviate collection with standard schema"""
    if not client.collections.exists(index_name):
        client.collections.create(
            name=index_name,
            properties=[
                Property(name="document_id", data_type=DataType.TEXT,
                        index_filterable=True),
                Property(name="content", data_type=DataType.TEXT,
                        index_searchable=True,
                        index_filterable=False),
                Property(name="chunk_index", data_type=DataType.INT,
                        index_filterable=True,
                        index_range_filter=True),
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
                bm25_b=0.75,
                bm25_k1=1.2
            )
        )

def prepare_document_metadata(
    file_path: str,
    text: str,
    mime_type: str,
    model: str
) -> Dict[str, Any]:
    """Prepare document metadata including fingerprint and summary"""
    is_url = file_path.startswith(("http://", "https://"))
    fingerprint = generate_fingerprint(text)
    
    metadata = {
        "filename": Path(file_path).name if not is_url else get_last_path_component(file_path),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mime_type": mime_type,
        "source_url": file_path if is_url else "None",
        "fingerprint": fingerprint
    }
    
    # Generate document ID from filename
    metadata["document_id"] = hashlib.sha256(
        metadata["filename"].encode()
    ).hexdigest()
    
    return metadata

def check_document_exists(
    collection: Any,
    document_id: str,
    fingerprint: str
) -> tuple[bool, str]:
    """Check if document exists and return status"""
    existing_docs = collection.query.fetch_objects(
        limit=1,
        filters=Filter.by_property("document_id").equal(document_id)
    )
    
    if existing_docs.objects:
        existing_fp = existing_docs.objects[0].properties["fingerprint"]
        if existing_fp == fingerprint:
            return True, "unchanged"
        return True, "changed"
    
    existing_content = collection.query.fetch_objects(
        limit=1,
        filters=Filter.by_property("fingerprint").equal(fingerprint)
    )
    if existing_content.objects:
        return True, "duplicate"
        
    return False, "new"

def init_embedding_model(model_name: str) -> TextEmbedding:
    """Initialize the embedding model"""
    return TextEmbedding(model_name=model_name)

def init_chunker(threshold: float, delimiters: str) -> SemanticChunker:
    """Initialize the semantic chunker"""
    return SemanticChunker(
        threshold=threshold,
        delim=delimiters.split(",")
    )

def delete_document_from_index(
    collection: Any,
    document_id: str,
    filename: str
) -> int:
    """Delete document and its chunks from index, return number of deleted chunks"""
    result = collection.data.delete_many(
        where=Filter.by_property("document_id").equal(document_id)
    )
    return result.successful

def check_document_in_index(
    collection: Any,
    document_id: str
) -> bool:
    """Check if document exists in index"""
    existing = collection.query.fetch_objects(
        limit=1,
        filters=Filter.by_property("document_id").equal(document_id)
    )
    return bool(existing.objects)

def get_document_id_from_path(file_path: str) -> tuple[str, str]:
    """Generate document ID from file path, return (document_id, filename)"""
    is_url = file_path.startswith(("http://", "https://"))
    filename = Path(file_path).name if not is_url else get_last_path_component(file_path)
    document_id = hashlib.sha256(filename.encode()).hexdigest()
    return document_id, filename 