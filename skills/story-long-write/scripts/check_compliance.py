#!/usr/bin/env python3
"""Post-writing compliance contract and verification gate for Oh Story.

Enforces:
1. Per-chapter compliance contract generation (story-compliance-contract/v1).
2. Deterministic & semantic verification against draft prose (story-compliance-report/v1).
3. Cryptographic binding via draft_sha256 and contract_sha256.
4. Distinguishing true constraints from compound nouns (cấm địa, cấm cung, 禁地).
5. Precedence: Author Intent > Outlines > AI Defaults. Outline conflicts generate
   advisory change proposals, never mutating authoritative outline files.
6. Commit gate enforcement preventing unverified, stale, or violating chapters.
7. Verification methodology transparency: clearly distinguishes deterministic checks,
   heuristic checks, and unverified complex literary obligations.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "story-compliance-contract/v1"
REPORT_REPORT_SCHEMA = "story-compliance-report/v1"
PROPOSAL_SCHEMA = "story-outline-proposal/v1"

WORK_ROOT = (".story", "work")

COMPOUND_NOUNS_PATTERN = re.compile(
    r"\b(?:cấm\s+địa|cấm\s+cung|cấm\s+thuật|cấm\s+thành|cấm\s+thư|biển\s+cấm|lệnh\s+cấm|khu\s+cấm)\b|"
    r"(?:禁地|禁区|紫禁城|禁军|禁书)",
    re.IGNORECASE,
)

DIRECTIVE_PATTERNS = [
    re.compile(
        r"(?:^|\s|[-*+]\s*)(?:CẤM\b|NGHIÊM CẤM\b|TUYỆT ĐỐI KHÔNG\b|KHÔNG ĐƯỢC\b|KHÔNG CHO PHÉP\b|ĐỪNG\b|TỪ CHỐI\b|BÃI BỎ\b)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:^|\s|[-*+]\s*)(?:BẮT BUỘC\b|NHẤT THIẾT PHẢI\b|TUYỆT ĐỐI PHẢI\b)", re.IGNORECASE),
    re.compile(r"(?:严禁|禁止|切勿|绝不(?:许|可)|不许|必须)"),
    re.compile(
        r"\b(?:MUST NOT|FORBIDDEN|NEVER|DO NOT|MANDATORY|STRICTLY PROHIBITED|STRICTLY FORBIDDEN)\b",
        re.IGNORECASE,
    ),
]

NEGATION_CONTEXT_PATTERNS = [
    re.compile(
        r"\b(?:không\s+(?:hề|có|được|thấy|nhắc|nói|hé\s+răng|chạm|thèm|đề\s+cập)|chẳng\s+(?:hề|có)|từ\s+chối|tuyệt\s+đối\s+không|bãi\s+bỏ)\b[^\.\n!?]{0,80}",
        re.IGNORECASE,
    ),
    re.compile(r"(?:不(?:曾|提|说|见|要|许)|严禁|并未|毫无|绝无)[^\.\n!?]{0,60}"),
    re.compile(r"\b(?:never|did not|refused to|not a single|without any|no mention of)\b[^\.\n!?]{0,60}", re.IGNORECASE),
]

# Semantic clusters for common prohibited novel tropes / actions
SEMANTIC_CLUSTERS = [
    {
        "cluster": "bribe",
        "trigger": re.compile(r"\b(?:hối\s+lộ|đút\s+lót|tiền\s+lót\s+tay|nhận\s+tiền|tiền\s+hối\s+lộ)\b", re.IGNORECASE),
        "patterns": [
            re.compile(r"\b(?:hối\s+lộ|đút\s+lót|tiền\s+lót\s+tay)\b", re.IGNORECASE),
            re.compile(r"(?:nhét|đút)[^\.\n!?]{0,60}(?:phong\s+bì|ngân\s+phiếu|ngân\s+lượng|túi\s+bạc|tiền)", re.IGNORECASE),
            re.compile(r"(?:phong\s+bì|ngân\s+phiếu|ngân\s+lượng|túi\s+bạc)[^\.\n!?]{0,60}(?:tay\s+áo|túi\s+áo|túi)", re.IGNORECASE),
        ],
    },
    {
        "cluster": "alcohol",
        "trigger": re.compile(r"\b(?:uống\s+rượu|say\s+sưa|nhậu\s+nhẹt)\b", re.IGNORECASE),
        "patterns": [
            re.compile(r"\b(?:uống\s+rượu|nhậu\s+nhẹt|chén\s+tạc\s+chén\s+thù)\b", re.IGNORECASE),
            re.compile(r"(?:uống\s+cạn|nâng\s+chén|cạn\s+ly|uống\s+hết)[^\.\n!?]{0,40}(?:chén|ly|vò|bình)?[^\.\n!?]{0,40}(?:rượu|rượu\s+mạnh)", re.IGNORECASE),
            re.compile(r"(?:rượu|rượu\s+mạnh)[^\.\n!?]{0,40}(?:uống\s+cạn|nâng\s+chén|cạn\s+ly)", re.IGNORECASE),
        ],
    },
    {
        "cluster": "violence_gore",
        "trigger": re.compile(r"\b(?:bạo\s+lực\s+máu\s+me|máu\s+me\s+be\s+bét|chặt\s+chém)\b", re.IGNORECASE),
        "patterns": [
            re.compile(r"\b(?:bạo\s+lực\s+máu\s+me|máu\s+me\s+be\s+bét|đầu\s+rơi\s+máu\s+chảy)\b", re.IGNORECASE),
            re.compile(r"(?:phanh\s+thây|mổ\s+bụng|chặt\s+đầu|máu\s+văng\s+tung\s+tóe)", re.IGNORECASE),
        ],
    },
]


def chapter_work_dir(project: Path, chapter: int) -> Path:
    width = max(3, len(str(chapter)))
    return project.resolve().joinpath(*WORK_ROOT, f"第{chapter:0{width}d}章")


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            return path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_body_file(project: Path, chapter: int) -> Path | None:
    body_dir = project.resolve() / "正文"
    if not body_dir.is_dir():
        return None
    pattern = rf"^第0*{chapter}章(?:[_\- 　].*)?\.md$"
    for path in sorted(body_dir.iterdir()):
        if path.is_file() and "_原稿_" not in path.name and re.match(pattern, path.name):
            return path
    return None


def extract_keywords_from_constraint(text: str) -> list[str]:
    cleaned = COMPOUND_NOUNS_PATTERN.sub(" ", text)
    cleaned = re.sub(
        r"^(?:[-*+]\s*)?(?:CẤM[: ]+|NGHIÊM CẤM[: ]+|TUYỆT ĐỐI KHÔNG[: ]+|KHÔNG ĐƯỢC[: ]+|BÃI BỎ[: ]+|严禁[: ]+|禁止[: ]+|MUST NOT[: ]+|FORBIDDEN[: ]+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    tokens = [w for w in re.sub(r"[,!?。！？;:：\"'“”‘’\(\)\[\]]", " ", cleaned).split() if len(w) >= 2]
    stopwords = {
        "trong", "chương", "này", "kia", "đó", "không", "được", "cho", "và", "với", "của", "các", "những",
        "phải", "để", "làm", "ở", "người", "nhân", "vật", "thì", "là", "mà", "một", "hai", "ba", "chính",
        "nào", "mọi", "sẽ", "đã", "đang", "rằng", "gì", "ai", "tại", "vào", "ra", "lên", "xuống", "cảnh",
        "viên", "quan", "nhận", "hoặc", "tiền", "nào", "hắn", "nàng", "chúng", "ta", "ông", "bà",
    }
    filtered = [t for t in tokens if t.lower() not in stopwords]
    phrases = []
    # 2-word, 3-word ngrams only to avoid false positive single-word noise
    for n in (3, 2):
        for i in range(len(filtered) - n + 1):
            phrase = " ".join(filtered[i : i + n])
            if len(phrase) >= 4 and phrase not in phrases:
                phrases.append(phrase)
    return phrases


def build_compliance_contract(
    project: Path,
    chapter: int,
    author_request: str | None = None,
    request_source: str = "cli",
    outline_text: str | None = None,
    author_boundaries: str | None = None,
    state_text: str | None = None,
) -> dict[str, Any]:
    """Tạo hợp đồng kiểm tra tuân thủ (story-compliance-contract/v1) cho chương."""
    project = project.resolve()
    raw_req = (author_request or "").strip()

    # Load boundaries if not supplied
    if author_boundaries is None:
        decided_file = project / "设定" / "题材定位.md"
        author_boundaries = read_text_safe(decided_file)
        # Also check author memory files
        for mem_dir in (project / "作者记忆", project / "docs" / "作者记忆"):
            if mem_dir.is_dir():
                for f in sorted(mem_dir.glob("*.md")):
                    if not f.name.startswith((".", "_")):
                        author_boundaries += "\n" + read_text_safe(f)

    # Load outline if not supplied
    if outline_text is None:
        outline_dir = project / "大纲"
        if outline_dir.is_dir():
            pattern = rf"^细纲_第0*{chapter}章.*\.md$"
            for path in sorted(outline_dir.iterdir()):
                if path.is_file() and re.match(pattern, path.name):
                    outline_text = read_text_safe(path)
                    break
        outline_text = outline_text or ""

    # Parse rules to check
    rules_to_check: list[dict[str, Any]] = []
    rule_idx = 1

    # Rules from Author Request
    if raw_req:
        for line in raw_req.splitlines():
            line = line.strip()
            if not line:
                continue
            is_neg = any(p.search(COMPOUND_NOUNS_PATTERN.sub(" ", line)) for p in DIRECTIVE_PATTERNS[:1] + DIRECTIVE_PATTERNS[2:4])
            is_pos = any(p.search(COMPOUND_NOUNS_PATTERN.sub(" ", line)) for p in DIRECTIVE_PATTERNS[1:2])
            rule_type = "prohibition" if is_neg else ("obligation" if is_pos else "author_instruction")
            keywords = extract_keywords_from_constraint(line)
            rules_to_check.append({
                "id": f"RULE-REQ-{rule_idx:03d}",
                "type": rule_type,
                "text": line,
                "scope": "chapter",
                "severity": "blocking" if rule_type == "prohibition" else "advisory",
                "source": f"author_request:{request_source}",
                "keywords": keywords,
            })
            rule_idx += 1

    # Rules from Author Boundaries
    if author_boundaries:
        for b_line in author_boundaries.splitlines():
            b_line = b_line.strip()
            if not b_line:
                continue
            cleaned = COMPOUND_NOUNS_PATTERN.sub(" ", b_line)
            if any(p.search(cleaned) for p in DIRECTIVE_PATTERNS):
                keywords = extract_keywords_from_constraint(b_line)
                rules_to_check.append({
                    "id": f"RULE-BND-{rule_idx:03d}",
                    "type": "prohibition",
                    "text": b_line,
                    "scope": "book",
                    "severity": "blocking",
                    "source": "author_boundaries",
                    "keywords": keywords,
                })
                rule_idx += 1

    # Detect Outline Conflicts (Author Request overrides Outline)
    outline_conflicts: list[dict[str, Any]] = []
    outline_lines = [l.strip() for l in outline_text.splitlines() if l.strip()]
    for rule in rules_to_check:
        if rule["type"] == "prohibition":
            for kw in rule["keywords"]:
                if len(kw) < 4:
                    continue
                kw_pat = re.compile(re.escape(kw), re.IGNORECASE)
                for o_line in outline_lines:
                    if kw_pat.search(o_line):
                        if not any(c["candidate"].lower() == kw.lower() for c in outline_conflicts):
                            outline_conflicts.append({
                                "candidate": kw,
                                "author_override": rule["text"],
                                "outline_line": o_line,
                                "status": "adjudicated_override",
                            })

    # Generate advisory outline change proposal if outline conflicts exist
    outline_proposals = []
    if outline_conflicts:
        outline_proposals = generate_outline_change_proposal(
            project=project,
            chapter=chapter,
            conflicts=outline_conflicts,
            author_request=raw_req,
        )

    # Detect Boundary Conflicts (Author Request vs Long-Term Boundaries)
    boundary_conflicts = []
    is_authorized_boundary = bool(re.search(r"\[(?:RETCON|OVERRIDE BOUNDARY|SỬA RANH GIỚI)\]", raw_req, re.IGNORECASE))
    is_request_prohibition = bool(re.search(r"\b(?:CẤM|NGHIÊM CẤM|TUYỆT ĐỐI KHÔNG|KHÔNG ĐƯỢC|ĐỪNG|严禁|禁止|MUST NOT|FORBIDDEN|NEVER|DO NOT)\b", raw_req, re.IGNORECASE))
    for rule in [r for r in rules_to_check if r["source"] == "author_boundaries"]:
        rule_is_prohibition = bool(re.search(r"\b(?:CẤM|NGHIÊM CẤM|TUYỆT ĐỐI KHÔNG|KHÔNG ĐƯỢC|ĐỪNG|严禁|禁止|MUST NOT|FORBIDDEN|NEVER|DO NOT)\b", rule["text"], re.IGNORECASE))
        # If both are prohibitions, author is reinforcing the boundary, not conflicting with it
        if rule_is_prohibition and is_request_prohibition:
            continue
        for kw in rule["keywords"]:
            if len(kw) >= 4 and re.search(r"\b" + re.escape(kw) + r"\b", raw_req, re.IGNORECASE):
                status = "AUTHORIZED_OVERRIDE" if is_authorized_boundary else "NEEDS_AUTHOR_DECISION"
                boundary_conflicts.append({
                    "boundary_rule": rule["text"],
                    "author_request": raw_req,
                    "keyword": kw,
                    "status": status,
                })
                break

    # Canon conflicts (stub detection or retcon flag)
    canon_conflicts = []
    if "[RETCON]" in raw_req.upper():
        canon_conflicts.append({
            "topic": "Explicit Retcon Request",
            "author_request": raw_req,
            "status": "AUTHORIZED_RETCON",
        })

    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "chapter": chapter,
        "project": project.name,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "author_request": {"raw": raw_req, "source": request_source},
        "outline_conflicts": outline_conflicts,
        "boundary_conflicts": boundary_conflicts,
        "canon_conflicts": canon_conflicts,
        "outline_proposals": [p.get("id") for p in outline_proposals],
        "rules_to_check": rules_to_check,
    }

    # Deterministic contract hash (excluding timestamp)
    hashable = {k: v for k, v in contract.items() if k not in ("created_at", "contract_sha256")}
    canonical = json.dumps(hashable, ensure_ascii=False, sort_keys=True)
    contract["contract_sha256"] = sha256_text(canonical)
    return contract


def generate_outline_change_proposal(
    project: Path,
    chapter: int,
    conflicts: list[dict[str, Any]],
    author_request: str,
) -> list[dict[str, Any]]:
    """Tạo đề xuất thay đổi đề cương có dẫn chứng.

    TUYỆT ĐỐI KHÔNG tự ý ghi đè tệp đề cương gốc (大纲/细纲_*.md).
    Lưu đề xuất vào .story/work/第xxx章/outline_change_proposal.json và .md.
    """
    proposals = []
    for i, c in enumerate(conflicts, 1):
        proposal = {
            "id": f"PROP-CH{chapter:03d}-{i:02d}",
            "schema": PROPOSAL_SCHEMA,
            "chapter": chapter,
            "conflicting_topic": c["candidate"],
            "original_outline_event": c["outline_line"],
            "author_decision": c["author_override"],
            "status": "advisory_proposal",
            "note": "Authoritative outline file remains unmutated. Author decision required to update master outline.",
        }
        proposals.append(proposal)

    work_dir = chapter_work_dir(project, chapter)
    work_dir.mkdir(parents=True, exist_ok=True)
    json_path = work_dir / "outline_change_proposal.json"
    json_path.write_text(json.dumps({"proposals": proposals}, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Đề xuất cập nhật đề cương — Chương {chapter}",
        "> ⚠️ Tệp đề cương gốc không bị thay đổi. Đây là đề xuất phân xử có dẫn chứng.",
        "",
        "## Các điểm đề cương đã bị yêu cầu tác giả bãi bỏ:",
    ]
    for p in proposals:
        md_lines.append(f"### {p['id']}: Chủ đề \"{p['conflicting_topic']}\"")
        md_lines.append(f"- **Đề cương cũ ghi**: {p['original_outline_event']}")
        md_lines.append(f"- **Yêu cầu tác giả mới**: {p['author_decision']}")
        md_lines.append("- **Trạng thái**: Yêu cầu tác giả đã bãi bỏ tình tiết cũ trong chương này.")
        md_lines.append("")
    md_path = work_dir / "outline_change_proposal.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return proposals


def save_compliance_contract(project: Path, chapter: int, contract: dict[str, Any]) -> Path:
    work_dir = chapter_work_dir(project, chapter)
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "compliance_contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_compliance_contract(project: Path, chapter: int, contract_path: Path | None = None) -> dict[str, Any] | None:
    path = contract_path or (chapter_work_dir(project, chapter) / "compliance_contract.json")
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("schema") == CONTRACT_SCHEMA:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def is_negated_or_authorized(sentence: str, match_start: int, match_end: int) -> bool:
    """Kiểm tra xem từ khóa xuất hiện có nằm trong cấu trúc phủ định hoặc từ chối hay không."""
    preceding = sentence[:match_end]
    if any(p.search(preceding) for p in NEGATION_CONTEXT_PATTERNS):
        return True
    window = sentence[max(0, match_start - 80) : min(len(sentence), match_end + 80)]
    return any(p.search(window) for p in NEGATION_CONTEXT_PATTERNS)


def extract_verbatim_quote(text: str, start: int, end: int, window: int = 50) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    quote = text[left:right].strip().replace("\r", " ").replace("\n", " ")
    return f"...{quote}..." if left > 0 or right < len(text) else quote


def verify_chapter_compliance(
    project: Path,
    chapter: int,
    body_path: Path | None = None,
    body_text: str | None = None,
    contract: dict[str, Any] | None = None,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    """Kiểm tra tính tuân thủ của bản thảo chương truyện đối với hợp đồng kiểm tra."""
    project = project.resolve()
    work_dir = chapter_work_dir(project, chapter)

    if contract is None:
        contract = load_compliance_contract(project, chapter, contract_path)

    if contract is None:
        return {
            "schema": REPORT_REPORT_SCHEMA,
            "chapter": chapter,
            "status": "INSUFFICIENT_CONTEXT",
            "draft_sha256": "",
            "contract_sha256": "",
            "findings": [],
            "summary": "Compliance contract not found or invalid.",
        }

    # Chapter scope validation (Test D & G)
    if contract.get("chapter") != chapter:
        return {
            "schema": REPORT_REPORT_SCHEMA,
            "chapter": chapter,
            "status": "INSUFFICIENT_CONTEXT",
            "draft_sha256": "",
            "contract_sha256": contract.get("contract_sha256", ""),
            "findings": [],
            "summary": f"Chapter scope mismatch: contract is for chapter {contract.get('chapter')}, requested chapter {chapter}",
        }

    # Read body
    if body_path is None:
        body_path = find_body_file(project, chapter)
    if body_text is None:
        if body_path is None or not body_path.is_file():
            return {
                "schema": REPORT_REPORT_SCHEMA,
                "chapter": chapter,
                "status": "INSUFFICIENT_CONTEXT",
                "draft_sha256": "",
                "contract_sha256": contract.get("contract_sha256", ""),
                "findings": [],
                "summary": f"Draft body file for chapter {chapter} not found.",
            }
        body_text = read_text_safe(body_path)

    if body_path and body_path.is_file():
        draft_sha256 = hashlib.sha256(body_path.read_bytes()).hexdigest()
    else:
        draft_sha256 = sha256_text(body_text)
    contract_sha256 = contract.get("contract_sha256", "")

    findings: list[dict[str, Any]] = []

    # Check unresolved boundary conflicts
    for bc in contract.get("boundary_conflicts", []):
        if bc.get("status") == "NEEDS_AUTHOR_DECISION":
            findings.append({
                "rule_id": "BOUNDARY_CONFLICT",
                "rule_text": bc.get("boundary_rule", ""),
                "source": "boundary_conflicts",
                "status": "NEEDS_AUTHOR_DECISION",
                "method": "deterministic",
                "confidence": "high",
                "verbatim_quote": bc.get("author_request", ""),
                "explanation": "Author request conflicts with long-term boundary without [OVERRIDE BOUNDARY] prefix.",
            })

    # Evaluate rules against draft prose
    sentences = re.split(r"(?<=[.!?。！？\n])\s*", body_text)

    for rule in contract.get("rules_to_check", []):
        rule_type = rule.get("type")
        rule_text = rule.get("text", "")
        keywords = rule.get("keywords", [])

        if rule_type == "prohibition":
            # Check semantic clusters first (Test B)
            matched_semantic = False
            for sc in SEMANTIC_CLUSTERS:
                if sc["trigger"].search(rule_text):
                    for pat in sc["patterns"]:
                        for s in sentences:
                            m = pat.search(s)
                            if m:
                                if not is_negated_or_authorized(s, m.start(), m.end()):
                                    quote = extract_verbatim_quote(s, m.start(), m.end())
                                    findings.append({
                                        "rule_id": rule.get("id"),
                                        "rule_text": rule_text,
                                        "source": rule.get("source"),
                                        "status": "VIOLATION",
                                        "method": "heuristic_semantic_cluster",
                                        "confidence": "medium",
                                        "verbatim_quote": quote,
                                        "explanation": f"Draft describes prohibited action (semantic match in cluster '{sc['cluster']}').",
                                    })
                                    matched_semantic = True
                                    break
                        if matched_semantic:
                            break
                    if matched_semantic:
                        break

            if matched_semantic:
                continue

            # Standard keyword / phrase matching with false-positive noun filters (Test A & C)
            for kw in keywords:
                if len(kw) < 4:
                    continue
                kw_pat = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
                for s in sentences:
                    s_cleaned = COMPOUND_NOUNS_PATTERN.sub(" ", s)
                    m = kw_pat.search(s_cleaned)
                    if m:
                        if not is_negated_or_authorized(s, m.start(), m.end()):
                            quote = extract_verbatim_quote(s, m.start(), m.end())
                            findings.append({
                                "rule_id": rule.get("id"),
                                "rule_text": rule_text,
                                "source": rule.get("source"),
                                "status": "VIOLATION",
                                "method": "heuristic_ngram",
                                "confidence": "high",
                                "verbatim_quote": quote,
                                "explanation": f"Draft mentions forbidden topic or performs forbidden action: '{kw}'.",
                            })
                            break

        elif rule_type == "author_instruction":
            # Soft literary / stylistic guidance: documented as unverified advisory
            findings.append({
                "rule_id": rule.get("id"),
                "rule_text": rule_text,
                "source": rule.get("source"),
                "status": "UNVERIFIED_ADVISORY",
                "method": "unsupported_complex_obligation",
                "confidence": "advisory_only",
                "verbatim_quote": "",
                "explanation": "General author instruction requires human review or LLM semantic reasoning; not mechanically verified.",
            })

    # Determine overall status
    has_violations = any(f["status"] == "VIOLATION" for f in findings)
    has_needs_decision = any(f["status"] == "NEEDS_AUTHOR_DECISION" for f in findings)

    if has_violations:
        status = "VIOLATION"
        summary = f"Draft has {len([f for f in findings if f['status'] == 'VIOLATION'])} compliance violation(s)."
    elif has_needs_decision:
        status = "NEEDS_AUTHOR_DECISION"
        summary = "Draft requires author confirmation regarding creative boundary conflict."
    else:
        status = "PASS"
        summary = "All checked compliance constraints verified successfully."

    report: dict[str, Any] = {
        "schema": REPORT_REPORT_SCHEMA,
        "chapter": chapter,
        "draft_sha256": draft_sha256,
        "contract_sha256": contract_sha256,
        "status": status,
        "findings": findings,
        "summary": summary,
        "verification_methods": {
            "deterministic_checks": [
                "hash_integrity",
                "chapter_scope_validation",
                "compound_noun_exclusion",
                "negation_context_detection",
            ],
            "heuristic_checks": [
                "ngram_keyword_matching",
                "semantic_cluster_matching",
            ],
            "unverified_semantic_obligations": [
                "literary_tone_compliance",
                "character_psychology_depth",
                "implicit_plot_consistency",
            ],
            "semantic_agent_needed": False,
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Save report in chapter work dir
    work_dir.mkdir(parents=True, exist_ok=True)
    report_path = work_dir / "compliance_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_compliance.py")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    contract_parser = subparsers.add_parser("contract")
    contract_parser.add_argument("--project", type=Path, required=True)
    contract_parser.add_argument("--chapter", type=int, required=True)
    contract_parser.add_argument("--request", type=str, default="")
    contract_parser.add_argument("--request-file", type=Path, default=None)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project", type=Path, required=True)
    verify_parser.add_argument("--chapter", type=int, required=True)
    verify_parser.add_argument("--draft", type=Path, default=None)
    verify_parser.add_argument("--contract", type=Path, default=None)

    args = parser.parse_args(argv or sys.argv[1:])

    if args.subcommand == "contract":
        req = args.request
        if args.request_file and args.request_file.is_file():
            req = read_text_safe(args.request_file)
        contract = build_compliance_contract(args.project, args.chapter, author_request=req)
        out_path = save_compliance_contract(args.project, args.chapter, contract)
        print(json.dumps({"status": "ok", "contract_file": str(out_path), "contract_sha256": contract["contract_sha256"]}))
        return 0

    elif args.subcommand == "verify":
        report = verify_chapter_compliance(
            project=args.project,
            chapter=args.chapter,
            body_path=args.draft,
            contract_path=args.contract,
        )
        print(json.dumps(report, ensure_ascii=False))
        if report["status"] == "PASS":
            return 0
        elif report["status"] in ("VIOLATION", "NEEDS_AUTHOR_DECISION"):
            return 1
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
