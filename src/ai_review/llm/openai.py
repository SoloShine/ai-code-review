from typing import Optional, Dict, Any
import httpx
import os
from .base import LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: str = "gpt-3.5-turbo", api_key_env: str = "OPENAI_API_KEY",
                 base_url: str = "https://api.openai.com/v1", timeout: int = 60,
                 max_tokens: int = 8000):
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout
        self.max_tokens = max_tokens

    def _get_chat_url(self) -> str:
        """Build the chat completions URL from base_url."""
        base = self.base_url
        # If base_url already ends with /v1 or /v4 etc, don't add /v1 again
        if base.endswith(("/v1", "/v4", "/v3")):
            return f"{base}/chat/completions"
        else:
            return f"{base}/v1/chat/completions"

    def review(self, prompt: str, timeout: int = 60) -> LLMResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            return LLMResponse(
                content="",
                success=False,
                error=f"API key not found in environment variable: {self.api_key_env}"
            )

        try:
            timeout_config = httpx.Timeout(float(timeout), connect=float(timeout // 2))

            with httpx.Client(timeout=timeout_config) as client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                response = client.post(
                    self._get_chat_url(),
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": 0.7
                    }
                )
                response.raise_for_status()

                result = response.json()

                if "choices" not in result or len(result["choices"]) == 0:
                    return LLMResponse(
                        content="",
                        success=False,
                        error="Response missing 'choices' field"
                    )

                choice = result["choices"][0]
                if "message" not in choice or "content" not in choice["message"]:
                    return LLMResponse(
                        content="",
                        success=False,
                        error="Response message structure is invalid"
                    )

                return LLMResponse(
                    content=choice["message"]["content"],
                    success=True
                )

        except httpx.TimeoutException:
            return LLMResponse(
                content="",
                success=False,
                error=f"Request timed out after {timeout} seconds"
            )
        except httpx.HTTPStatusError as e:
            error_msg = e.response.text
            if "error" in e.response.json():
                error_msg = e.response.json()["error"]["message"]
            return LLMResponse(
                content="",
                success=False,
                error=f"HTTP error {e.response.status_code}: {error_msg}"
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
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            return False

        try:
            with httpx.Client(timeout=httpx.Timeout(float(self.timeout_seconds), connect=15.0)) as client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                response = client.post(
                    self._get_chat_url(),
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": "test"
                            }
                        ],
                        "max_tokens": 1
                    }
                )

                # Consider it a success if we get any response (even if rate limited)
                return response.status_code < 500

        except httpx.RequestError:
            return False
        except Exception:
            return False