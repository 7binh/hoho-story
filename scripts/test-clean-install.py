#!/usr/bin/env python3
"""Phase 3.2: Clean-Install Verification Suite via Skills CLI.

Verifies:
- Stage A: Isolated installation using `npx --yes skills add <source> --skill story-long-write --agent antigravity -y`
- Stage B: Installed tree integrity (SKILL.md, references, scripts, self-contained module resolution)
- Stage C: End-to-end functionality using ONLY installed scripts:
    1. build_writer_prompt with author intent -> verifies prompt and compliance_contract.json
    2. chapter check on violating draft -> blocked (COMPLIANCE_BLOCKED), report saved, draft preserved
    3. chapter commit on violating draft -> blocked
    4. draft fixed without re-running check -> commit blocked (COMPLIANCE_STALE)
    5. chapter check on compliant draft -> ready (PASS)
    6. chapter commit on compliant draft -> success (tracking_committed: true)
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_body_text(*, alcohol: bool = False) -> str:
    lead = (
        "Phong cao hứng nâng chén uống cạn vò rượu mạnh trước mặt mọi người。\n"
        if alcohol else
        "Phong gặp An tại quán trà nhỏ ven sông. Hắn chỉ gọi một ấm trà xanh thanh đạm và từ chối mọi loại rượu。\n"
    )
    lines = [
        f"Hai người cùng nhau ôn lại chuyện xưa bên bến cảng vắng lần thứ {i:02d} trong chiều thu ấm áp。\n"
        for i in range(1, 14)
    ]
    return "# 第 1 章\n<!-- 去味:跳过 -->\n" + lead + "".join(lines)


def load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CleanInstallVerificationTests(unittest.TestCase):
    staging_dir: Path
    installed_skill_dir: Path
    project_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path(tempfile.mkdtemp(prefix="oh-story-clean-install-"))
        cls.staging_dir = cls.temp_root / "staging"
        cls.staging_dir.mkdir(parents=True, exist_ok=True)
        cls.project_dir = cls.temp_root / "synthetic_novel"
        cls.project_dir.mkdir(parents=True, exist_ok=True)

        # Stage A: Run Skills CLI install
        cmd = [
            "npx", "--yes", "skills", "add",
            str(ROOT),
            "--skill", "story-long-write",
            "--agent", "antigravity",
            "-y",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(cls.staging_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"npx skills add failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

        cls.installed_skill_dir = cls.staging_dir / ".agents" / "skills" / "story-long-write"

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def test_01_installed_tree_structure(self) -> None:
        """Stage B.1: Check installed skill directory, SKILL.md, references, and scripts."""
        self.assertTrue(self.installed_skill_dir.is_dir(), f"Installed dir missing: {self.installed_skill_dir}")
        skill_md = self.installed_skill_dir / "SKILL.md"
        self.assertTrue(skill_md.is_file(), "SKILL.md missing")
        skill_text = skill_md.read_text(encoding="utf-8")
        self.assertIn("story-long-write", skill_text)
        self.assertIn("compliance_contract.json", skill_text)

        # References
        refs_dir = self.installed_skill_dir / "references"
        self.assertTrue(refs_dir.is_dir(), "references/ missing")
        self.assertTrue((refs_dir / "workflow-chapter.md").is_file(), "workflow-chapter.md missing")
        self.assertTrue((refs_dir / "agent-calls.md").is_file(), "agent-calls.md missing")

        # Scripts
        scripts_dir = self.installed_skill_dir / "scripts"
        self.assertTrue(scripts_dir.is_dir(), "scripts/ missing")
        required_scripts = [
            "build_writer_prompt.py",
            "check_compliance.py",
            "storyctl.py",
            "tracking_commit.py",
            "wordcount_core.py",
            "author_memory_commit.py",
            "outline_view.py",
        ]
        for s in required_scripts:
            self.assertTrue((scripts_dir / s).is_file(), f"Installed script missing: {s}")

    def test_02_installed_scripts_independent_execution(self) -> None:
        """Stage B.2: Installed scripts execute without cwd dependency and without importing dev repo."""
        scripts_dir = self.installed_skill_dir / "scripts"
        for script_name in ["storyctl.py", "check_compliance.py", "build_writer_prompt.py"]:
            script_path = scripts_dir / script_name
            proc = subprocess.run(
                [sys.executable, str(script_path), "--help"],
                cwd=str(self.temp_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, f"{script_name} --help failed:\n{proc.stderr}")

    def test_03_end_to_end_pipeline_with_compliance_gate(self) -> None:
        """Stage C: End-to-end story workflow executed purely from the clean installed scripts."""
        scripts_dir = self.installed_skill_dir / "scripts"
        project = self.project_dir

        # Setup standard synthetic story structure
        (project / "设定").mkdir(parents=True, exist_ok=True)
        (project / "大纲").mkdir(parents=True, exist_ok=True)
        (project / "正文").mkdir(parents=True, exist_ok=True)
        (project / "追踪").mkdir(parents=True, exist_ok=True)

        (project / "设定" / "题材定位.md").write_text("# 题材定位\n\n- 题材: Tiên hiệp\n", encoding="utf-8")
        (project / "设定" / "文风.md").write_text("# 文风\n" + "Hành văn tự nhiên, mộc mạc。\n" * 10, encoding="utf-8")
        (project / "大纲" / "卷纲_第1卷.md").write_text(
            "# 第 1 卷\n\n"
            "## 卷契约\n- 核心看点: Khởi đầu hành trình\n\n"
            "### U01\n"
            "- 章节范围：第1-5章\n"
            "- 单元情绪引擎：Trầm tĩnh\n"
            "- 单元节拍/章功能分配：第1章 Phong gặp An\n",
            encoding="utf-8",
        )
        outline_content = (
            "# 第 1 章细纲\n\n"
            "### 第 1 章：Khởi Đầu\n\n"
            "- 单元ID/位置: U01-01\n"
            "- 目标情绪: Trầm tĩnh\n"
            "- 主角目标: Uống trà bàn chuyện xưa\n"
            "- 字数目标：1000 字\n"
            "- 字数口径：visible_chars_v1\n"
            "- 情节点:\n"
            "  - Phong gặp An tại bến sông\n"
            "  - Từ chối uống rượu mạnh và giữ sự tỉnh táo\n"
        )
        (project / "大纲" / "细纲_第001章.md").write_text(outline_content, encoding="utf-8")

        headings = ["当前位置", "长期约束", "核心角色状态", "活跃伏笔", "近三章速记", "下一章承诺", "连贯性风险"]
        context_body = "\n".join("## " + h + "\n无\n" for h in headings)
        (project / "追踪" / "上下文.md").write_text(context_body, encoding="utf-8")

        # Initialize tracking using installed tracking_commit
        tracking_mod = load_module_from_path("clean_tracking_commit", scripts_dir / "tracking_commit.py")
        tracking_mod.initialize(
            project,
            {
                "schema_version": 1,
                "book_title": "SyntheticBook",
                "last_chapter": 0,
                "context": {
                    "position": {"volume": "第 1 卷", "volume_start_chapter": 1, "story_time": "Chiều thu", "scene": "bến sông"},
                    "long_term_constraints": ["Phong từ chối uống rượu."],
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

        # Step 1: Run installed build_writer_prompt.py with author intent
        build_prompt_script = scripts_dir / "build_writer_prompt.py"
        author_request = "Nhân vật chính Phong tuyệt đối không uống rượu, cấm tiệt uống rượu mạnh."
        proc_prompt = subprocess.run(
            [
                sys.executable, str(build_prompt_script),
                "--project", str(project),
                "--chapter", "1",
                "--request", author_request,
                "--out",
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc_prompt.returncode, 0, f"build_writer_prompt failed:\n{proc_prompt.stderr}")

        work_dir = project / ".story" / "work" / "第001章"
        if not work_dir.exists():
            work_dir = project / ".story" / "work" / "第1章"
        self.assertTrue(work_dir.is_dir(), f"Work dir not created: {work_dir}")
        contract_path = work_dir / "compliance_contract.json"
        self.assertTrue(contract_path.is_file(), "compliance_contract.json not created")

        contract_data = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract_data.get("schema"), "story-compliance-contract/v1")
        self.assertIn("contract_sha256", contract_data)

        # Step 2: Write a draft that VIOLATES author intent (Phong drinks alcohol)
        draft_file = project / "正文" / "第001章_khoi_dau.md"
        draft_file.write_text(make_body_text(alcohol=True), encoding="utf-8")

        # Step 3: Run installed storyctl.py chapter check -> must be BLOCKED
        storyctl_script = scripts_dir / "storyctl.py"
        proc_check_viol = subprocess.run(
            [
                sys.executable, str(storyctl_script), "chapter", "check",
                "--project", str(project),
                "--chapter", "1",
                "--fix-punctuation",
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc_check_viol.returncode, 1, f"Violating draft was not blocked:\nSTDOUT:\n{proc_check_viol.stdout}\nSTDERR:\n{proc_check_viol.stderr}")
        check_json = json.loads(proc_check_viol.stdout)
        self.assertEqual(check_json.get("status"), "blocked")
        self.assertIn("compliance", check_json)
        self.assertEqual(check_json["compliance"].get("status"), "VIOLATION")

        # Verify draft was NOT wiped
        self.assertTrue(draft_file.is_file(), "Draft was wiped on violation!")

        # Step 4: Try to commit violating draft -> must be BLOCKED
        tx_doc = {
            "schema_version": 1,
            "mode": "append",
            "chapter": 1,
            "chapter_title": "Khởi Đầu",
            "expected_state_revision": 0,
            "delta": {
                "result": "Hoàn thành chương 1.",
                "character_changes": [],
                "foreshadow_changes": [],
                "timeline_events": [],
                "constraints": [],
                "next_chapter_commitments": ["Tiếp tục."],
            },
            "context": {
                "position": {"volume": "第 1 卷", "volume_start_chapter": 1, "story_time": "Chiều thu", "scene": "bến sông"},
                "long_term_constraints": ["Phong từ chối uống rượu."],
                "active_character_names": [],
                "continuity_risks": [],
            },
            "character_snapshots": {},
        }
        draft_tracking = work_dir / "tracking.json"
        draft_tracking.write_text(json.dumps(tx_doc, ensure_ascii=False), encoding="utf-8")

        proc_commit_viol = subprocess.run(
            [
                sys.executable, str(storyctl_script), "chapter", "commit",
                "--project", str(project),
                "--chapter", "1",
                "--input", str(draft_tracking),
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertNotEqual(proc_commit_viol.returncode, 0, "Violating draft commit was not blocked!")
        commit_err = json.loads(proc_commit_viol.stdout)
        self.assertEqual(commit_err.get("error_code"), "COMPLIANCE_BLOCKED")

        # Step 5: Fix draft to COMPLY, but DO NOT re-run check -> commit must be BLOCKED (COMPLIANCE_STALE)
        draft_file.write_text(make_body_text(alcohol=False), encoding="utf-8")
        proc_commit_stale = subprocess.run(
            [
                sys.executable, str(storyctl_script), "chapter", "commit",
                "--project", str(project),
                "--chapter", "1",
                "--input", str(draft_tracking),
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertNotEqual(proc_commit_stale.returncode, 0, "Stale compliance report commit was not blocked!")
        stale_err = json.loads(proc_commit_stale.stdout)
        self.assertEqual(stale_err.get("error_code"), "COMPLIANCE_STALE")

        # Step 6: Re-run installed storyctl.py chapter check -> must be READY (PASS)
        proc_check_pass = subprocess.run(
            [
                sys.executable, str(storyctl_script), "chapter", "check",
                "--project", str(project),
                "--chapter", "1",
                "--fix-punctuation",
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc_check_pass.returncode, 0, f"Compliant draft check failed:\n{proc_check_pass.stderr}")
        pass_json = json.loads(proc_check_pass.stdout)
        self.assertEqual(pass_json.get("status"), "ready")
        self.assertEqual(pass_json.get("compliance", {}).get("status"), "PASS")

        # Step 7: Commit compliant chapter -> must SUCCEED
        proc_commit_pass = subprocess.run(
            [
                sys.executable, str(storyctl_script), "chapter", "commit",
                "--project", str(project),
                "--chapter", "1",
                "--input", str(draft_tracking),
            ],
            cwd=str(self.temp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc_commit_pass.returncode, 0, f"Compliant chapter commit failed:\n{proc_commit_pass.stderr}")
        commit_json = json.loads(proc_commit_pass.stdout)
        self.assertTrue(commit_json.get("tracking_committed"), "Commit failed to report tracking_committed")

        # Verify tracking state updated
        state = json.loads((project / "追踪" / "_tracking-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state.get("last_committed_chapter"), 1)


if __name__ == "__main__":
    unittest.main()
