from abc import ABC, abstractmethod
from typing import Callable


class BaseAgenticTool(ABC):
    """Base class for all Agentic tools."""

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def get_tools(self) -> list[Callable]:
        """Forward method that should be implemented by subclasses."""
        pass
