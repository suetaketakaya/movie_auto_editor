"""Base class for all LLM agents in the Creative Intelligence Layer."""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Standardized response from an LLM agent."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    error: Optional[str] = None
    tokens_used: int = 0
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "model": self.model,
        }


class BaseLLMAgent(ABC):
    """Abstract base class for Creative Intelligence agents.

    All agents use Ollama for local LLM inference with JSON-structured output.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout: int = 120,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        logger.info("%s initialized (model=%s)", self.__class__.__name__, model)

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging and identification."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining the agent's role and behavior."""
        pass

    @abstractmethod
    def build_prompt(self, context: dict[str, Any]) -> str:
        """Build the user prompt from the given context."""
        pass

    @abstractmethod
    def parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate the LLM response into structured data."""
        pass

    async def execute(self, context: dict[str, Any]) -> AgentResponse:
        """Execute the agent with the given context.

        This is an async wrapper around the synchronous LLM call,
        using run_in_executor to avoid blocking.
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_sync, context)

    def _execute_sync(self, context: dict[str, Any]) -> AgentResponse:
        """Synchronous execution of the LLM call."""
        try:
            user_prompt = self.build_prompt(context)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            logger.info("[%s] Sending request to Ollama...", self.name)

            response = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": full_prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2048,
                    },
                },
                timeout=self._timeout,
            )
            response.raise_for_status()

            result = response.json()
            raw_text = result.get("response", "{}")

            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as e:
                logger.warning("[%s] JSON parse error: %s", self.name, e)
                # Try to extract JSON from the response
                parsed = self._extract_json(raw_text)

            data = self.parse_response(parsed)

            logger.info("[%s] Successfully processed response", self.name)

            return AgentResponse(
                success=True,
                data=data,
                raw_response=raw_text,
                model=self._model,
            )

        except requests.RequestException as e:
            logger.error("[%s] HTTP error: %s", self.name, e)
            return AgentResponse(
                success=False,
                error=f"HTTP error: {e}",
                model=self._model,
            )
        except Exception as e:
            logger.error("[%s] Unexpected error: %s", self.name, e)
            return AgentResponse(
                success=False,
                error=str(e),
                model=self._model,
            )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Attempt to extract JSON from a text that may contain extra content."""
        import re
        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
