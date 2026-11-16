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
6. Riwayat percakapan sebelumnya (jika ada) berfungsi sebagai konteks agar Anda memahami rujukan, topik lanjutan, atau maksud pertanyaan pengguna. Namun seluruh klaim hukum/faktual pada jawaban saat ini tetap WAJIB bersumber dan disitasi dengan `[ID: <chunk_id>]` dari Konteks Sumber Terverifikasi pada pesan terakhir.

FORMAT JAWABAN:
- Bahasa Indonesia ilmiah yang jernih, ringkas, dan terstruktur dengan poin-poin bila perlu.
- Kutip frasa Arab kunci dari `arabic_raw` seperlunya jika relevan dan tersedia di konteks.
- Pastikan seluruh ID pada `[ID: ...]` benar-benar ada dalam konteks.\
"""

_QUERY_EXPANSION_SYSTEM_PROMPT = """\
Anda membantu ekspansi kueri lintas-bahasa (Bahasa Indonesia ke istilah pencarian fikih/hadits Bahasa Arab) untuk mesin retrieval Jamiyyah.
Keluarkan HANYA objek JSON valid dengan format: {"standalone_query": "...", "ar_terms": ["...", "..."]}.
- `standalone_query`: jika terdapat riwayat percakapan dan kueri terbaru berupa pertanyaan lanjutan (memakai kata rujukan seperti "itu", "tadi", "syaratnya", dll.), tulis ulang menjadi pertanyaan mandiri yang utuh dalam Bahasa Indonesia; jika sudah mandiri, pertahankan maksud aslinya secara ringkas.
- `ar_terms`: berikan 3 sampai 6 kata/frasa Arab singkat tanpa harakat yang relevan untuk pencarian leksikal. Jangan menjawab pertanyaannya.\
"""

_CONVERSATIONAL_SYSTEM_PROMPT = """\
Anda adalah Jamiyyah, asisten peneliti literatur Islam yang ramah, santun, dan membantu.
Saat ini pengguna sedang melakukan percakapan biasa (sapaan, ucapan terima kasih, perkenalan, obrolan ringan, atau pertanyaan umum tentang fungsi Jamiyyah).

PANDUAN:
1. Jawablah secara natural, hangat, dan ringkas dalam bahasa yang digunakan pengguna (utamanya Bahasa Indonesia).
2. Gunakan riwayat percakapan sebelumnya (jika ada) untuk memahami konteks obrolan pengguna (misalnya nama pengguna atau topik yang baru saja dibahas).
3. Anda dapat menjelaskan secara singkat bahwa Jamiyyah membantu menelusuri rujukan primer Turats Syafi'iyah (seperti Matan Taqrib & Fathul Qarib), Hadits, Bahtsul Masail, dan Al-Qur'an dengan prinsip kehati-hatian ilmiah (*Tawaqquf* bila dalil/rujukan tidak mencukupi).
4. Jangan mengarang dalil, hadits, atau tag `[ID: ...]` fiktif. Bila pengguna ingin menanyakan hukum fikih atau rujukan kitab tertentu, ajak mereka menuliskannya langsung agar sistem dapat menelusuri teks primer yang terverifikasi.\
"""

_GREETING_PREFIXES = (
    "assalamualaikum warahmatullahi wabarakatuh",
    "assalamu alaikum warahmatullahi wabarakatuh",
    "assalamualaikum wr wb",
    "assalamualaikum",
    "assalamu alaikum",
    "asalamualaikum",
    "waalaikumsalam warahmatullahi wabarakatuh",
    "waalaikumsalam",
    "selamat pagi",
    "selamat siang",
    "selamat sore",
    "selamat malam",
    "ahlan wa sahlan",
    "ahlan",
    "marhaban",
    "permisi",
    "punten",
    "halo",
    "hallo",
    "hello",
    "hai",
    "hei",
    "hey",
    "hi",
)

_VOCATIVE_WORDS = frozenset({
    "jamiyyah", "min", "admin", "kak", "bro", "sis", "bang", "mas", "mbak",
    "ustadz", "ustad", "pak", "bu", "teman", "kawan", "bot", "ai", "asisten",
    "semua", "semuanya", "ya", "yah", "nih", "dong", "deh", "sih", "rek",
})

_PURE_CASUAL_PHRASES = frozenset({
    "p", "tes", "test", "testing", "ping", "cek", "cek cek",
    "pagi", "siang", "sore", "malam", "salam", "salam kenal",
    "apa kabar", "apa kabarnya", "gimana kabarnya", "gimana kabar",
    "bagaimana kabarmu", "gimana kabarmu", "kabar baik", "baik baik",
    "how are you", "how r u",
    "terima kasih", "terima kasih banyak", "terimakasih", "makasih",
    "makasih banyak", "makasih ya", "makasi", "trims", "thanks", "thank you",
    "thx", "ty", "syukron", "syukran", "jazakallah", "jazakallah khairan",
    "jazakumullah", "jazakumullah khairan", "alhamdulillah", "sama sama",
    "oke", "ok", "okay", "baik", "baiklah", "siap", "sip", "mantap", "bagus",
    "keren", "hebat", "paham", "mengerti", "jelas", "noted", "iya", "ya",
    "oh gitu", "ooh gitu", "ooo gitu", "sip makasih", "oke makasih",
    "oke siap", "baik makasih", "siap paham", "oke paham",
    "sampai jumpa", "bye", "goodbye", "dadah", "wassalamualaikum",
    "hehe", "hihi", "haha", "wkwk", "wkwkwk",
})

_CASUAL_REGEXES = (
    re.compile(r"^(siapa\s+(kamu|anda|namamu|nama\s+kamu|dirimu))$"),
    re.compile(r"^(kamu|anda)\s+(itu\s+)?(siapa|apa)$"),
    re.compile(r"^(apa\s+itu\s+jamiyyah)$"),
    re.compile(r"^(perkenalkan\s+(dirimu|diri\s+kamu|diri\s+anda))$"),
    re.compile(r"^(kamu|anda|jamiyyah)\s+(bisa|dapat)\s+(bantu|melakukan\s+)?apa(\s+saja)?$"),
    re.compile(r"^bisa\s+(bantu|tolong)\s+apa(\s+saja)?$"),
    re.compile(r"^(apa\s+saja\s+)?fitur(\s+(kamu|anda|jamiyyah))?$"),
    re.compile(r"^(bagaimana|gimana)\s+cara\s+(pakai|pakenya|pakainya|menggunakan|kerja)(\s+nya)?$"),
    re.compile(r"^(bantuan|help|panduan)$"),
    re.compile(r"^(boleh|bisa)\s+(tanya|bertanya|nanya|kenalan|ngobrol)(\s+(dong|ya|kak|min))?$"),
    re.compile(r"^(aku|saya|ana|ane)\s+(mau|ingin)\s+(tanya|bertanya|nanya|kenalan|ngobrol)(\s+(dong|nih|sesuatu))?$"),
    re.compile(r"^(mau|ingin)\s+(tanya|bertanya|nanya)(\s+(dong|nih|ya|sesuatu))?$"),
    re.compile(r"^izin\s+(bertanya|tanya|nanya)$"),
    re.compile(r"^(lagi\s+(apa|ngapain|sibuk)(\s+nih)?)$"),
    re.compile(r"^(nama\s+(saya|aku)\s+[a-z0-9\s]{1,40}|namaku\s+[a-z0-9\s]{1,40}|panggil\s+(saya|aku)\s+[a-z0-9\s]{1,30})$"),
    re.compile(r"^(siapa\s+nama\s+(saya|aku))$"),
    re.compile(r"^(terima\s+kasih|makasih|syukron|jazakallah).{0,40}(penjelasannya|bantuannya|jawabannya|infonya|informasinya)?$"),
    re.compile(r"^(sangat\s+membantu|membantu\s+sekali|penjelasannya\s+(bagus|jelas|keren|mantap))$"),
    re.compile(r"^(wah\s+)?(keren|mantap|bagus|hebat|nice|good)(\s+(banget|sekali|nih|ya))?$"),
    re.compile(r"^(kamu|anda)\s+(pakai|menggunakan)\s+model\s+apa$"),
)

_HISTORY_REPHRASE_REGEXES = (
    re.compile(r"^(tolong\s+)?(ringkas|persingkat|simpulkan|ulangi)(\s+(lagi|dong|ya|saja|aja|jawaban\s+tadi))?$"),
    re.compile(r"^(tolong\s+)?(jelaskan\s+)?(lebih\s+)?(singkat|sederhana|ringkas|simpel|mudah\s+dipahami)(\s+(lagi|dong|ya))?$"),
)

_DOMAIN_OR_EXTERNAL_MARKERS = frozenset({
    "hukum", "hukumnya", "dalil", "dalilnya", "kitab", "hadits", "hadis",
    "quran", "alquran", "ayat", "surah", "surat", "fikih", "fiqih", "syariah",
    "syariat", "syarat", "syaratnya", "rukun", "rukunnya", "wajib", "haram",
    "halal", "sunnah", "makruh", "mubah", "sah", "batal", "batalnya",
    "shalat", "sholat", "solat", "wudhu", "wudlu", "tayammum", "tayamum",
    "najis", "thaharah", "qullah", "zakat", "puasa", "haji", "umrah",
    "nikah", "talak", "waris", "riba", "salam", "akad", "jual", "beli",
    "paylater", "gadai", "wakaf", "hibah", "prediksi", "harga", "saham",
    "kripto", "bitcoin", "presiden", "resep", "sejarah", "tafsir", "fatwa",
    "mazhab", "madzhab", "syafii", "syafiiyah", "taqrib", "fathul", "qarib",
})

_FOLLOWUP_ANAPHORA_MARKERS = frozenset({
    "itu", "tersebut", "tadi", "ini", "begitu", "demikian", "selanjutnya",
    "lalu", "terus", "kemudian", "kalau", "jika", "bagaimana", "gimana",
    "maksudnya", "dalilnya", "syaratnya", "hukumnya", "rukunnya", "contohnya",
    "penjelasannya", "bedanya", "lanjutannya", "menurut",
})

_STOPWORDS_CONTEXT = frozenset({
    "apa", "apakah", "bagaimana", "bagai", "siapa", "kapan", "dimana",
    "mengapa", "kenapa", "berapa", "mana", "yang", "dan", "atau", "di", "ke",
    "dari", "pada", "untuk", "dengan", "dalam", "itu", "ini", "adalah",
    "tentang", "mengenai", "menurut", "saja", "ada", "tidak", "bukan",
    "boleh", "bisa", "dapat", "harus", "saya", "aku", "kita", "kami",
    "tolong", "jelaskan", "sebutkan", "coba", "dong", "ya", "kah",
})


@dataclass(frozen=True)
class GroundedGenerationResult:
    """Outcome of Layer 2 LLM generation checked by Layer 3 citation validation."""

    status: str  # "answered" | "tawaqquf"
    answer: str | None
    cited_ids: list[str]
    missing_ids: list[str]
    reason: str


def normalize_chat_history(
    history: Sequence[dict[str, Any]] | None,
    *,
    max_messages: int = 10,
    max_chars: int = 1500,
) -> list[dict[str, str]]:
    """Sanitize and bound conversation history into ``[{role, content}, ...]``."""
    if not history:
        return []

    cleaned: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if len(content) > max_chars:
            content = f"{content[:max_chars].rstrip()}..."
        cleaned.append({"role": role, "content": content})

    if max_messages > 0 and len(cleaned) > max_messages:
        return cleaned[-max_messages:]
    return cleaned


def _normalize_casual_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("'", "").replace("’", "")
    # Collapse exaggerated repeated letters on common greeting/filler tokens (halooo -> halo)
    lowered = re.sub(r"\bha+l+o+\b", "halo", lowered)
    lowered = re.sub(r"\bha+i+\b", "hai", lowered)
    lowered = re.sub(r"\bh+i+\b", "hi", lowered)
    lowered = re.sub(r"\bo+k+e+\b", "oke", lowered)
    lowered = re.sub(r"\bmaka+si+h+\b", "makasih", lowered)
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _strip_greeting_prefixes(norm_text: str) -> str:
    remaining = norm_text
    changed = True
    while changed and remaining:
        changed = False
        for prefix in _GREETING_PREFIXES:
            if remaining == prefix:
                return ""
            if remaining.startswith(f"{prefix} "):
                remaining = remaining[len(prefix) :].strip()
                changed = True
                break
        if remaining:
            tokens = remaining.split()
            while tokens and tokens[0] in _VOCATIVE_WORDS:
                tokens.pop(0)
                changed = True
            remaining = " ".join(tokens)
    return remaining


def is_casual_conversation(
    query: str,
    history: Sequence[dict[str, Any]] | None = None,
) -> bool:
    """Return True only when ``query`` is casual chat that should bypass RAG guardrails."""
    raw = query.strip()
    if not raw:
        return False

    norm = _normalize_casual_text(raw)
    if not norm:
        return False

    words = set(norm.split())
    if words & _DOMAIN_OR_EXTERNAL_MARKERS:
        return False

    remainder = _strip_greeting_prefixes(norm)
    if not remainder:
        return True

    if remainder in _PURE_CASUAL_PHRASES:
        return True

    # Strip trailing vocatives like "apa kabar kak" -> "apa kabar"
    rem_tokens = remainder.split()
    while len(rem_tokens) > 1 and rem_tokens[-1] in _VOCATIVE_WORDS:
        rem_tokens.pop()
    remainder_trimmed = " ".join(rem_tokens)
    if remainder_trimmed in _PURE_CASUAL_PHRASES:
        return True

    for pattern in _CASUAL_REGEXES:
        if pattern.match(remainder) or pattern.match(remainder_trimmed):
            return True

    if normalize_chat_history(history):
        for pattern in _HISTORY_REPHRASE_REGEXES:
            if pattern.match(remainder) or pattern.match(remainder_trimmed):
                return True

    return False


def _deterministic_casual_reply(
    query: str,
    history: Sequence[dict[str, str]],
) -> str:
    norm = _normalize_casual_text(query)
    if "assalamualaikum" in norm or "asalamualaikum" in norm or "assalamu alaikum" in norm:
        greeting = "Wa'alaikumussalam warahmatullahi wabarakatuh."
    elif any(w in norm for w in ("terima kasih", "terimakasih", "makasih", "thanks", "thank you", "syukron", "syukran", "jazak")):
        return (
            "Sama-sama! Senang bisa membantu. Silakan ajukan pertanyaan fikih, hadits, "
            "atau rujukan kitab lainnya kapan saja."
        )
    elif any(p in norm for p in ("siapa kamu", "kamu siapa", "siapa anda", "apa itu jamiyyah", "bisa bantu apa", "kamu bisa apa", "fitur")):
        return (
            "Saya **Jamiyyah**, asisten peneliti literatur Islam yang berfokus pada "
            "penelusuran teks primer (Kitab Turats Syafi'iyah, Hadits, Bahtsul Masail, dan Al-Qur'an) "
            "dengan sitasi terverifikasi serta prinsip *Tawaqquf* bila bukti tidak mencukupi. "
            "Ada topik fikih atau hadits yang ingin Anda telusuri?"
        )
    elif any(w in norm for w in ("oke", "ok", "baik", "siap", "sip", "paham", "mengerti", "jelas", "mantap")):
        return "Siap! Jika ada pertanyaan lanjutan atau pembahasan kitab lain yang ingin ditelusuri, silakan sampaikan."
    else:
        greeting = "Halo! Selamat datang di Jamiyyah."

    if history:
        return (
            f"{greeting} Percakapan kita sebelumnya masih tersimpan dalam konteks. "
            "Silakan lanjutkan obrolan atau ajukan pertanyaan fikih/hadits yang ingin ditelusuri."
        )
    return (
        f"{greeting} Ada topik fikih, hadits, atau rujukan kitab turats yang ingin Anda telusuri hari ini?"
    )


def generate_conversational_reply(
    query: str,
    llm_client: OpenAICompatClient | None,
    *,
    model: str,
    history: Sequence[dict[str, Any]] | None = None,
) -> tuple[str, str, str | None]:
    """Generate a friendly conversational reply using history without RAG guardrails.

    Returns ``(answer_text, rag_mode, llm_error)``.
    """
    clean_history = normalize_chat_history(history)
    if llm_client is None:
        return _deterministic_casual_reply(query, clean_history), "conversational_fallback", None

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _CONVERSATIONAL_SYSTEM_PROMPT},
        *clean_history,
        {"role": "user", "content": query.strip()},
    ]
    try:
        answer = llm_client.chat_completion(
            messages,
            model=model,
            temperature=0.4,
            max_tokens=500,
        )
        return answer, "conversational", None
    except OpenAICompatError as exc:
        return (
            _deterministic_casual_reply(query, clean_history),
            "conversational_fallback",
            str(exc),
        )


def contextualize_query_fallback(
    query: str,
    history: Sequence[dict[str, Any]] | None = None,
) -> str:
    """Append key terms from the prior user question when ``query`` is a short follow-up."""
    clean_history = normalize_chat_history(history)
    if not clean_history:
        return query

    tokens = re.findall(r"[a-z0-9']+|[\u0600-\u06FF]+", query.lower())
    needs_context = len(tokens) <= 5 or any(t in _FOLLOWUP_ANAPHORA_MARKERS for t in tokens)
    if not needs_context:
        return query

    prev_user_msgs = [m["content"] for m in clean_history if m["role"] == "user"]
    if not prev_user_msgs:
        return query

    prev_tokens = re.findall(r"[a-z0-9']+|[\u0600-\u06FF]+", prev_user_msgs[-1].lower())
    cur_set = set(tokens)
    carry_terms = [
        t
        for t in prev_tokens
        if t not in _STOPWORDS_CONTEXT and t not in cur_set and len(t) > 1
    ]
    if not carry_terms:
        return query

    # Deduplicate while preserving order
    deduped = list(dict.fromkeys(carry_terms))[:6]
    return f"{query.strip()} ({' '.join(deduped)})"


def contextualize_and_expand_query(
    query: str,
    llm_client: OpenAICompatClient,
    *,
    model: str,
    history: Sequence[dict[str, Any]] | None = None,
) -> tuple[str, list[str]]:
    """Contextualize follow-up queries with history and generate Arabic search terms."""
    clean_history = normalize_chat_history(history, max_messages=6, max_chars=500)
    if clean_history:
        hist_lines = [
            f"{'Pengguna' if m['role'] == 'user' else 'Asisten'}: {m['content']}"
            for m in clean_history
        ]
        user_content = (
            "Riwayat percakapan sebelumnya:\n"
            + "\n".join(hist_lines)
            + f"\n\nPertanyaan terbaru:\n{query}"
        )
    else:
        user_content = query

    try:
        raw = llm_client.chat_completion(
            [
                {"role": "system", "content": _QUERY_EXPANSION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            model=model,
            temperature=0.0,
            max_tokens=240,
        )
    except OpenAICompatError:
        return contextualize_query_fallback(query, clean_history), []

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return contextualize_query_fallback(query, clean_history), []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return contextualize_query_fallback(query, clean_history), []

    standalone = parsed.get("standalone_query")
    effective_query = (
        str(standalone).strip()
        if isinstance(standalone, str) and str(standalone).strip()
        else contextualize_query_fallback(query, clean_history)
    )

    terms = parsed.get("ar_terms")
    ar_terms = (
        [str(t).strip() for t in terms if str(t).strip()][:8]
        if isinstance(terms, list)
        else []
    )
    return effective_query, ar_terms


def expand_query_with_llm(
    query: str,
    llm_client: OpenAICompatClient,
    *,
    model: str,
    history: Sequence[dict[str, Any]] | None = None,
) -> list[str]:
    """Generate Arabic search terms from an Indonesian query using ``temperature=0.0``."""
    _effective_query, ar_terms = contextualize_and_expand_query(
        query,
        llm_client,
        model=model,
        history=history,
    )
    return ar_terms


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
    history: Sequence[dict[str, Any]] | None = None,
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

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _STRICT_GROUNDING_SYSTEM_PROMPT},
        *normalize_chat_history(history),
        {"role": "user", "content": user_prompt},
    ]

    answer_text = llm_client.chat_completion(
        messages,
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
