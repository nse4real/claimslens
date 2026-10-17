"""Single gateway for Claude message completions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

MODEL_ID = "claude-haiku-5-5"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0


class CallCapExceeded(Exception):
    pass


class MissingApiKey(Exception):
    pass


class Gateway(Protocol):
    @property
    def usage(self) -> Usage: ...

    def complete(self, system: str, user: str, model: str, max_tokens: int) -> str: ...


class AnthropicGateway:
    def __init__(self, max_calls: int, sdk: Any | None = None) -> None:
        self.max_calls = max_calls
        self._usage = Usage()
        if sdk is not None:
            self._sdk = sdk
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise MissingApiKey(
                "ANTHROPIC_API_KEY is not set. Set ANTHROPIC_API_KEY before using the Anthropic gateway."
            )

        import anthropic

        self._sdk = anthropic.Anthropic(api_key=api_key)

    @property
    def usage(self) -> Usage:
        return Usage(
            input_tokens=self._usage.input_tokens,
            output_tokens=self._usage.output_tokens,
            calls=self._usage.calls,
        )

    def complete(self, system: str, user: str, model: str, max_tokens: int) -> str:
        if self._usage.calls >= self.max_calls:
            raise CallCapExceeded(
                f"Call cap of {self.max_calls} would be exceeded; no API call was made."
            )

        self._usage.calls += 1
        response = self._sdk.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self._usage.input_tokens += response.usage.input_tokens
        self._usage.output_tokens += response.usage.output_tokens

        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""
