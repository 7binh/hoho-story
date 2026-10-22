#!/usr/bin/env python3

"""Comprehensive Regression & Hardening Test Suite for Long-Form Memory & Continuity (Phase 4).

Covers:

- Test 1: Distant chapter detail recall across the 3-chapter window.

- Test 2: Character-isolated private knowledge & negative knowledge boundaries.

- Test 3: Item location & possession state transitions across chapters.

- Test 4: Cross-chapter causality & unfulfilled commitments carried forward.

- Test 5: Distinct canon vs outline intent (detecting when old outline contradicts committed canon).

- Test 6: Summary drift & false canon detection (preventing hallucinated summaries from corrupting state).

- Test 7: Outline richness vs writer context delivery (delivering dialogue anchors, scene access, and boundaries).

- Test 8: False belief vs objective canon (isolating subjective character beliefs from objective facts).

"""

from __future__ import annotations

import hashlib

import json

import os

import shutil

import subprocess

import sys

import tempfile

import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPTS = ROOT / "skills/story-long-write/scripts"

sys.path.insert(0, str(SCRIPTS))

import tracking_commit  # type: ignore

import storyctl  # type: ignore

import build_writer_prompt  # type: ignore

class ContinuityMemoryTests(unittest.TestCase):

    def setUp(self) -> None:

        self.tmp = tempfile.TemporaryDirectory(prefix="continuity-memory-")

        self.addCleanup(self.tmp.cleanup)

        self.book = (Path(self.tmp.name) / "TestStory").resolve()

        self.book.mkdir(parents=True, exist_ok=True)

    def put(self, relative_path: str, content: str) -> Path:

        file_path = self.book / relative_path

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")

        return file_path

    def setup_baseline_book(self) -> None:

        """Create standard book files required by build_writer_prompt and tracking."""

        self.put("设定/文风.md", "# 文风\nVăn phong chuẩn mực, tự nhiên, nhịp điệu gãy gọn.\n" * 5)

        self.put("设定/题材定位.md", "## 作者已定\n- Ranh giới: Không viết truyện phản cảm.\n")

        self.put("设定/题材正文提示卡.md", "# 题材卡\nGiữ vững cốt truyện.\n")

        self.put(

            "大纲/卷纲_第一卷.md",

            "# 第一卷\n"

            "## 卷契约\nThử thách đầu đời.\n"

            "### 剧情单元 U1\n"

            "- 章节范围：第1-10章\n"

            "- 单元情绪引擎：Căng thẳng → Thư giãn\n"

            "- 单元节拍/章功能分配：Khám phá bí mật\n"

        )

        headings = ["当前位置", "长期约束", "核心角色状态", "活跃伏笔", "近三章速记", "下一章承诺", "连贯性风险"]

        context_body = "\n".join("## " + h + "\n无\n" for h in headings)

        self.put("追踪/上下文.md", context_body)

    def test_01_distant_chapter_detail_recall(self) -> None:

        """Test 1: Distant detail from Chapter 1 must be retrieved in Chapter 6 despite 3-chapter window."""

        self.setup_baseline_book()

        # Initialize tracking state with Chapter 1 hidden item

        init_doc = {

            "schema_version": 1,

            "book_title": "TestStory",

            "last_chapter": 0,

            "context": {

                "position": {

                    "volume": "第一卷",

                    "volume_start_chapter": 1,

                    "story_time": "Ngày 1",

                    "scene": "Phòng ngủ",

                },

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu gia",

                    "location": "Phòng ngủ",

                    "goal": "Tìm bảo vật",

                    "state": "Bình thường",

                    "abilities_resources": [],

                    "relationships": [],

                    "knowledge": [],

                    "open_threads": [],

                }

            },

            "foreshadow": [],

            "timeline_events": [],

        }

        tracking_commit.initialize(self.book, init_doc)

        # Commit Chapter 1 recording the hidden box

        # Chapters 1-5 committed, so Chapter 1 is evicted from recent_chapters (only last 3 kept)

        state_file = self.book / "追踪" / "_tracking-state.json"

        state = json.loads(state_file.read_text(encoding="utf-8"))

        state["last_committed_chapter"] = 5

        state["context"]["recent_chapters"] = [

            {"chapter": 3, "summary": "Chương 3 diễn biến tiếp."},

            {"chapter": 4, "summary": "Chương 4 diễn biến tiếp."},

            {"chapter": 5, "summary": "Chương 5 diễn biến tiếp."},

        ]

        # Distant timeline fact from Chapter 1

        state["timeline"]["E001"] = {

            "id": "E001",

            "first_recorded_chapter": 1,

            "updated_chapter": 1,

            "story_time": "Đêm ngày 1",

            "objective_fact": "Phong đã giấu chiếc hộp gỗ mun chứa bức thư của cha ở dưới ván sàn phòng ngủ.",

            "reader_knowledge": "Phong cất giấu chiếc hộp gỗ mun dưới sàn nhà.",

            "reveal_status": "已揭示",

            "reveal_chapter": 1,

            "characters": ["Phong"],

        }

        # Item registry

        state["items"] = {

            "chiếc hộp gỗ mun": {

                "name": "chiếc hộp gỗ mun",

                "holder": None,

                "location": "dưới ván sàn phòng ngủ",

                "status": "nguyên vẹn",

                "origin_chapter": 1,

                "updated_chapter": 1,

                "description": "chứa bức thư của cha",

            }

        }

        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # Regenerate views

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        # Previous chapter (Chapter 5) text

        self.put("正文/第005章_Hoi_ngo.md", "# 第 5 章\n" + "Phong đứng bên cửa sổ suy ngẫm.\n" * 15)

        # Chapter 6 outline mentions retrieving the box

        self.put(

            "大纲/细纲_第006章.md",

            "### 第 6 章：Bảo vật gia truyền\n"

            "- 核心事件：Phong quay trở lại phòng ngủ, cạy ván sàn để lấy lại chiếc hộp gỗ mun.\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Hồi hộp → Quyết tâm\n"

            "- 主角目标/关键选择：Lấy lại kỷ vật của cha\n"

        )

        # Run build_writer_prompt for Chapter 6

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 6, report)

        self.assertEqual(errors, [])

        self.assertIsNotNone(prompt)

        # Verify: Prompt MUST recall the Chapter 1 location ("dưới ván sàn phòng ngủ")

        self.assertIn("chiếc hộp gỗ mun", prompt)

        self.assertIn("dưới ván sàn phòng ngủ", prompt)

    def test_02_character_isolated_private_knowledge(self) -> None:

        """Test 2: Private secret between A and B must not be leaked to C in scene."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 2,

            "imported_through_chapter": 0,

            "state_revision": 2,

            "context": {

                "position": {

                    "volume": "第一卷",

                    "volume_start_chapter": 1,

                    "story_time": "Ngày 3",

                    "scene": "Quán trà",

                },

                "long_term_constraints": [],

                "active_character_names": ["Phong", "Bảo"],

                "continuity_risks": [],

                "recent_chapters": [

                    {"chapter": 1, "summary": "Chương 1 mở đầu."},

                    {"chapter": 2, "summary": "Phong và An bí mật bàn chuyện."},

                ],

                "next_chapter_commitments": [],

            },

            "characters": {

                "Phong": {

                    "identity": "Thiếu gia",

                    "location": "Quán trà",

                    "goal": "Thăm dò Bảo",

                    "state": "Cảnh giác",

                    "abilities_resources": [],

                    "relationships": [],

                    "knowledge": ["An từng làm việc cho tập đoàn Hắc Long"],

                    "open_threads": [],

                },

                "Bảo": {

                    "identity": "Bạn học",

                    "location": "Quán trà",

                    "goal": "Uống trà",

                    "state": "Vô tư",

                    "abilities_resources": [],

                    "relationships": [],

                    "knowledge": [],

                    "unaware": ["An từng làm việc cho tập đoàn Hắc Long"],

                    "open_threads": [],

                },

            },

            "foreshadow": {},

            "timeline": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第002章_Mat_dam.md", "# 第 2 章\n" + "An thì thầm vào tai Phong về Hắc Long.\n" * 15)

        # Chapter 3 outline has Phong and Bao in the teahouse

        self.put(

            "大纲/细纲_第003章.md",

            "### 第 3 章：Uống trà đàm đạo\n"

            "- 核心事件：Phong gặp Bảo ở quán trà, trò chuyện về tình hình phố thị.\n"

            "- 人物出场顺序：Phong, Bảo\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Thư thái nhưng dò xét\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 3, report)

        self.assertEqual(errors, [])

        # Verify: Prompt MUST enforce character knowledge boundary for Bảo

        self.assertIn("Bảo", prompt)

        self.assertIn("KHÔNG BIẾT", prompt)

        self.assertIn("Hắc Long", prompt)

    def test_03_item_location_and_possession_transitions(self) -> None:

        """Test 3: Item possession transition (Phong -> An -> Lost in river) tracked accurately."""

        self.setup_baseline_book()

        self.put(

            "大纲/细纲_第001章.md",

            "- 字数目标：2000 字\n"

            "- 字数口径：visible_chars_v1\n"

            "### 第 1 章：Nhận ngọc\n",

        )

        self.put("正文/第001章_Nhan_ngoc.md", "# 第 1 章\n<!-- 去味:跳过 -->\n" + "Phong nhận ngọc bội gia truyền trước sảnh đường。\n" * 48)

        init_doc = {

            "schema_version": 1,

            "book_title": "TestStory",

            "last_chapter": 0,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Phủ"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Phủ", "goal": "Bảo vệ ngọc bội", "state": "Khỏe",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

            "foreshadow": [],

            "timeline_events": [],

        }

        state = tracking_commit.initialize(self.book, init_doc)

        # Chapter 1: Phong has jade

        tx1 = {

            "schema_version": 1,

            "mode": "append",

            "chapter": 1,

            "chapter_title": "Nhận ngọc",

            "expected_state_revision": 0,

            "delta": {

                "result": "Phong nhận Ngọc bội Long Phượng từ gia tộc.",

                "character_changes": [{"name": "Phong", "change": "Mang theo ngọc bội"}],

                "foreshadow_changes": [],

                "timeline_events": [],

                "constraints": [],

                "next_chapter_commitments": [],

                "retired_context_items": [],

                "retired_characters": [],

                "item_changes": [

                    {

                        "action": "upsert",

                        "name": "Ngọc bội Long Phượng",

                        "holder": "Phong",

                        "location": "trên người Phong",

                        "status": "nguyên vẹn",

                        "description": "Bảo vật gia truyền",

                    }

                ],

            },

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Phủ"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Phủ", "goal": "Bảo vệ ngọc bội", "state": "Khỏe",

                    "abilities_resources": ["Ngọc bội Long Phượng"], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

        }

        tx1["wordcount"] = storyctl.build_project_wordcount_record(self.book, 1, resolution="within_user_band")

        state = tracking_commit.apply_transaction(self.book, tx1)

        self.assertEqual(state["items"]["Ngọc bội Long Phượng"]["holder"], "Phong")

        # Chapter 2: Phong hands jade to An, An drops it into the river

        self.put(

            "大纲/细纲_第002章.md",

            "- 字数目标：2000 字\n"

            "- 字数口径：visible_chars_v1\n"

            "### 第 2 章：Đánh mất\n",

        )

        self.put("正文/第002章_Danh_mat.md", "# 第 2 章\n<!-- 去味:跳过 -->\n" + "Ngọc bội chìm sâu xuống đáy hồ lạnh lẽo。\n" * 60)

        tx2 = {

            "schema_version": 1,

            "mode": "append",

            "chapter": 2,

            "chapter_title": "Đánh mất",

            "expected_state_revision": 1,

            "delta": {

                "result": "An sơ ý làm rơi Ngọc bội Long Phượng xuống đáy hồ Vọng Nguyệt.",

                "character_changes": [

                    {"name": "Phong", "change": "Giao ngọc cho An"},

                    {"name": "An", "change": "Đánh rơi ngọc xuống hồ"},

                ],

                "foreshadow_changes": [],

                "timeline_events": [],

                "constraints": [],

                "next_chapter_commitments": [],

                "retired_context_items": [],

                "retired_characters": [],

                "item_changes": [

                    {

                        "action": "upsert",

                        "name": "Ngọc bội Long Phượng",

                        "holder": None,

                        "location": "đáy hồ Vọng Nguyệt",

                        "status": "thất lạc",

                        "description": "Bảo vật gia truyền đã chìm",

                    }

                ],

            },

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 2", "scene": "Hồ Vọng Nguyệt"},

                "long_term_constraints": [],

                "active_character_names": ["Phong", "An"],

                "continuity_risks": ["Ngọc bội Long Phượng đã thất lạc dưới hồ"],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Hồ", "goal": "Tìm ngọc", "state": "Lo lắng",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                },

                "An": {

                    "identity": "Sư muội", "location": "Hồ", "goal": "Tạ lỗi", "state": "Hối hận",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                },

            },

        }

        tx2["wordcount"] = storyctl.build_project_wordcount_record(self.book, 2, resolution="within_user_band")

        state = tracking_commit.apply_transaction(self.book, tx2)

        # Verify item state after Chapter 2

        item = state["items"]["Ngọc bội Long Phượng"]

        self.assertIsNone(item["holder"])

        self.assertEqual(item["location"], "đáy hồ Vọng Nguyệt")

        self.assertEqual(item["status"], "thất lạc")

    def test_04_cross_chapter_causality_and_unfulfilled_commitments(self) -> None:

        """Test 4: Unfulfilled commitments carry forward across chapters with escalation warning."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 3,

            "imported_through_chapter": 0,

            "state_revision": 3,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 4", "scene": "Rừng trúc"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [

                    {"chapter": 1, "summary": "Chương 1"},

                    {"chapter": 2, "summary": "Chương 2"},

                    {"chapter": 3, "summary": "Chương 3"},

                ],

                "next_chapter_commitments": ["Đưa linh dược cho Lão Khôi trước giờ Ngọ"],

            },

            "characters": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Rừng trúc", "goal": "Chạy trốn", "state": "Mệt mỏi",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

            "unfulfilled_commitments": [

                {

                    "id": "C001",

                    "commitment": "Trả lời tối hậu thư của bang Cự Lộ",

                    "origin_chapter": 2,

                    "deadline_chapter": 3,

                    "status": "pending",

                }

            ],

            "foreshadow": {},

            "timeline": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第003章_Chay_tron.md", "# 第 3 章\n" + "Phong bị truy sát trong rừng trúc suốt cả ngày.\n" * 15)

        # Chapter 4 outline

        self.put(

            "大纲/细纲_第004章.md",

            "### 第 4 章：Gặp lại Lão Khôi\n"

            "- 核心事件：Phong đến gặp Lão Khôi để trao đổi tin tức.\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Căng thẳng\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 4, report)

        self.assertEqual(errors, [])

        # Verify: Prompt MUST surface unfulfilled commitment from Chapter 2 as a continuity alert

        self.assertIn("tối hậu thư của bang Cự Lộ", prompt)

        self.assertIn("CẢNH BÁO NỢ TÌNH TIẾT", prompt)

    def test_05_distinct_canon_vs_outline_intent(self) -> None:

        """Test 5: Detect when outline assumes unexecuted/cut plan instead of committed canon."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 2,

            "imported_through_chapter": 0,

            "state_revision": 2,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 3", "scene": "Phòng kín"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [

                    {"chapter": 1, "summary": "Chương 1"},

                    {"chapter": 2, "summary": "Phong giấu bản giao kèo vào trong áo, kiên quyết không đốt."},

                ],

                "next_chapter_commitments": [],

            },

            "characters": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Phòng kín", "goal": "Bảo vệ chứng cứ", "state": "Khỏe",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

            "timeline": {

                "E002": {

                    "id": "E002",

                    "first_recorded_chapter": 2,

                    "updated_chapter": 2,

                    "story_time": "Ngày 2",

                    "objective_fact": "Phong không đốt bản giao kèo mà giấu kỹ trong lớp áo lót.",

                    "reader_knowledge": "Bản giao kèo vẫn còn nguyên vẹn trong người Phong.",

                    "reveal_status": "已揭示",

                    "reveal_chapter": 2,

                    "characters": ["Phong"],

                }

            },

            "foreshadow": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第002章_Luu_lai_chung_cu.md", "# 第 2 章\n" + "Phong nhét bản giao kèo vào ngực áo.\n" * 15)

        # Chapter 3 outline was written based on the old unexecuted plan (assuming contract was burned)

        self.put(

            "大纲/细纲_第003章.md",

            "### 第 3 章：Không còn chứng cứ\n"

            "- 核心事件：Vì bản giao kèo đã bị đốt ở chương trước, Phong không thể chứng minh sự vô tội trước công đường.\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Bất lực\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 3, report)

        self.assertEqual(errors, [])

        # Verify: Prompt MUST flag CANON-OUTLINE CONFLICT

        self.assertIn("CANON-OUTLINE CONFLICT", prompt)

        self.assertIn("bản giao kèo", prompt)

    def test_06_summary_drift_detection(self) -> None:

        """Test 6: Refuse commit when tracking delta summary directly contradicts draft prose."""

        self.setup_baseline_book()

        self.put(

            "大纲/细纲_第001章.md",

            "- 字数目标：1000 字\n"

            "- 字数口径：visible_chars_v1\n"

            "### 第 1 章：Đối mặt thương hội\n"

            "| # | 情节点 | 功能标签 | 执行边界 |\n"

            "|---|---|---|---|\n"

            "| 1 | Phong gặp thương hội | 推进 | Không nhượng bộ |\n"

        )

        init_doc = {

            "schema_version": 1,

            "book_title": "TestStory",

            "last_chapter": 0,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Phòng họp"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Phòng họp", "goal": "Từ chối ký", "state": "Cương quyết",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

            "foreshadow": [],

            "timeline_events": [],

        }

        tracking_commit.initialize(self.book, init_doc)

        # Actual draft prose: Phong refused to sign

        draft_lines = [f"Phong kiên quyết từ chối ký tên vào bản thỏa thuận lần thứ {i:02d}。\n" for i in range(1, 22)]

        draft_text = "# 第 1 章\n<!-- 去味:跳过 -->\n" + "".join(draft_lines)

        draft_file = self.put("正文/第001章_Doi_mat_thuong_hoi.md", draft_text)

        # Compliance contract & report (valid PASS)

        work_dir = self.book / ".story" / "work" / "第001章"

        work_dir.mkdir(parents=True, exist_ok=True)

        contract = {

            "schema": "story-compliance-contract/v1",

            "chapter": 1,

            "author_rules": [],

            "contract_sha256": "dummy",

        }

        contract_hash = hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

        contract["contract_sha256"] = contract_hash

        (work_dir / "compliance_contract.json").write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")

        draft_bytes = draft_file.read_bytes()

        draft_hash = hashlib.sha256(draft_bytes).hexdigest()

        report = {

            "schema": "story-compliance-report/v1",

            "chapter": 1,

            "status": "PASS",

            "findings": [],

            "contract_sha256": contract_hash,

            "draft_sha256": draft_hash,

        }

        (work_dir / "compliance_report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        # Proposed transaction with hallucinated summary: claims Phong signed successfully!

        tx = {

            "schema_version": 1,

            "mode": "append",

            "chapter": 1,

            "chapter_title": "Đối mặt thương hội",

            "expected_state_revision": 0,

            "delta": {

                "result": "Phong đã ký kết thành công bản thỏa thuận với hội thương gia.",  # Direct contradiction!

                "character_changes": [{"name": "Phong", "change": "Đã ký thỏa thuận"}],

                "foreshadow_changes": [],

                "timeline_events": [],

                "constraints": [],

                "next_chapter_commitments": [],

                "retired_context_items": [],

                "retired_characters": [],

            },

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Phòng họp"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

            },

            "character_snapshots": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Phòng họp", "goal": "Từ chối ký", "state": "Cương quyết",

                    "abilities_resources": [], "relationships": [], "knowledge": [], "open_threads": [],

                }

            },

        }

        tx_path = work_dir / "tracking.json"

        tx_path.write_text(json.dumps(tx, ensure_ascii=False), encoding="utf-8")

        # storyctl chapter commit MUST reject with SUMMARY_DRIFT_DETECTED

        with self.assertRaises(storyctl.ChapterRefused) as ctx:

            storyctl.chapter_commit(self.book, 1, tx_path, accept_current_length=False)

        self.assertEqual(ctx.exception.code, "SUMMARY_DRIFT_DETECTED")

    def test_07_outline_richness_delivery_to_writer_prompt(self) -> None:

        """Test 7: Dialogue anchors, scene access, and execution boundaries reach writer prompt."""

        self.setup_baseline_book()

        self.put(

            "大纲/细纲_第005章.md",

            "### 第 5 章：Quyết tử trước cổng thành\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Bi tráng → Hào sảng\n"

            "- 复沓锚句：\"Ta không bán kiếm, ta bán mạng.\"\n"

            "- 镜头准入：Chỉ Phong và Lão Khôi được thoại; các đệ tử khác chỉ hành động không lời.\n"

            "- 执行边界：Tuyệt đối không rút kiếm khỏi vỏ trước khi có hiệu lệnh.\n"

        )

        self.put("正文/第004章_Truoc_gio_G.md", "# 第 4 章\n" + "Mọi người tập trung trước cổng thành.\n" * 15)

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 5, report)

        self.assertEqual(errors, [])

        # Verify: Prompt MUST explicitly contain the rich constraints

        self.assertIn("Ta không bán kiếm, ta bán mạng.", prompt)

        self.assertIn("Chỉ Phong và Lão Khôi được thoại", prompt)

        self.assertIn("Tuyệt đối không rút kiếm khỏi vỏ", prompt)

    def test_08_false_belief_vs_objective_canon(self) -> None:

        """Test 8: Distinguish subjective character suspicion from objective canon truth."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 2,

            "imported_through_chapter": 0,

            "state_revision": 2,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 3", "scene": "Đại điện"},

                "long_term_constraints": [],

                "active_character_names": ["Phong", "Bảo"],

                "continuity_risks": [],

                "recent_chapters": [

                    {"chapter": 1, "summary": "Chương 1"},

                    {"chapter": 2, "summary": "Phong phát hiện manh mối thích khách."},

                ],

                "next_chapter_commitments": [],

            },

            "characters": {

                "Phong": {

                    "identity": "Đội trưởng thị vệ", "location": "Đại điện", "goal": "Tìm thích khách", "state": "Căng thẳng",

                    "abilities_resources": [], "relationships": [], "knowledge": [],

                    "beliefs": ["Bảo là kẻ phản bội đã mở cổng thành"],  # Subjective suspicion!

                    "open_threads": [],

                },

                "Bảo": {

                    "identity": "Thị vệ", "location": "Đại điện", "goal": "Thực hiện nhiệm vụ", "state": "Bình thường",

                    "abilities_resources": [], "relationships": [], "knowledge": [],

                    "open_threads": [],

                },

            },

            "timeline": {

                "E010": {

                    "id": "E010",

                    "first_recorded_chapter": 2,

                    "updated_chapter": 2,

                    "story_time": "Đêm ngày 2",

                    "objective_fact": "Bảo hoàn toàn vô tội; thích khách thực sự là cận vệ Hắc Y.",

                    "reader_knowledge": "Người đọc đã thấy bóng dáng cận vệ Hắc Y mở cổng.",

                    "reveal_status": "未揭示",

                    "reveal_chapter": None,

                    "characters": ["Bảo"],

                }

            },

            "foreshadow": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第002章_Manh_moi.md", "# 第 2 章\n" + "Phong nhìn thấy chiếc khăn rơi gần chỗ Bảo.\n" * 15)

        # Chapter 3 outline

        self.put(

            "大纲/细纲_第003章.md",

            "### 第 3 章：Đối chất trong đêm\n"

            "- 核心事件：Phong âm thầm theo dõi và đối chất với Bảo về vụ mở cổng thành.\n"

            "- 人物出场顺序：Phong, Bảo\n"

            "- 单元ID/位置：U1\n"

            "- 目标情绪：Nghi kỵ dâng cao\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 3, report)

        self.assertEqual(errors, [])

        # Verify: Prompt MUST clarify that Phong's suspicion is subjective and NOT objective truth

        self.assertIn("NHẬN THỨC CHỦ QUAN", prompt)

        self.assertIn("Bảo là kẻ phản bội", prompt)

        self.assertIn("KHÔNG PHẢI sự thật khách quan", prompt)

    def test_09_epistemic_tri_state_distinction(self) -> None:

        """Test 9: Epistemic Tri-State: Confirmed known, confirmed unknown, and unspecified."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 2,

            "imported_through_chapter": 0,

            "state_revision": 2,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 3", "scene": "Mật thất"},

                "long_term_constraints": [],

                "active_character_names": ["Phong"],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "characters": {

                "Phong": {

                    "identity": "Thiếu hiệp", "location": "Mật thất", "goal": "Điều tra bí mật", "state": "Tỉnh táo",

                    "abilities_resources": [], "relationships": [],

                    "knowledge": ["Gia tộc từng có một vị lão tổ tu vi Đại Thừa"],  # Confirmed known

                    "unaware": ["Thân phận thực sự của Viện trưởng là thúc phụ của mình"],  # Confirmed unknown (blind spot)

                    "beliefs": ["Có người nội gián trong thư viện"],  # Subjective suspicion

                    "open_threads": [],

                }

            },

            "timeline": {},

            "foreshadow": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第002章_Mat_that.md", "# 第 2 章\n" + "Phong bước vào mật thất âm u.\n" * 15)

        # Chapter 3 outline involves Phong

        self.put(

            "大纲/细纲_第003章.md",

            "### 第 3 章：Thử thách thư viện\n"

            "- 人物出场顺序：Phong\n"

            "- 核心事件：Phong tìm kiếm cổ tịch trong thư viện.\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 3, report)

        self.assertEqual(errors, [])

        # Verify all 3 epistemic states & guidelines are rendered into prompt

        self.assertIn("NGUYÊN TẮC TAM PHÂN TRI THỨC", prompt)

        self.assertIn("[ĐÃ XÁC NHẬN BIẾT] Nhân vật Phong ĐÃ BIẾT: \"Gia tộc từng có một vị lão tổ tu vi Đại Thừa\"", prompt)

        self.assertIn("[ĐÃ XÁC NHẬN KHÔNG BIẾT / MÙ THÔNG TIN] Nhân vật Phong TUYỆT ĐỐI KHÔNG BIẾT: \"Thân phận thực sự của Viện trưởng", prompt)

        self.assertIn("NHẬN THỨC CHỦ QUAN / NGHI NGỜ", prompt)

    def test_10_item_alias_and_lost_vs_unknown_location(self) -> None:

        """Test 10: Item matching supports aliases and cleanly distinguishes confirmed lost vs unknown location."""

        self.setup_baseline_book()

        state = {

            "schema_version": 4,

            "book_title": "TestStory",

            "last_committed_chapter": 2,

            "imported_through_chapter": 0,

            "state_revision": 2,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 3", "scene": "Phố"},

                "long_term_constraints": [],

                "active_character_names": [],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "characters": {},

            "items": {

                "Bản đồ Cổ Mộ": {

                    "name": "Bản đồ Cổ Mộ",

                    "holder": None,

                    "location": "không rõ",

                    "status": "nguyên vẹn",

                    "origin_chapter": 1,

                    "updated_chapter": 1,

                    "description": "Bản đồ da cừu",

                    "aliases": ["Tấm da cừu", "Mật đồ"],

                },

                "Huyền Băng Kiếm": {

                    "name": "Huyền Băng Kiếm",

                    "holder": "Lý Tiêu",

                    "location": "đáy vực Vạn Kiếp",

                    "status": "thất lạc",

                    "origin_chapter": 1,

                    "updated_chapter": 2,

                    "description": "Bảo kiếm trấn phái",

                    "aliases": ["Băng kiếm"],

                },

            },

            "timeline": {},

            "foreshadow": {},

            "wordcount_records": {},

        }

        self.put("追踪/_tracking-state.json", json.dumps(state, ensure_ascii=False, indent=2))

        views = tracking_commit.render_views(tracking_commit.normalize_state(state))

        tracking_commit.write_views(self.book / "追踪", views)

        self.put("正文/第002章_Pho_thi.md", "# 第 2 章\n" + "Mọi người đi dạo trên phố.\n" * 15)

        # Chapter 3 outline mentions aliases and items

        self.put(

            "大纲/细纲_第003章.md",

            "### 第 3 章：Tìm kiếm di vật\n"

            "- 情节点：Nhắc đến Tấm da cừu của phụ thân và hỏi thăm tung tích Băng kiếm.\n"

        )

        report: list[str] = []

        prompt, errors = build_writer_prompt.build(self.book, 3, report)

        self.assertEqual(errors, [])

        # Verify: Matched through aliases, distinguished unknown location vs confirmed lost

        self.assertIn("Bản đồ Cổ Mộ", prompt)

        self.assertIn("CHƯA RÕ VỊ TRÍ", prompt)

        self.assertIn("Huyền Băng Kiếm", prompt)

        self.assertIn("XÁC NHẬN THẤT LẠC", prompt)

    def test_11_commitment_lifecycle_and_overdue_handling(self) -> None:

        """Test 11: Commitments can be added, alert when overdue, and stop alerting when fulfilled."""

        self.setup_baseline_book()

        self.put(

            "大纲/细纲_第001章.md",

            "- 字数目标：2000 字\n"

            "- 字数口径：visible_chars_v1\n"

            "### 第 1 章：Hẹn ước\n",

        )

        self.put("正文/第001章_Hen_uoc.md", "# 第 1 章\n<!-- 去味:跳过 -->\n" + "Lời ước hẹn khắc ghi trong tim.\n" * 80)

        init_doc = {

            "schema_version": 1,

            "book_title": "TestStory",

            "last_chapter": 0,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Đình"},

                "long_term_constraints": [],

                "active_character_names": [],

                "continuity_risks": [],

                "recent_chapters": [],

                "next_chapter_commitments": [],

            },

            "character_snapshots": {},

            "foreshadow": [],

            "timeline_events": [],

        }

        tracking_commit.initialize(self.book, init_doc)

        # Chapter 1 transaction adds a commitment with deadline Chapter 2

        tx1 = {

            "schema_version": 1,

            "mode": "append",

            "chapter": 1,

            "chapter_title": "Hẹn ước",

            "expected_state_revision": 0,

            "delta": {

                "result": "Phong lập lời thề giao đan dược trước giờ ngọ ngày mai.",

                "character_changes": [],

                "foreshadow_changes": [],

                "timeline_events": [],

                "constraints": [],

                "next_chapter_commitments": [],

                "retired_context_items": [],

                "retired_characters": [],

                "commitment_changes": [

                    {

                        "action": "add",

                        "id": "C101",

                        "commitment": "Giao đan dược cho Dược phòng",

                        "deadline_chapter": 2,

                        "status": "pending",

                    }

                ],

            },

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Đình"},

                "long_term_constraints": [],

                "active_character_names": [],

                "continuity_risks": [],

            },

            "character_snapshots": {},

        }

        tx1["wordcount"] = storyctl.build_project_wordcount_record(self.book, 1, resolution="within_user_band")

        state1 = tracking_commit.apply_transaction(self.book, tx1)

        self.assertEqual(len(state1["unfulfilled_commitments"]), 1)

        self.assertEqual(state1["unfulfilled_commitments"][0]["status"], "pending")

        # Now building prompt for Chapter 2: it is at the deadline -> Overdue/Deadline alert

        self.put("大纲/细纲_第002章.md", "- 字数目标：2000 字\n- 字数口径：visible_chars_v1\n### 第 2 章：Chậm trễ\n")

        report: list[str] = []

        prompt2, _ = build_writer_prompt.build(self.book, 2, report)

        self.assertIn("QUÁ HẠN", prompt2)

        self.assertIn("Giao đan dược", prompt2)

        # Chapter 2 fulfills the commitment

        self.put("正文/第002章_Cham_tre.md", "# 第 2 章\n<!-- 去味:跳过 -->\n" + "Phong đã kịp thời giao đan dược cho trưởng lão.\n" * 50)

        tx2 = {

            "schema_version": 1,

            "mode": "append",

            "chapter": 2,

            "chapter_title": "Chậm trễ",

            "expected_state_revision": 1,

            "delta": {

                "result": "Phong đã giao đan dược an toàn.",

                "character_changes": [],

                "foreshadow_changes": [],

                "timeline_events": [],

                "constraints": [],

                "next_chapter_commitments": [],

                "retired_context_items": [],

                "retired_characters": [],

                "commitment_changes": [

                    {

                        "action": "fulfill",

                        "id": "C101",

                        "resolution": "Đã giao đan dược tận tay",

                    }

                ],

            },

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 2", "scene": "Dược phòng"},

                "long_term_constraints": [],

                "active_character_names": [],

                "continuity_risks": [],

            },

            "character_snapshots": {},

        }

        tx2["wordcount"] = storyctl.build_project_wordcount_record(self.book, 2, resolution="within_user_band")

        state2 = tracking_commit.apply_transaction(self.book, tx2)

        self.assertEqual(state2["unfulfilled_commitments"][0]["status"], "fulfilled")

        # In Chapter 3: Commitment was fulfilled in Chapter 2, so it appears as fulfilled confirmation, NOT overdue warning

        self.put("大纲/细纲_第003章.md", "### 第 3 章：Khởi hành\n- Tình tiết: Chuẩn bị lên đường.\n")

        prompt3, _ = build_writer_prompt.build(self.book, 3, report)

        self.assertIn("CAM KẾT ĐÃ HOÀN THÀNH", prompt3)

        self.assertNotIn("CẢNH BÁO NỢ TÌNH TIẾT QUÁ HẠN", prompt3)

    def test_12_summary_drift_scenarios_B_C_D_E(self) -> None:

        """Test 12: Verify summary drift avoids false positives in Scenarios B, C, D, E."""

        # Scenario B: Contemplated signing in prose, but refused; summary records refusal -> No drift

        prose_B = "Ban đầu Phong định đồng ý và cầm bút lên ký kết, nhưng sau đó chàng kiên quyết từ chối ký tên."

        sum_B = "Phong kiên quyết từ chối ký tên."

        self.assertIsNone(storyctl.detect_summary_drift(sum_B, prose_B))

        # Scenario C: Subjective misconception in prose vs objective fact in summary -> No drift

        prose_C = "An ngỡ rằng giao kèo đã bị thiêu hủy, nhưng thực tế Phong đã bảo tồn nguyên vẹn."

        sum_C = "Phong đã bảo tồn nguyên vẹn giao kèo."

        self.assertIsNone(storyctl.detect_summary_drift(sum_C, prose_C))

        # Scenario D: Mentioned in a dream vs reality in summary -> No drift

        prose_D = "Trong giấc mơ, Phong thấy mình đã chết, nhưng khi tỉnh dậy chàng vẫn sống sót bình an."

        sum_D = "Phong vẫn sống sót bình an sau cơn ác mộng."

        self.assertIsNone(storyctl.detect_summary_drift(sum_D, prose_D))

        # Scenario E: Paraphrasing same outcome -> No drift

        prose_E = "Đội ngũ giành thắng lợi hoàn toàn trước quân địch."

        sum_E = "Phe ta chiến thắng vẻ vang."

        self.assertIsNone(storyctl.detect_summary_drift(sum_E, prose_E))

    def test_13_legacy_state_compatibility(self) -> None:

        """Test 13: Backward compatibility with legacy state lacking Phase 4 fields."""

        legacy_state = {

            "schema_version": tracking_commit.TRACKING_SCHEMA_VERSION,

            "book_title": "LegacyStory",

            "last_committed_chapter": 1,

            "imported_through_chapter": 0,

            "state_revision": 1,

            "context": {

                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "Ngày 1", "scene": "Sân"},

                "long_term_constraints": ["Không phá vỡ quy tắc"],

                "active_character_names": ["Nam"],

                "continuity_risks": [],

                "recent_chapters": [{"chapter": 1, "summary": "Chương 1 khởi đầu."}],

                "next_chapter_commitments": ["Luyện công"],

            },

            "characters": {

                "Nam": {

                    "identity": "Đệ tử", "location": "Sân", "goal": "Luyện kiếm", "state": "Khỏe",

                    "abilities_resources": ["Kiếm gỗ"], "relationships": [], "knowledge": ["Kiếm pháp cơ bản"], "open_threads": [],

                }

            },

            "foreshadow": {},

            "timeline": {},

            "wordcount_records": {},

        }

        # Normalization and views must succeed seamlessly without error

        norm = tracking_commit.normalize_state(legacy_state)

        self.assertEqual(norm["book_title"], "LegacyStory")

        views = tracking_commit.render_views(norm)

        self.assertIn("上下文.md", views)

        self.assertIn("角色状态/Nam.md", views)

        # 道具状态.md should NOT be present when items is absent

        self.assertNotIn("道具状态.md", views)

if __name__ == "__main__":

    unittest.main()
