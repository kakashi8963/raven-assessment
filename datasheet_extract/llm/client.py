"""Azure OpenAI client with retry, usage capture, and JSON-mode extraction."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from openai import AzureOpenAI

from datasheet_extract.config import MAX_RETRIES, MAX_TOKENS, TEMPERATURE, Config
from datasheet_extract.model import Usage

log = logging.getLogger(__name__)

_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE:"


def is_payload_too_large(exc: BaseException) -> bool:
    return str(exc).startswith(_PAYLOAD_TOO_LARGE)


class LLMClient:
    def __init__(self, config: Config):
        if not config.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        if not config.azure_endpoint:
            raise ValueError("AZURE_ENDPOINT_GPT4 environment variable is required")
        self.config = config
        self.client = AzureOpenAI(
            api_key=config.api_key,
            api_version=config.api_version,
            azure_endpoint=config.azure_endpoint,
        )
        self.usage = Usage()

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.config.deployment,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or "{}"
                if resp.usage:
                    self.usage.prompt_tokens += resp.usage.prompt_tokens or 0
                    self.usage.completion_tokens += resp.usage.completion_tokens or 0
                    self.usage.total_tokens += resp.usage.total_tokens or 0
                self.usage.calls += 1
                return json.loads(content)
            except json.JSONDecodeError as e:
                last_err = e
                log.warning("JSON parse failed (attempt %d): %s", attempt + 1, e)
            except Exception as e:
                last_err = e
                err_str = str(e)
                if ("413" in err_str or "context_length" in err_str.lower()) and "max_tokens is too large" not in err_str:
                    raise RuntimeError(f"{_PAYLOAD_TOO_LARGE} {err_str}") from e
                if "429" in err_str and attempt < MAX_RETRIES:
                    wait = _parse_retry_after(err_str) or (2**attempt * 5)
                    log.warning("Rate limited — waiting %.0fs (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                    continue
                log.warning("Azure OpenAI call failed (attempt %d): %s", attempt + 1, e)
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)

        raise RuntimeError(f"LLM chat_json failed after retries: {last_err}")


def _parse_retry_after(err_str: str) -> float | None:
    m = re.search(r"try again in (\d+)m([\d.]+)s", err_str)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r"try again in ([\d.]+)s", err_str)
    if m:
        return float(m.group(1))
    return None
