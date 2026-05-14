from typing import Optional
import httpx
from .base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434",
                 timeout: int = 120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout

    def review(self, prompt: str, timeout: int = 60) -> LLMResponse:
        try:
            timeout_config = httpx.Timeout(timeout, connect=timeout // 2)

            with httpx.Client(timeout=timeout_config) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()

                result = response.json()

                if "response" not in result:
                    return LLMResponse(
                        content="",
                        success=False,
                        error="Response missing 'response' field"
                    )

                return LLMResponse(
                    content=result["response"],
                    success=True
                )

        except httpx.TimeoutException:
            return LLMResponse(
                content="",
                success=False,
                error=f"Request timed out after {timeout} seconds"
            )
        except httpx.HTTPStatusError as e:
            return LLMResponse(
                content="",
                success=False,
                error=f"HTTP error {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            return LLMResponse(
                content="",
                success=False,
                error=f"Request error: {str(e)}"
            )
        except Exception as e:
            return LLMResponse(
                content="",
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

    def test_connection(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(float(self.timeout_seconds), connect=15.0)) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()

                tags = response.json()
                if "models" not in tags:
                    return False

                # Check if our model exists in the available models
                model_names = [model["name"] for model in tags["models"]]

                return self.model in model_names

        except httpx.RequestError:
            return False
        except Exception:
            return False