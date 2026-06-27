"""Pipeline configuration: Azure OpenAI client, deployment, pricing, thresholds."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_DEPLOYMENT = "gpt-4o"
AZURE_API_VERSION = "2024-02-15-preview"

# Azure GPT-4o pricing per 1M tokens (approximate — confirm against your Azure plan).
GPT4O_PRICING: dict[str, float] = {"input": 2.50, "output": 10.00}

# Grounding thresholds
FUZZY_RATIO_THRESHOLD = 0.80
MATCH_SCORE_THRESHOLD = 0.50
LINE_CLUSTER_Y_TOLERANCE_FACTOR = 0.5

# OCR
OCR_DPI = 300
OCR_LANG = "eng+fra"
OCR_MIN_WORDS_PER_PAGE = 5

# Section detection / merge
MIN_SECTION_LINES = 3
MIN_HEADER_CHARS = 8

# Post-filter
MIN_FIELD_NAME_LEN = 3
OCR_MIN_LABEL_CONF = 0.55
MIN_NAME_ALPHA_RATIO = 0.45

# LLM
MAX_RETRIES = 2
TEMPERATURE = 0.0
MAX_TOKENS = 4_096  # Azure gpt-4o deployment completion limit
LINES_PER_BATCH = 40
DENSE_PAGE_LINES = 45  # above this, skip whole-page call and use merged sections


@dataclass
class Config:
    api_key: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_API_KEY", ""))
    azure_endpoint: str = field(
        default_factory=lambda: os.environ.get("AZURE_ENDPOINT_GPT4", "").rstrip("/")
    )
    deployment: str = field(
        default_factory=lambda: os.environ.get("AZURE_DEPLOYMENT_GPT4", DEFAULT_DEPLOYMENT)
    )
    api_version: str = AZURE_API_VERSION

    def pricing(self) -> dict[str, float]:
        return GPT4O_PRICING
