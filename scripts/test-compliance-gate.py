#!/usr/bin/env python3
"""Comprehensive Regression & Hardening Test Suite for Phase 3 & 3.1.
Covers:
- Test A: Normal workflow without manual verifier invocation (Option A auto-verification in chapter check).
- Test B: Compliance violation in normal workflow (auto-blocked at check & commit, work dir preserved).
- Test C: Fail-Closed enforcement when contract is skipped in official workflow (cannot commit silently).
- Test D: Draft changed after check invalidates report (COMPLIANCE_STALE).
- Test E: Verifier failure / corrupt report rejected (COMPLIANCE_INVALID).
- Test F: Workflow recovery after draft fix (auto re-verifies and commits).
- Test G: Chapter scope isolation (mismatched chapter rejected).
- Test H: Backward compatibility for bare legacy fixtures.
- Unit Tests: Compound noun exclusion, semantic clusters, and outline override proposals.
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

import check_compliance  # type: ignore
import storyctl  # type: ignore


def make_body_text(*, alcohol: bool = False) -> str:
    lead = (
        "Phong cao hứng nâng chén uống cạn vò rượu mạnh trước mặt mọi người。\n"
        if alcohol else
        "Phong gặp An tại quán trà nhỏ ven sông. Hắn chỉ gọi một ấm trà xanh thanh đạm và từ chối mọi loại rượu。\n"
    )
    # 13 lines * ~70 chars + lead = ~1002 visible characters (in visible_chars_v1)
    # Must end each line with '。\n'
    lines = [
        f"Hai người cùng nhau ôn lại chuyện xưa bên bến cảng vắng lần thứ {i:02d} trong chiều thu ấm áp。\n"
        for i in range(1, 14)
    ]
    return "# 第 1 章\n<!-- 去味:跳过 -->\n" + lead + "".join(lines)


class ComplianceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="compliance-gate-")
        self.addCleanup(self.tmp.cleanup)
        self.book = (Path(self.tmp.name) / "TestStory").resolve()
        self.book.mkdir(parents=True, exist_ok=True)

        # Baseline story structures
        self.outline_file = self.put(
            "大纲/细纲_第001章.md",
            "- 字数目标：1000 字\n"
            "- 字数口径：visible_chars_v1\n"
            "### 第 1 章：Gặp gỡ ở bến tàu\n"
            "| # | 情节点（谁做了什么） | 功能标签 | 执行边界 |\n"
            "|---|---|---|---|\n"
            "| 1 | Phong gặp lại An ở bến tàu | 推进 | Không cãi vã |\n"
            "| 2 | Phong trò chuyện về chuyến đi | 展示 | Uống trà |\n",
        )
        self.volume_file = self.put(
            "大纲/卷纲_第一卷.md",
            "# 第一卷\n"
            "## 卷契约\n"
            "Hành trình khởi đầu từ bến cảng.\n",
        )
        headings = ["当前位置", "长期约束", "核心角色状态", "活跃伏笔", "近三章速记", "下一章承诺", "连贯性风险"]
        context_body = "\n".join("## " + h + "\n无\n" for h in headings)
        self.put("追踪/上下文.md", context_body)
        self.put("设定/文风.md", "# 文风\n" + "Văn phong gãy gọn, tập trung hành động.\n" * 10)
        self.put("设定/题材正文提示卡.md", "# Ranh giới\nKhông miêu tả bạo lực quá mức.")
        self.put("设定/题材定位.md", "## 作者已定\n- CẤM nhân vật Phong uống rượu.\n")

        # Initialize tracking
        storyctl._tracking_module().initialize(
            self.book,
            {
                "schema_version": 1,
                "book_title": "TestStory",
                "last_chapter": 0,
                "context": {
                    "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "当日", "scene": "bến tàu"},
                    "long_term_constraints": ["只写批准内容。"],
                    "active_character_names": [],
                    "continuity_risks": [],
                    "recent_chapters": [],
                    "next_chapter_commitments": [],
                },
                "character_snapshots": {},
                "foreshadow": [],
                "timeline_events": [],
            },
        )

    def put(self, relative_path: str, content: str) -> Path:
        file_path = self.book / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def make_tracking_tx(self, chapter: int, revision: int = 0) -> Path:
        tx_doc = {
            "schema_version": 1,
            "mode": "append",
            "chapter": chapter,
            "chapter_title": f"Chương {chapter}",
            "expected_state_revision": revision,
            "delta": {
                "result": f"Hoàn thành chương {chapter}.",
                "character_changes": [],
                "foreshadow_changes": [],
                "timeline_events": [],
                "constraints": [],
                "next_chapter_commitments": ["Tiếp tục."],
            },
            "context": {
                "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "当日", "scene": "bến tàu"},
                "long_term_constraints": ["只写批准内容。"],
                "active_character_names": [],
                "continuity_risks": [],
            },
            "character_snapshots": {},
        }
        tx_file = self.book / ".story" / "work" / f"第{chapter:03d}章" / "tracking.json"
        tx_file.parent.mkdir(parents=True, exist_ok=True)
        tx_file.write_text(json.dumps(tx_doc, ensure_ascii=False), encoding="utf-8")
        return tx_file

    def run_cli(self, *args: str) -> tuple[subprocess.CompletedProcess, dict | None]:
        cmd = [sys.executable, str(SCRIPTS / "storyctl.py"), *args]
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **os.environ}
        proc = subprocess.run(cmd, cwd=str(self.book), capture_output=True, text=True, encoding="utf-8", env=env)
        data = None
        if proc.stdout.strip():
            try:
                data = json.loads(proc.stdout.strip().splitlines()[-1])
            except Exception:
                pass
        return proc, data

    # -------------------------------------------------------------------------
    # TEST A: Normal Workflow Without Manual Verifier Invocation
    # -------------------------------------------------------------------------
    def test_a_normal_workflow_automatic_verification(self) -> None:
        """Quy trình chuẩn: build prompt -> draft -> chapter check (tự động verifier) -> chapter commit.
        Không cần bất kỳ bước gọi thủ công nào tới check_compliance.py verify.
        """
        # Step 3: Run build_writer_prompt.py with author request
        cmd_prompt = [
            sys.executable,
            str(SCRIPTS / "build_writer_prompt.py"),
            "--project", str(self.book),
            "--chapter", "1",
            "--request", "CẤM nhân vật Phong uống rượu.",
            "--out",
        ]
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **os.environ}
        res_prompt = subprocess.run(cmd_prompt, cwd=str(self.book), capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(res_prompt.returncode, 0, res_prompt.stderr)

        work_dir = self.book / ".story" / "work" / "第001章"
        contract_file = work_dir / "compliance_contract.json"
        self.assertTrue(contract_file.is_file(), "Contract must be generated by build_writer_prompt.py")

        # Step 7: Writer creates compliant draft (~1002 visible chars)
        self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=False))

        # Step 8: Run storyctl chapter check --fix-punctuation
        # Verifier is called AUTOMATICALLY inside chapter check (Option A)
        proc_check, check_data = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1", "--fix-punctuation")
        self.assertEqual(proc_check.returncode, 0, f"stdout: {proc_check.stdout}\nstderr: {proc_check.stderr}")
        self.assertIsNotNone(check_data)
        self.assertEqual(check_data["status"], "ready")
        self.assertIn("compliance", check_data)
        self.assertEqual(check_data["compliance"]["status"], "PASS")

        # Verify compliance_report.json was generated automatically
        report_file = work_dir / "compliance_report.json"
        self.assertTrue(report_file.is_file(), "compliance_report.json must be written automatically by chapter check")
        report_data = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(report_data["status"], "PASS")
        self.assertEqual(report_data["chapter"], 1)

        # Step 12: Run storyctl chapter commit
        tx_file = self.make_tracking_tx(1, revision=0)
        proc_commit, commit_data = self.run_cli("chapter", "commit", "--project", str(self.book), "--chapter", "1", "--input", str(tx_file))
        self.assertEqual(proc_commit.returncode, 0, f"stdout: {proc_commit.stdout}\nstderr: {proc_commit.stderr}")
        self.assertTrue(commit_data.get("tracking_committed"))

    # -------------------------------------------------------------------------
    # TEST B: Compliance Violation in Normal Workflow
    # -------------------------------------------------------------------------
    def test_b_compliance_violation_in_normal_workflow(self) -> None:
        """Bản thảo vi phạm quy định cấm. Chạy quy trình bình thường:
        chapter check trả status blocked, chapter commit bị từ chối COMPLIANCE_BLOCKED,
        thư mục work và bản thảo được bảo toàn.
        """
        cmd_prompt = [
            sys.executable,
            str(SCRIPTS / "build_writer_prompt.py"),
            "--project", str(self.book),
            "--chapter", "1",
            "--request", "CẤM nhân vật Phong uống rượu.",
            "--out",
        ]
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **os.environ}
        subprocess.run(cmd_prompt, cwd=str(self.book), capture_output=True, text=True, check=True, encoding="utf-8", env=env)

        # Violating draft with alcohol (~1002 chars)
        self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=True))

        # Step 8: chapter check must detect violation automatically
        proc_check, check_data = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1")
        self.assertEqual(proc_check.returncode, 1)
        self.assertEqual(check_data["status"], "blocked")
        self.assertEqual(check_data["compliance"]["status"], "VIOLATION")

        # Step 12: chapter commit must refuse
        tx_file = self.make_tracking_tx(1, revision=0)
        proc_commit, commit_data = self.run_cli("chapter", "commit", "--project", str(self.book), "--chapter", "1", "--input", str(tx_file))
        self.assertEqual(proc_commit.returncode, 2)
        self.assertIn("COMPLIANCE_BLOCKED", proc_commit.stdout)

        # Crucial invariants:
        work_dir = self.book / ".story" / "work" / "第001章"
        self.assertTrue(work_dir.is_dir(), "Work dir must be preserved when commit is refused")
        tracking_state = storyctl._tracking_module().load_state(self.book)
        self.assertEqual(tracking_state["last_committed_chapter"], 0, "Tracking state must NOT be advanced")

    # -------------------------------------------------------------------------
    # TEST C: Fail-Closed Enforcement When Contract Is Skipped
    # -------------------------------------------------------------------------
    def test_c_fail_closed_missing_contract_rejection(self) -> None:
        """Quy trình viết chính thức (có 设定/题材定位.md) nhưng bỏ qua bước tạo hợp đồng.
        Hệ thống fail-closed: chapter check và commit đều từ chối với COMPLIANCE_MISSING.
        """
        # Draft created directly without running build_writer_prompt.py
        self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=False))

        # Chapter check must block because official workflow requires compliance contract
        proc_check, check_data = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1")
        self.assertEqual(proc_check.returncode, 1)
        self.assertEqual(check_data["status"], "blocked")
        self.assertEqual(check_data["compliance"]["error_code"], "COMPLIANCE_MISSING")

        # Chapter commit must be blocked
        tx_file = self.make_tracking_tx(1, revision=0)
        proc_commit, commit_data = self.run_cli("chapter", "commit", "--project", str(self.book), "--chapter", "1", "--input", str(tx_file))
        self.assertEqual(proc_commit.returncode, 2)
        self.assertIn("COMPLIANCE_MISSING", proc_commit.stdout)

    # -------------------------------------------------------------------------
    # TEST D: Draft Changed After Check (Stale Report)
    # -------------------------------------------------------------------------
    def test_d_draft_changed_after_check_stale_rejection(self) -> None:
        """Kiểm tra đạt, nhưng sau đó bản thảo bị sửa đổi. Thử commit bằng báo cáo cũ -> bị từ chối COMPLIANCE_STALE."""
        cmd_prompt = [
            sys.executable,
            str(SCRIPTS / "build_writer_prompt.py"),
            "--project", str(self.book),
            "--chapter", "1",
            "--request", "CẤM nhân vật Phong uống rượu.",
            "--out",
        ]
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **os.environ}
        subprocess.run(cmd_prompt, cwd=str(self.book), capture_output=True, text=True, check=True, encoding="utf-8", env=env)

        body_file = self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=False))

        # Run check -> PASS report generated
        proc_check, check_data = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1")
        self.assertEqual(proc_check.returncode, 0, f"stdout: {proc_check.stdout}\nstderr: {proc_check.stderr}")
        self.assertEqual(check_data["compliance"]["status"], "PASS")

        # Now tamper with draft in-place
        body_file.write_text(body_file.read_text(encoding="utf-8") + "Phong lại uống rượu một mình。\n", encoding="utf-8")

        # Attempt commit without re-running check -> stale hash detected
        tx_file = self.make_tracking_tx(1, revision=0)
        proc_commit, _ = self.run_cli("chapter", "commit", "--project", str(self.book), "--chapter", "1", "--input", str(tx_file))
        self.assertEqual(proc_commit.returncode, 2)
        self.assertIn("COMPLIANCE_STALE", proc_commit.stdout)

    # -------------------------------------------------------------------------
    # TEST E: Verifier Failure / Corrupt Report Rejected
    # -------------------------------------------------------------------------
    def test_e_verifier_failure_and_corrupt_report(self) -> None:
        """Báo cáo bị hỏng (corrupted json) hoặc sai schema -> không tự biến thành PASS, commit bị từ chối COMPLIANCE_INVALID."""
        work_dir = self.book / ".story" / "work" / "第001章"
        work_dir.mkdir(parents=True, exist_ok=True)
        contract = check_compliance.build_compliance_contract(self.book, 1, author_request="CẤM gây sự.")
        check_compliance.save_compliance_contract(self.book, 1, contract)

        body_file = self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=False))

        # Write corrupt report
        report_file = work_dir / "compliance_report.json"
        report_file.write_text("{ corrupt json syntax...", encoding="utf-8")

        # Calling gate directly
        with self.assertRaises(storyctl.ChapterRefused) as ctx:
            storyctl.check_compliance_gate(self.book, 1, body_file)
        self.assertEqual(ctx.exception.code, "COMPLIANCE_INVALID")

    # -------------------------------------------------------------------------
    # TEST F: Workflow Recovery After Draft Fix
    # -------------------------------------------------------------------------
    def test_f_workflow_recovery_after_draft_fix(self) -> None:
        """Sau khi phát hiện vi phạm, sửa bản thảo và chạy lại chapter check.
        Hệ thống tự động re-verify, tạo báo cáo PASS mới, và commit thành công.
        """
        cmd_prompt = [
            sys.executable,
            str(SCRIPTS / "build_writer_prompt.py"),
            "--project", str(self.book),
            "--chapter", "1",
            "--request", "CẤM nhân vật Phong uống rượu.",
            "--out",
        ]
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **os.environ}
        subprocess.run(cmd_prompt, cwd=str(self.book), capture_output=True, text=True, check=True, encoding="utf-8", env=env)

        body_file = self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=True))

        # 1. First check -> BLOCKED
        proc1, data1 = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1")
        self.assertEqual(proc1.returncode, 1)
        self.assertEqual(data1["status"], "blocked")

        # 2. Author fixes draft (~1002 chars without alcohol)
        body_file.write_text(make_body_text(alcohol=False), encoding="utf-8")

        # 3. Second check -> AUTOMATICALLY RE-VERIFIED to PASS
        proc2, data2 = self.run_cli("chapter", "check", "--project", str(self.book), "--chapter", "1")
        self.assertEqual(proc2.returncode, 0, f"stdout: {proc2.stdout}\nstderr: {proc2.stderr}")
        self.assertEqual(data2["status"], "ready")
        self.assertEqual(data2["compliance"]["status"], "PASS")

        # 4. Commit succeeds
        tx_file = self.make_tracking_tx(1, revision=0)
        proc_commit, commit_data = self.run_cli("chapter", "commit", "--project", str(self.book), "--chapter", "1", "--input", str(tx_file))
        self.assertEqual(proc_commit.returncode, 0)
        self.assertTrue(commit_data.get("tracking_committed"))

    # -------------------------------------------------------------------------
    # TEST G: Chapter Scope Isolation
    # -------------------------------------------------------------------------
    def test_g_chapter_scope_isolation(self) -> None:
        """Hợp đồng và báo cáo thuộc chương 2 không được dùng cho chương 1."""
        contract_ch2 = check_compliance.build_compliance_contract(self.book, 2, author_request="CẤM đốt thuyền.")
        # Erroneously put chapter 2 contract in chapter 1 directory
        ch1_work = self.book / ".story" / "work" / "第001章"
        ch1_work.mkdir(parents=True, exist_ok=True)
        (ch1_work / "compliance_contract.json").write_text(json.dumps(contract_ch2, ensure_ascii=False), encoding="utf-8")

        body_file = self.put("正文/第001章_Gặp_gỡ.md", make_body_text(alcohol=False))

        # Verification must reject due to chapter mismatch
        report = check_compliance.verify_chapter_compliance(self.book, 1, body_path=body_file)
        self.assertEqual(report["status"], "INSUFFICIENT_CONTEXT")
        self.assertIn("mismatch", report["summary"].lower())

    # -------------------------------------------------------------------------
    # TEST H: Backward Compatibility for Bare Legacy Fixtures
    # -------------------------------------------------------------------------
    def test_h_legacy_backward_compatibility(self) -> None:
        """Dự án bare CLI chỉ kiểm tra từ ngữ/wordcount cơ bản, không có cấu trúc tiểu thuyết
        (không có 设定/题材定位.md, không có contract).
        Commit thành công mà không bị chặn, bảo đảm 100% tương thích ngược.
        """
        with tempfile.TemporaryDirectory(prefix="legacy-bare-") as bare_tmp:
            bare_project = Path(bare_tmp) / "BareBook"
            bare_project.mkdir()

            # Only initialize bare tracking and minimal outline/body
            storyctl._tracking_module().initialize(
                bare_project,
                {
                    "schema_version": 1,
                    "book_title": "BareBook",
                    "last_chapter": 0,
                    "context": {
                        "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "当日", "scene": "test"},
                        "long_term_constraints": ["只写批准内容。"],
                        "active_character_names": [],
                        "continuity_risks": [],
                        "recent_chapters": [],
                        "next_chapter_commitments": [],
                    },
                    "character_snapshots": {},
                    "foreshadow": [],
                    "timeline_events": [],
                },
            )
            outline = bare_project / "大纲" / "细纲_第001章.md"
            outline.parent.mkdir(parents=True, exist_ok=True)
            outline.write_text("- 字数目标：1000 字\n- 字数口径：visible_chars_v1\n", encoding="utf-8")

            body = bare_project / "正文" / "第001章_测试.md"
            body.parent.mkdir(parents=True, exist_ok=True)
            body_text = "# 第 1 章 测试\n<!-- 去味:跳过 -->\n" + "".join(
                f"Đoạn văn kiểm tra đếm từ số {i:02d} với nội dung khác biệt hoàn toàn để tránh lặp từ。\n"
                for i in range(1, 17)
            )
            body.write_text(body_text, encoding="utf-8")

            # In this bare project, is_official_workflow_project is False
            self.assertFalse(storyctl.is_official_workflow_project(bare_project, 1))

            # Check succeeds with compliance: None
            checked = storyctl.chapter_check(bare_project, 1)
            self.assertEqual(checked["status"], "ready")
            self.assertIsNone(checked.get("compliance"))

            # Commit succeeds without error
            tx_doc = {
                "schema_version": 1,
                "mode": "append",
                "chapter": 1,
                "chapter_title": "Test",
                "expected_state_revision": 0,
                "delta": {
                    "result": "Hoàn thành.",
                    "character_changes": [],
                    "foreshadow_changes": [],
                    "timeline_events": [],
                    "constraints": [],
                    "next_chapter_commitments": [],
                },
                "context": {
                    "position": {"volume": "第一卷", "volume_start_chapter": 1, "story_time": "当日", "scene": "test"},
                    "long_term_constraints": ["只写批准内容。"],
                    "active_character_names": [],
                    "continuity_risks": [],
                },
                "character_snapshots": {},
            }
            tx_path = bare_project / "tx.json"
            tx_path.write_text(json.dumps(tx_doc, ensure_ascii=False), encoding="utf-8")

            committed = storyctl.chapter_commit(bare_project, 1, tx_path, accept_current_length=False)
            self.assertTrue(committed["tracking_committed"])

    # -------------------------------------------------------------------------
    # UNIT TESTS: Semantic Clusters, Compound Nouns, Outline Overrides
    # -------------------------------------------------------------------------
    def test_unit_semantic_cluster_detection(self) -> None:
        """Kiểm tra phát hiện vi phạm ngữ nghĩa thông qua cụm từ (bribe, alcohol, violence)."""
        contract = check_compliance.build_compliance_contract(
            self.book, 1, author_request="TUYỆT ĐỐI CẤM quan viên nhận tiền hối lộ hoặc đút lót."
        )
        check_compliance.save_compliance_contract(self.book, 1, contract)
        body = self.put(
            "正文/第001章_Gặp_gỡ.md",
            "# 第 1 章\nThương nhân kín đáo nhét chiếc phong bì dày cộp đựng đầy ngân phiếu vào trong tay áo của quan lớn。\n" * 10
        )
        report = check_compliance.verify_chapter_compliance(self.book, 1, body_path=body)
        self.assertEqual(report["status"], "VIOLATION")
        self.assertEqual(report["findings"][0]["method"], "heuristic_semantic_cluster")

    def test_unit_compound_noun_and_negation_exclusion(self) -> None:
        """Danh từ ghép như 'cấm địa', 'cấm cung' và ngữ cảnh phủ định không tạo false-positive."""
        contract = check_compliance.build_compliance_contract(
            self.book, 1, author_request="CẤM tiết lộ bí mật thân thế."
        )
        check_compliance.save_compliance_contract(self.book, 1, contract)
        body = self.put(
            "正文/第001章_Gặp_gỡ.md",
            "# 第 1 章\nHai người cùng bước vào cấm địa. Phong cẩn trọng, không hé răng nửa lời về bí mật thân thế。\n" * 10
        )
        report = check_compliance.verify_chapter_compliance(self.book, 1, body_path=body)
        self.assertEqual(report["status"], "PASS")

    def test_unit_outline_override_proposal_generation(self) -> None:
        """Khi tác giả bãi bỏ tình tiết trong đề cương, tạo đề xuất tư vấn mà không sửa đổi file đề cương gốc."""
        outline_with_sword = (
            "- 字数目标：1000 字\n"
            "- 字数口径：visible_chars_v1\n"
            "### 第 1 章：Gặp gỡ ở bến tàu\n"
            "| # | 情节点（谁做了什么） | 功能标签 | 执行边界 |\n"
            "|---|---|---|---|\n"
            "| 1 | Phong gặp lại An ở bến tàu | 推进 | Không cãi vã |\n"
            "| 2 | Phong khoe bảo kiếm gia truyền | 展示 | Chưa rút kiếm |\n"
        )
        contract = check_compliance.build_compliance_contract(
            self.book, 1,
            author_request="BÃI BỎ cảnh khoe bảo kiếm trong đề cương; CẤM nhắc đến bảo kiếm.",
            outline_text=outline_with_sword,
        )
        check_compliance.save_compliance_contract(self.book, 1, contract)
        self.assertTrue(len(contract["outline_conflicts"]) >= 1)
        self.assertEqual(contract["outline_conflicts"][0]["status"], "adjudicated_override")
        # Ensure outline file on disk untouched
        self.assertIn("Phong gặp lại An ở bến tàu", self.outline_file.read_text(encoding="utf-8"))
        proposal_file = self.book / ".story" / "work" / "第001章" / "outline_change_proposal.json"
        self.assertTrue(proposal_file.is_file())


if __name__ == "__main__":
    unittest.main()
