import os
import pickle
import tempfile
import hashlib
from typing import Any, Callable, TypeVar, ParamSpec, Dict, List
from pydantic import BaseModel, Field

P = ParamSpec('P')
R = TypeVar('R')

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Query for web search.")

class Queries(BaseModel):
    queries: List[SearchQuery] = Field(
        description="List of search queries.",
    )

class Section(BaseModel):
    name: str = Field(
        description="Name for this section of the report.",
    )
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section.",
    )
    research: bool = Field(
        description="Whether to perform web research for this section of the report."
    )
    content: str = Field(
        description="The content of the section."
    )   

class Sections(BaseModel):
    sections: List[Section] = Field(
        description="Sections of the report.",
    )


def format_sections(sections: list[Section]) -> str:
    """ Format a list of sections into a string """
    formatted_str = ""
    for idx, section in enumerate(sections, 1):
        formatted_str += f"""
{'='*60}
Section {idx}: {section.name}
{'='*60}
Description:
{section.description}
Requires Research: 
{section.research}

Content:
{section.content if section.content else '[Not yet written]'}

"""
    return formatted_str

def cached_call(func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """
    Explicitly cache a function call's result to a file in the temp directory.
    
    Args:
        func: The function to call with caching
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function call, either from cache or fresh execution
    """
    # Create a unique cache key based on function name and arguments
    key_parts = [func.__name__]
    key_parts.extend([str(arg) for arg in args])
    key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    
    # Create a hash of the key parts to use as filename
    cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
    cache_path = os.path.join(tempfile.gettempdir(), f"cache_{cache_key}.pkl")
    
    # Try to load from cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                print(f"Cache hit: Loading result for {func.__name__} from {cache_path}")
                return pickle.load(f)
        except (pickle.PickleError, IOError) as e:
            print(f"Cache error: {e}. Will recompute result.")
    
    # Cache miss or error - call the function
    result = func(*args, **kwargs)
    
    # Save result to cache
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(result, f)
            print(f"Cached result for {func.__name__} at {cache_path}")
    except (pickle.PickleError, IOError) as e:
        print(f"Failed to cache result: {e}")
        
    return result