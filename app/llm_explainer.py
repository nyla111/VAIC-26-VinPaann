"""LLM-grounded explanation — thay 'explanation' template cố định bằng câu trả lời do Claude
sinh ra, CHỈ được phép dựa trên evidence thật truyền vào (bulletin/policy text trích từ
data canonical). 
Thiết kế fail-open giống `ml_forecaster.py`: nếu thiếu `anthropic` package, thiếu
ANTHROPIC_API_KEY, hoặc API lỗi/refusal — trả về None và caller (main.py) tự dùng lại
`explanation` template cũ. 
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

logger = logging.getLogger("ai2_dispatch.llm_explainer")

MODEL_ID = "claude-opus-4-8"

SYSTEM_PROMPT = """Bạn là trợ lý giải thích quyết định cho hệ thống điều phối logistics nông \
sản ĐBSCL (AI Layer 2 - Forecast & Dispatch Agent tại Cần Thơ).

Nhiệm vụ: viết 2-4 câu tiếng Việt giải thích NGẮN GỌN quyết định dispatch, DÀNH CHO người vận \
hành (không phải kỹ sư).

Quy tắc bắt buộc:
- CHỈ dùng thông tin trong phần "DỮ LIỆU" được cung cấp — không suy đoán, không bịa số liệu, \
không thêm bulletin_id/policy_id nào không có trong dữ liệu.
- Nếu có bulletin thời tiết hoặc policy liên quan, trích dẫn đúng ID của nó trong câu trả lời \
(ví dụ: "theo bản tin WX_...", "theo chính sách POL_...").
- Không lặp lại nguyên văn con số JSON — diễn giải bằng câu tự nhiên.
- Không thêm lời khuyên, không thêm cảnh báo ngoài dữ liệu được cung cấp.
- Trả lời bằng văn xuôi thuần, không dùng markdown, không dùng bullet."""


@lru_cache(maxsize=1)
def _get_client():
    try:
        import anthropic
    except ImportError:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        logger.exception("Failed to construct Anthropic client")
        return None


@dataclass
class GroundingEvidence:
    bulletin_refs: tuple[str, ...] = ()
    bulletin_texts: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    policy_texts: tuple[str, ...] = ()


def _build_user_message(decision_summary: str, evidence: GroundingEvidence) -> str:
    lines = ["DỮ LIỆU:", decision_summary]
    if evidence.bulletin_texts:
        lines.append("\nBản tin thời tiết/thủy văn liên quan:")
        for ref, text in zip(evidence.bulletin_refs, evidence.bulletin_texts):
            lines.append(f"- [{ref}] {text}")
    if evidence.policy_texts:
        lines.append("\nChính sách/SOP liên quan:")
        for ref, text in zip(evidence.policy_refs, evidence.policy_texts):
            lines.append(f"- [{ref}] {text}")
    lines.append("\nViết giải thích 2-4 câu theo đúng quy tắc ở system prompt.")
    return "\n".join(lines)


def generate_grounded_explanation(
    decision_summary: str, evidence: GroundingEvidence
) -> Optional[str]:
    """Trả None nếu không thể gọi LLM (thiếu key/package/lỗi) — caller phải tự fallback."""

    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=300,
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(decision_summary, evidence)}],
        )
    except Exception:
        logger.exception("LLM grounded-explanation call failed, falling back to template")
        return None

    if response.stop_reason == "refusal":
        logger.warning("LLM refused grounded-explanation request (stop_details=%s)", response.stop_details)
        return None

    text = next((b.text for b in response.content if b.type == "text"), None)
    return text.strip() if text else None
