"""Response types returned by every adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Choice:
    index: int
    message: Message
    finish_reason: str  # "stop" | "length" | "content_filter"


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Completion:
    model: str
    choices: list[Choice]
    usage: Usage
    raw: Any = field(default=None, repr=False)
