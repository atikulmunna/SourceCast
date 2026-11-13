"""Retrieval and answer-quality eval for SourceCast. Run by hand: it spends credits.

    cd backend
    python -m evals.run_eval --fetch-only
    python -m evals.run_eval --embedding-models openai/text-embedding-3-small
    python -m evals.run_eval --chat settings --chat auto:low --chat model:openai/gpt-6-luna

Fixtures are the caption transcripts of the talks in sources.json, fetched once
through the app's YouTube caption path and cached in evals/fixtures/ (gitignored:
third-party content). Questions are in questions.json.

Per embedding model: hit@1 and hit@5 on answerable questions, top similarity on
answerable and unanswerable questions (to pick the score threshold), and cost.
Per chat configuration (answers use the first embedding model for retrieval):
valid citations, citations of the expected moment, correct refusals, cost and
latency. Results go to stdout and evals/results/<timestamp>.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.schemas.qa import EvidenceHit
from app.services.chunking_service import create_chunks
from app.services.grounded_answer_service import confidence_label, excerpt
from app.services.llm_provider import (
    AUTO_ROUTER,
    OpenRouterAnswerProvider,
    get_answer_provider,
)
from app.services.openrouter_client import OpenRouterClient, get_openrouter_client
from app.services.prompt_service import build_grounded_answer_messages
from app.services.transcription_service import TranscriptSegmentData
from app.services.youtube_caption_service import extract_caption_segments
from evals.metrics import Span, citations_valid, cited_ids, hit_at, is_refusal, overlaps

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
RESULTS = ROOT / "results"
EMBED_BATCH = 64
ANSWER_LIMIT = 5  # evidence items per answer, as in production


class SpendLimitReached(RuntimeError):
    pass


@dataclass
class Question:
    id: str
    question: str
    source: str | None = None
    start: float | None = None
    end: float | None = None

    @property
    def answerable(self) -> bool:
        return self.source is not None


@dataclass
class Chunk:
    span: Span
    text: str
    title: str


@dataclass
class Spend:
    limit: float
    total: float = 0.0
    by_label: dict[str, float] = field(default_factory=dict)

    def add(self, label: str, cost: float | None) -> None:
        self.total += cost or 0.0
        self.by_label[label] = self.by_label.get(label, 0.0) + (cost or 0.0)
        if self.total > self.limit:
            raise SpendLimitReached(f"spent ${self.total:.4f}, over the ${self.limit:.2f} limit")


# ── Fixtures ──────────────────────────────────────────────────────────────────


async def load_segments(source: dict[str, str]) -> list[TranscriptSegmentData]:
    path = FIXTURES / f"{source['key']}.json"
    if not path.exists():
        segments = await extract_caption_segments(source["url"], "en")
        if not segments:
            raise RuntimeError(f"No captions for {source['url']}")
        FIXTURES.mkdir(exist_ok=True)
        path.write_text(
            json.dumps(
                [
                    {"start": float(s.start_time_sec), "end": float(s.end_time_sec), "text": s.text}
                    for s in segments
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        TranscriptSegmentData(
            segment_index=index,
            start_time_sec=Decimal(str(row["start"])),
            end_time_sec=Decimal(str(row["end"])),
            text=row["text"],
        )
        for index, row in enumerate(rows)
    ]


async def build_chunks(sources: list[dict[str, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for source in sources:
        for chunk in create_chunks(await load_segments(source)):
            span = Span(source["key"], float(chunk.start_time_sec), float(chunk.end_time_sec))
            chunks.append(Chunk(span=span, text=chunk.text, title=source["title"]))
    return chunks


def load_questions() -> list[Question]:
    return [Question(**row) for row in json.loads((ROOT / "questions.json").read_text("utf-8"))]


# ── Retrieval ─────────────────────────────────────────────────────────────────


async def embed(
    client: OpenRouterClient, model: str, texts: list[str], spend: Spend
) -> np.ndarray:
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), EMBED_BATCH):
        result = await client.embeddings(model=model, inputs=texts[offset : offset + EMBED_BATCH])
        spend.add(f"embed {model}", result.cost)
        rows = sorted(result.body["data"], key=lambda row: row["index"])
        vectors.extend(row["embedding"] for row in rows)
    matrix = np.asarray(vectors, dtype=np.float32)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


@dataclass
class Index:
    model: str
    chunks: list[Chunk]
    chunk_vectors: np.ndarray
    question_vectors: dict[str, np.ndarray]

    def ranked(self, question_id: str) -> list[tuple[Chunk, float]]:
        scores = self.chunk_vectors @ self.question_vectors[question_id]
        order = np.argsort(-scores)
        return [(self.chunks[i], float(scores[i])) for i in order]


async def build_index(
    client: OpenRouterClient,
    model: str,
    chunks: list[Chunk],
    questions: list[Question],
    spend: Spend,
) -> Index:
    chunk_vectors = await embed(client, model, [c.text for c in chunks], spend)
    question_vectors = await embed(client, model, [q.question for q in questions], spend)
    return Index(
        model=model,
        chunks=chunks,
        chunk_vectors=chunk_vectors,
        question_vectors={q.id: question_vectors[i] for i, q in enumerate(questions)},
    )


def retrieval_report(index: Index, questions: list[Question], cost: float) -> dict[str, Any]:
    answerable = [q for q in questions if q.answerable]
    unanswerable = [q for q in questions if not q.answerable]
    hits1 = hits5 = 0
    top_answerable: list[float] = []
    misses: list[str] = []
    for q in answerable:
        ranked = index.ranked(q.id)
        spans = [chunk.span for chunk, _ in ranked]
        hits1 += hit_at(spans, 1, q.source, q.start, q.end)
        hit5 = hit_at(spans, 5, q.source, q.start, q.end)
        hits5 += hit5
        if not hit5:
            misses.append(q.id)
        top_answerable.append(ranked[0][1])
    top_unanswerable = [index.ranked(q.id)[0][1] for q in unanswerable]
    return {
        "model": index.model,
        "dims": index.chunk_vectors.shape[1],
        "hit@1": hits1 / len(answerable),
        "hit@5": hits5 / len(answerable),
        "top_answerable_median": statistics.median(top_answerable),
        "top_answerable_min": min(top_answerable),
        "top_unanswerable_max": max(top_unanswerable) if top_unanswerable else None,
        "cost": cost,
        "misses": misses,
    }


# ── Answers ───────────────────────────────────────────────────────────────────


def chat_provider(config: str) -> OpenRouterAnswerProvider:
    """`settings` (the configured production chat), `auto:<tier>[:<pattern>|<pattern>]`
    for the Auto Router, or `model:<slug>`."""
    if config == "settings":
        return get_answer_provider()
    kind, _, rest = config.partition(":")
    if kind == "model":
        return OpenRouterAnswerProvider(model=rest)
    if kind != "auto":
        raise ValueError(f"Unknown chat config {config!r}")
    tier, _, patterns = rest.partition(":")
    return OpenRouterAnswerProvider(
        model=AUTO_ROUTER,
        cost_tier=tier or "medium",
        allowed_models=patterns.split("|") if patterns else None,
    )


async def answer_report(
    client: OpenRouterClient,
    config: str,
    index: Index,
    questions: list[Question],
    *,
    threshold: float,
    excerpt_only: bool,
    spend: Spend,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider = chat_provider(config)
    rows: list[dict[str, Any]] = []
    for q in questions:
        hits = [(c, s) for c, s in index.ranked(q.id)[:ANSWER_LIMIT] if s >= threshold]
        evidence = [
            EvidenceHit(
                chunk_id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                space_id=None,
                source_title=chunk.title,
                start_time_sec=Decimal(str(chunk.span.start)),
                end_time_sec=Decimal(str(chunk.span.end)),
                excerpt=excerpt(chunk.text),
                score=round(score, 4),
                confidence_label=confidence_label(score),
                text=None if excerpt_only else chunk.text,
            )
            for chunk, score in hits
        ]
        row: dict[str, Any] = {"id": q.id, "answerable": q.answerable, "evidence": len(evidence)}
        if not evidence:
            row.update(answer="(no evidence above threshold)", refused=True, ids=[], cost=0.0)
            row.update(model="-", latency=0.0, valid=False, grounded=False)
        else:
            started = time.monotonic()
            result = await client.chat_completion(
                provider.payload(build_grounded_answer_messages(q.question, evidence))
            )
            spend.add(f"chat {config}", result.cost)
            answer = result.body["choices"][0]["message"].get("content") or ""
            ids = cited_ids(answer)
            row.update(
                answer=answer.strip(),
                model=result.model,
                cost=result.cost or 0.0,
                latency=time.monotonic() - started,
                ids=ids,
                valid=citations_valid(ids, len(evidence)),
                refused=is_refusal(answer),
                grounded=q.answerable
                and any(
                    overlaps(hits[i - 1][0].span, q.source, q.start, q.end)
                    for i in ids
                    if 1 <= i <= len(hits)
                ),
            )
        row["correct"] = (
            (row["valid"] and not row["refused"]) if q.answerable else row["refused"]
        )
        rows.append(row)

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    called = [r for r in rows if r["model"] != "-"]
    models: dict[str, int] = {}
    for r in called:
        models[r["model"]] = models.get(r["model"], 0) + 1
    summary = {
        "config": config,
        "evidence": "500-char excerpt" if excerpt_only else "full chunk",
        "answered_with_valid_citations": sum(r["correct"] for r in answerable) / len(answerable),
        "cites_expected_moment": sum(r["grounded"] for r in answerable) / len(answerable),
        "correct_refusals": (
            sum(r["correct"] for r in unanswerable) / len(unanswerable) if unanswerable else None
        ),
        "mean_cost": statistics.mean(r["cost"] for r in called) if called else 0.0,
        "median_latency": statistics.median(r["latency"] for r in called) if called else 0.0,
        "models": models,
    }
    return summary, rows


# ── Report ────────────────────────────────────────────────────────────────────


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def markdown(
    retrieval: list[dict[str, Any]],
    answers: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    *,
    chunks: int,
    questions: list[Question],
    threshold: float,
    spend: Spend,
) -> str:
    answerable = sum(q.answerable for q in questions)
    lines = [
        f"# SourceCast eval, {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"{chunks} chunks; {answerable} answerable and {len(questions) - answerable} "
        f"unanswerable questions; answer threshold {threshold}; total spend ${spend.total:.4f}.",
        "",
        "## Retrieval",
        "",
        "| Model | Dims | hit@1 | hit@5 | Top score, answerable (median / min) "
        "| Top score, unanswerable (max) | Cost | Missed at 5 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in retrieval:
        unanswerable_max = r["top_unanswerable_max"]
        lines.append(
            f"| `{r['model']}` | {r['dims']} | {pct(r['hit@1'])} | {pct(r['hit@5'])} "
            f"| {r['top_answerable_median']:.3f} / {r['top_answerable_min']:.3f} "
            f"| {'n/a' if unanswerable_max is None else f'{unanswerable_max:.3f}'} "
            f"| ${r['cost']:.5f} | {', '.join(r['misses']) or 'none'} |"
        )
    if answers:
        lines += [
            "",
            "## Answers",
            "",
            "| Config | Evidence | Valid citations | Cites expected moment | Correct refusals "
            "| Mean cost | Median latency | Models used |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for summary, _ in answers:
            used = ", ".join(f"`{m}` x{n}" for m, n in sorted(summary["models"].items()))
            lines.append(
                f"| `{summary['config']}` | {summary['evidence']} "
                f"| {pct(summary['answered_with_valid_citations'])} "
                f"| {pct(summary['cites_expected_moment'])} | {pct(summary['correct_refusals'])} "
                f"| ${summary['mean_cost']:.5f} | {summary['median_latency']:.1f}s | {used} |"
            )
        for summary, rows in answers:
            lines += ["", f"### `{summary['config']}`, {summary['evidence']}", ""]
            for r in rows:
                flags = "ok" if r["correct"] else "WRONG"
                answer = " ".join(r["answer"].split())[:240]
                lines.append(f"- **{r['id']}** {flags}, cites {r['ids'] or '-'}: {answer}")
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--fetch-only", action="store_true", help="cache fixtures and stop")
    parser.add_argument(
        "--embedding-models",
        default=settings.EMBEDDING_MODEL,
        help="comma-separated; the first one is used for answers",
    )
    parser.add_argument("--chat", action="append", default=[], help="chat config, repeatable")
    parser.add_argument(
        "--excerpt-only", action="store_true", help="send 500-char excerpts (the old prompt)"
    )
    parser.add_argument("--threshold", type=float, default=0.25, help="answer score threshold")
    parser.add_argument("--max-spend", type=float, default=0.50, help="abort above this many USD")
    args = parser.parse_args()

    sources = json.loads((ROOT / "sources.json").read_text("utf-8"))
    chunks = await build_chunks(sources)
    if args.fetch_only:
        print(f"Fixtures cached: {len(chunks)} chunks from {len(sources)} sources.")
        return

    questions = load_questions()
    client = get_openrouter_client()
    spend = Spend(limit=args.max_spend)
    indexes: list[Index] = []
    retrieval: list[dict[str, Any]] = []
    answers = []
    try:
        for model in [m.strip() for m in args.embedding_models.split(",") if m.strip()]:
            before = spend.total
            index = await build_index(client, model, chunks, questions, spend)
            indexes.append(index)
            retrieval.append(retrieval_report(index, questions, spend.total - before))
        for config in args.chat:
            answers.append(
                await answer_report(
                    client,
                    config,
                    indexes[0],
                    questions,
                    threshold=args.threshold,
                    excerpt_only=args.excerpt_only,
                    spend=spend,
                )
            )
    except SpendLimitReached as exc:
        print(f"Stopped: {exc}")
    finally:
        await client.aclose()

    report = markdown(
        retrieval,
        answers,
        chunks=len(chunks),
        questions=questions,
        threshold=args.threshold,
        spend=spend,
    )
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(report, encoding="utf-8")
    raw = {"retrieval": retrieval, "answers": [{"summary": s, "rows": r} for s, r in answers]}
    path.with_suffix(".json").write_text(json.dumps(raw, indent=1, default=str), encoding="utf-8")
    print(report)
    print(f"Saved to {path}")


if __name__ == "__main__":
    asyncio.run(main())
