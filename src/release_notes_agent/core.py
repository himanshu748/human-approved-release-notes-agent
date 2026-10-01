"""Pure, deterministic drafting and integrity verification; no network or model calls."""

import hashlib
import html
import json
import re
from typing import Any

from .models import Draft, Source

MAX_SOURCE_BYTES = 1024 * 1024
MAX_DRAFT_BYTES = 2 * 1024 * 1024
SECTIONS = (
    ("Breaking changes", {"breaking", "breaking-change", "breaking change"}),
    ("Features", {"feature", "enhancement", "feat"}),
    ("Fixes", {"bug", "fix", "bugfix"}),
    ("Documentation", {"docs", "documentation"}),
    ("Maintenance", set()),
)
SUSPICIOUS = re.compile(
    r"ignore (?:all |previous |prior )*instructions|system prompt|publish now|"
    r"skip (?:the )?(?:review|approval)|approve automatically|reveal (?:the )?(?:secret|token)",
    re.IGNORECASE,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_source(value: str | dict) -> Source:
    encoded = value if isinstance(value, str) else canonical_json(value)
    if len(encoded.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds 1 MiB limit")
    return Source.model_validate(json.loads(encoded))


def escape_markdown(value: str) -> str:
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def build_draft(source: Source) -> Draft:
    source = parse_source(source.model_dump(mode="json"))
    source_sha = digest_of(source.model_dump(mode="json"))
    warnings = [
        "Draft uses PR titles and labels only; verify user impact and technical accuracy.",
        "Sources are an unverified local snapshot; hashes prove consistency, not authenticity.",
    ]
    sections: dict[str, list[str]] = {name: [] for name, _ in SECTIONS}
    excluded = []
    for pr in source.pull_requests:
        if not pr.merged:
            excluded.append(pr.number)
            continue
        section = next(
            (name for name, labels in SECTIONS if labels.intersection(pr.labels)), "Maintenance"
        )
        sections[section].append(f"- {escape_markdown(pr.title)} ([#{pr.number}]({pr.url}))")
        if SUSPICIOUS.search(pr.title + "\n" + pr.body):
            warnings.append(
                f"PR #{pr.number}: instruction-like text detected; inspect source body."
            )
        if section == "Breaking changes":
            warnings.append(f"PR #{pr.number}: maintainer must verify migration guidance.")
    lines = [
        f"# {source.repository} {source.version}",
        "",
        "<!-- DRAFT: human review required -->",
        "",
    ]
    for section, entries in sections.items():
        if entries:
            lines += [f"## {section}", "", *entries, ""]
            if section == "Breaking changes":
                lines += [
                    "Migration guidance must be supplied by a maintainer "
                    "before external publication.",
                    "",
                ]
    if not any(sections.values()):
        lines += ["No merged pull requests in this snapshot.", ""]
        warnings.append("Empty release: no merged pull requests were included.")
    lines += [
        "## Source provenance",
        "",
        f"Snapshot SHA-256: `{source_sha}`",
        "",
        "Drafting mode: deterministic template; no LLM-generated claims.",
        "",
    ]
    fields = {
        "schema_version": 1,
        "generator": "deterministic-template-v1",
        "source": source.model_dump(mode="json"),
        "source_sha256": source_sha,
        "markdown": "\n".join(lines),
        "warnings": warnings,
        "excluded_prs": excluded,
    }
    return Draft.model_validate({**fields, "digest": digest_of(fields)})


def load_draft(text: str) -> Draft:
    if len(text.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise ValueError("Draft exceeds 2 MiB limit")
    draft = Draft.model_validate(json.loads(text))
    fields = draft.model_dump(mode="json", exclude={"digest"})
    if digest_of(fields) != draft.digest:
        raise ValueError("Draft integrity check failed; regenerate the draft")
    if build_draft(draft.source) != draft:
        raise ValueError("Draft does not match generated content; regenerate from the source")
    return draft
