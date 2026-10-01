"""Strict input contracts. PR content is data, never executable instructions."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def safe_text(value: str) -> str:
    if any(unicodedata.category(c).startswith("C") and c not in "\n\t\r" for c in value):
        raise ValueError("Control and invisible formatting characters are not allowed")
    return value


class PullRequest(StrictModel):
    number: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=20_000)
    labels: list[str] = Field(default_factory=list, max_length=50)
    url: str = Field(max_length=300)
    merged: bool

    @field_validator("title", "body")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return safe_text(value)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Title must not be blank")
        return value

    @field_validator("labels")
    @classmethod
    def normalize_labels(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _:/.-]{0,63}", v) for v in values):
            raise ValueError("Labels must be short printable names")
        return sorted({v.lower() for v in values})


class Source(StrictModel):
    repository: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$"
    )
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$")
    pull_requests: list[PullRequest] = Field(max_length=500)

    @model_validator(mode="after")
    def validate_sources(self) -> "Source":
        seen = set()
        for pr in self.pull_requests:
            if pr.number in seen:
                raise ValueError(f"Duplicate PR number: {pr.number}")
            seen.add(pr.number)
            if pr.url != f"https://github.com/{self.repository}/pull/{pr.number}":
                raise ValueError(f"PR #{pr.number}: URL must match repository and number exactly")
        self.pull_requests.sort(key=lambda pr: pr.number)
        return self


class Draft(StrictModel):
    schema_version: Literal[1] = 1
    generator: Literal["deterministic-template-v1"] = "deterministic-template-v1"
    source: Source
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    markdown: str = Field(max_length=500_000)
    warnings: list[str]
    excluded_prs: list[int]
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
