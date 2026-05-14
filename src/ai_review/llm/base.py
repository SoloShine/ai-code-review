from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union


@dataclass
class LLMResponse:
    content: str
    success: bool
    error: Union[str, None] = None


class LLMProvider(ABC):
    @abstractmethod
    def review(self, prompt: str, timeout: int = 60) -> LLMResponse: ...

    @abstractmethod
    def test_connection(self) -> bool: ...