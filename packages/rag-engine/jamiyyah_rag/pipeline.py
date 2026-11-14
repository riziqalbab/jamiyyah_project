"""Multi-Layered RAG pipeline using OpenAI-compatible Cloud LLM + Strict Guardrails."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from jamiyyah_rag.guardrails import GroundingConfig, validate_citations
from jamiyyah_rag.openai_compat import OpenAICompatClient, OpenAICompatError

_STRICT_GROUNDING_SYSTEM_PROMPT = """\
Anda adalah asisten peneliti literatur Islam (Turats Syafi'iyah, Hadits, Bahtsul Masail, dan Al-Qur'an) pada mesin pencari Jamiyyah.

ATURAN MUTLAK (STRICT GROUNDING & ANTI-HALUSINASI):
1. Jawab HANYA berdasarkan potongan sumber primer yang diberikan di konteks user. DILARANG keras menggunakan pengetahuan eksternal, menambah dalil yang tidak tertulis di konteks, atau mengarang teks Arab/terjemahan.
2. Setiap pernyataan faktual atau poin hukum WAJIB menyertakan tag sitasi persis dalam format `[ID: <chunk_id>]` sesuai ID pada konteks.
3. DILARANG membuat kesimpulan istinbath hukum mandiri di luar apa yang dinyatakan secara eksplisit oleh teks rujukan.
4. Bedakan dengan jelas antara:
   - Ketentuan/pendapat yang tertulis langsung dalam nash/ibarat rujukan.
   - Penjelasan ringkas atau terjemahan dari rujukan tersebut.
5. Jika konteks yang diberikan ternyata TIDAK cukup atau tidak menjawab pertanyaan pengguna secara langsung, balas persis diawali dengan `TAWAQQUF:` diikuti alasan singkatnya.

FORMAT JAWABAN:
- Bahasa Indonesia ilmiah yang jernih, ringkas, dan terstruktur dengan poin-poin bila perlu.
- Kutip frasa Arab kunci dari `arabic_raw` seperlunya jika relevan dan tersedia di konteks.
- Pastikan seluruh ID pada `[ID: ...]` benar-benar ada dalam konteks.\
"""

_QUERY_EXPANSION_SYSTEM_PROMPT = """\
Anda membantu ekspansi kueri lintas-bahasa (Bahasa Indonesia ke istilah pencarian fikih/hadits Bahasa Arab) untuk mesin retrieval Jamiyyah.
Keluarkan HANYA objek JSON valid dengan format: {"ar_terms": ["...", "..."]}.
Berikan 3 sampai 6 kata/frasa Arab singkat tanpa harakat yang relevan untuk pencarian leksikal. Jangan menjawab pertanyaannya.\
"""


@dataclass(frozen=True)
class GroundedGenerationResult:
    """Outcome of Layer 2 LLM generation checked by Layer 3 citation validation."""

    status: str  # "answered" | "tawaqquf"
    answer: str | None
    cited_ids: list[str]
    missing_ids: list[str]
    reason: str


def expand_query_with_llm(
    query: str,
    llm_client: OpenAICompatClient,
    *,
    model: str,
) -> list[str]:
    """Generate Arabic search terms from an Indonesian query using ``temperature=0.0``."""
    try:
        raw = llm_client.chat_completion(
            [
                {"role": "system", "content": _QUERY_EXPANSION_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            model=model,
            temperature=0.0,
            max_tokens=180,
        )
    except OpenAICompatError:
        return []

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    terms = parsed.get("ar_terms")
    if not isinstance(terms, list):
        return []
    return [str(t).strip() for t in terms if str(t).strip()][:8]


def build_rag_context(chunks: Sequence[dict[str, Any]]) -> str:
    """Serialize retrieved canonical chunks into a citation-bounded prompt context."""
    blocks: list[str] = []
    for chunk in chunks:
        cid = chunk["chunk_id"]
        hier = " > ".join(chunk.get("hierarchy", []))
        ref = chunk.get("citation", {}).get("full_reference") or cid
        ar_raw = (chunk.get("content", {}).get("arabic_raw") or "").strip()
        indo = (chunk.get("content", {}).get("indonesian") or "").strip()
        blocks.append(
            f"[ID: {cid}]\n"
            f"Referensi: {ref}\n"
            f"Hierarki: {hier}\n"
            f"Ibarat Arab (arabic_raw): {ar_raw or '(tidak tersedia)'}\n"
            f"Terjemah/Keterangan Indonesia: {indo or '(tidak tersedia)'}"
        )
    return "\n\n---\n\n".join(blocks)


def generate_strict_grounded_answer(
    query: str,
    chunks: Sequence[dict[str, Any]],
    llm_client: OpenAICompatClient,
    *,
    model: str,
    config: GroundingConfig | None = None,
) -> GroundedGenerationResult:
    """Execute Layer 2 Cloud LLM synthesis followed by Layer 3 Citation Validation."""
    cfg = config or GroundingConfig()
    allowed_ids = [chunk["chunk_id"] for chunk in chunks]
    context_text = build_rag_context(chunks)

    user_prompt = (
        f"Pertanyaan Pengguna:\n{query}\n\n"
        f"Konteks Sumber Terverifikasi (wajib disitasi dengan [ID: <chunk_id>]):\n\n"
        f"{context_text}"
    )

    answer_text = llm_client.chat_completion(
        [
            {"role": "system", "content": _STRICT_GROUNDING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=cfg.temperature,
        max_tokens=1100,
    )

    if answer_text.upper().startswith("TAWAQQUF:"):
        return GroundedGenerationResult(
            status="tawaqquf",
            answer=None,
            cited_ids=[],
            missing_ids=[],
            reason=answer_text,
        )

    cit_check = validate_citations(
        answer_text,
        allowed_chunk_ids=allowed_ids,
        require_at_least_one=cfg.require_citations,
    )
    if not cit_check.valid:
        detail = (
            f"Fabricated citation IDs: {cit_check.missing_ids}"
            if cit_check.missing_ids
            else "Model output omitted mandatory [ID: <chunk_id>] citations."
        )
        return GroundedGenerationResult(
            status="tawaqquf",
            answer=None,
            cited_ids=cit_check.cited_ids,
            missing_ids=cit_check.missing_ids,
            reason=f"Layer 3 Citation Validation failed ({detail}).",
        )

    return GroundedGenerationResult(
        status="answered",
        answer=answer_text,
        cited_ids=cit_check.cited_ids,
        missing_ids=[],
        reason="OK",
    )
