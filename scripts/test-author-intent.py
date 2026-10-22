#!/usr/bin/env python3
"""Comprehensive Regression & Hardening Test Suite for Author Intent Preservation.
Covers Phase 2 and Phase 2.1 requirements:
1. Multilingual author boundary headers (Vietnamese, Chinese, English, numbered).
2. Author requirements > 600 characters (critical constraints preserved).
3. Author memory loading from both 作者记忆/*.md and docs/作者记忆/*.md with provenance.
4. Memory filtering: ignores internal/cache files, empty files, and mismatched book scopes.
5. Conflict resolution: author current request overrides outline (CONFLICT OVERRIDE).
6. Canon conflict detection (CANON CONFLICT warning vs AUTHORIZED RETCON).
7. Boundary conflict detection (BOUNDARY CONFLICT warning vs AUTHORIZED BOUNDARY OVERRIDE).
8. False-positive noun filtering: phrases like 'cấm địa', 'cấm cung', 'biển cấm' are not misidentified as constraints.
9. Request safety & scoping: precedence, missing file error, and chapter isolation.
10. Budget exhaustion handling when critical rules exceed 3500 characters.
11. Full end-to-end pipeline integration test from inputs to final prompt file on disk.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'skills/story-long-write/scripts'


class AuthorIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='author-intent-')
        self.addCleanup(self.tmp.cleanup)
        self.book = (Path(self.tmp.name) / 'TestStory').resolve()
        self.book.mkdir(parents=True, exist_ok=True)

        # Baseline structure required by build_writer_prompt.py
        self.outline_file = self.put(
            '大纲/细纲_第005章.md',
            '### 第 5 章：Diễn kịch với thế giới\n'
            '- 核心事件：Phong và Ân đối mặt với mẹ Lành; Phong hứa chiều nay sẽ đi mua đồ lót nữ cho An.\n'
            '- 单元ID/位置：H1-05\n'
            '- 目标情绪：Căng thẳng → Thở phào\n'
            '- 主角目标/关键选择：Che giấu bí mật\n'
        )
        self.volume_file = self.put(
            '大纲/卷纲_第一卷.md',
            '# 第一卷\n'
            '### 剧情单元 H1-05\n'
            '- 章节范围：第1-5章\n'
            '- 单元情绪引擎：Căng thẳng → Thở phào\n'
            '- 单元节拍/章功能分配：第5章 đối phó người nhà\n'
        )
        headings = ['当前位置', '长期约束', '核心角色状态', '活跃伏笔', '近三章速记', '下一章承诺', '连贯性风险']
        context_body = '\n'.join('## ' + h + '\n无\n' for h in headings)
        self.put('追踪/上下文.md', context_body)
        self.put('设定/文风.md', '# 文风\n' + 'Hành văn tự nhiên, đối thoại đời thường.\n' * 10)
        self.put('设定/题材正文提示卡.md', '# Ranh giới\nGiữ bí mật tuyệt đối về biến thân.')

        # Previous chapter (Chapter 4) for chapter 5
        self.put('正文/第004章_Truoc_khi_chuong_reo.md', '# 第 4 章\n' + 'Phong thở dài nhìn An.\n' * 20)

    def put(self, relative_path: str, content: str) -> Path:
        file_path = self.book / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return file_path

    def run_build(self, *extra_args, chapter=5):
        cmd = [
            sys.executable,
            str(SCRIPTS / 'build_writer_prompt.py'),
            '--project', str(self.book),
            '--chapter', str(chapter),
            *extra_args
        ]
        return subprocess.run(
            cmd,
            cwd=str(self.book),
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

    # -------------------------------------------------------------------------
    # TEST 1: Multilingual Author Boundary Headers
    # -------------------------------------------------------------------------
    def test_multilingual_author_boundary_headers(self):
        """Test that author boundary headers in Vietnamese, English, and Chinese are recognized."""
        test_cases = [
            (
                'Vietnamese "## Tác giả đã chốt"',
                '## Tác giả đã chốt\n- CẤM Phong làm bác sĩ phụ khoa.\n- CẤM mansplaining.\n',
                ['CẤM Phong làm bác sĩ phụ khoa', 'CẤM mansplaining']
            ),
            (
                'Vietnamese "## Ranh giới sáng tác"',
                '## 1. Ranh giới sáng tác\n- Tuyệt đối cấm thiểu năng hóa nữ chính.\n- Giữ bí mật biến thân.\n',
                ['Tuyệt đối cấm thiểu năng hóa nữ chính', 'Giữ bí mật biến thân']
            ),
            (
                'English "## Author Boundaries"',
                '## Author Boundaries\n- Slow burn pacing over 70 chapters.\n- No instant romance.\n',
                ['Slow burn pacing over 70 chapters', 'No instant romance']
            ),
            (
                'Chinese "## 作者已定"',
                '## 作者已定\n- 严禁男主当众说教。\n',
                ['严禁男主当众说教']
            ),
        ]

        for label, content, expected_phrases in test_cases:
            with self.subTest(label=label):
                self.put('设定/题材定位.md', f'# Đề tài\n\n{content}')
                res = self.run_build()
                self.assertEqual(res.returncode, 0, f"Failed on {label}: {res.stderr}")
                for phrase in expected_phrases:
                    self.assertIn(
                        phrase,
                        res.stdout,
                        f"Expected phrase '{phrase}' was not found in prompt for {label}."
                    )
                self.assertIn("作者已定：已注入", res.stdout, f"Report should confirm injection for {label}")

    # -------------------------------------------------------------------------
    # TEST 2: Requirements > 600 Characters (Critical rules preserved)
    # -------------------------------------------------------------------------
    def test_author_requirements_longer_than_600_chars_preserved(self):
        """Test that a long list of author constraints (> 1000 chars) preserves high-priority rules at the end."""
        filler_rules = [f"- Quy tắc thường nhật số {i:02d}: Phong và Ân phân chia công việc nhà rõ ràng." for i in range(1, 25)]
        critical_constraint = "CẤM: Tuyệt đối không để nhân vật chính làm lộ bí mật biến thân trước chương 15."
        full_text = "## Tác giả đã chốt\n" + "\n".join(filler_rules) + f"\n- {critical_constraint}\n"

        self.assertTrue(len(full_text) > 1000, f"Setup error: length is {len(full_text)}")
        self.put('设定/题材定位.md', f'# Đề tài\n\n{full_text}')

        res = self.run_build()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(
            critical_constraint,
            res.stdout,
            "Critical author constraint at the end of a long boundary list (>600 chars) was silently truncated!"
        )

    # -------------------------------------------------------------------------
    # TEST 3: Author Memory Loading from both 作者记忆/ and docs/作者记忆/
    # -------------------------------------------------------------------------
    def test_author_memory_markdown_files_loaded(self):
        """Test that Markdown files in both 作者记忆/ and docs/作者记忆/ are loaded with exact provenance."""
        mem1 = "# Ký ức: Tương tác\n- Slow-burn bắt buộc, không đốt cháy giai đoạn.\n"
        mem2 = "# Ký ức: Văn phong thoại\n- Đối thoại sắc bén nhưng không ác ý.\n"
        self.put('作者记忆/nhan_vat_va_tuong_tac.md', mem1)
        self.put('docs/作者记忆/van_phong_thoai.md', mem2)

        res = self.run_build()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Slow-burn bắt buộc", res.stdout)
        self.assertIn("nhan_vat_va_tuong_tac.md", res.stdout)
        self.assertIn("Đối thoại sắc bén nhưng không ác ý", res.stdout)
        self.assertIn("docs/作者记忆/van_phong_thoai.md", res.stdout)

    # -------------------------------------------------------------------------
    # TEST 4: Author Memory Scoping & Cache Filtering
    # -------------------------------------------------------------------------
    def test_author_memory_scoped_and_filtered(self):
        """Test that internal files, empty files, and mismatched book scopes are safely ignored."""
        # 1. File scoped to a different book via frontmatter
        foreign_mem = "---\nbook: OtherNovel\n---\n- Không nên xuất hiện ở TestStory.\n"
        self.put('作者记忆/foreign_book.md', foreign_mem)

        # 2. Empty file
        self.put('作者记忆/empty_note.md', "   \n\n   ")

        # 3. Cache/internal files starting with '.' or '_'
        self.put('作者记忆/.hidden.md', "- Bí mật ẩn\n")
        self.put('作者记忆/_template.md', "- Mẫu ghi chú\n")

        res = self.run_build()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Không nên xuất hiện ở TestStory", res.stdout)
        self.assertNotIn("Bí mật ẩn", res.stdout)
        self.assertNotIn("Mẫu ghi chú", res.stdout)
        self.assertIn("限定书目 'OtherNovel' 与当前项目 'TestStory' 不符", res.stdout)
        self.assertIn("跳过 作者记忆/empty_note.md（内容为空）", res.stdout)

    # -------------------------------------------------------------------------
    # TEST 5: Conflict Between Author Request and Outline
    # -------------------------------------------------------------------------
    def test_conflict_between_author_request_and_outline(self):
        """Test that an author's explicit current request overrides conflicting outline details."""
        author_req = "CẤM: Trong chương 5 Phong không được nhắc đến việc đi mua đồ lót."
        res = self.run_build('--request', author_req)
        self.assertEqual(res.returncode, 0, res.stderr)

        self.assertIn(author_req, res.stdout)
        self.assertNotIn("与细纲冲突以细纲为准", res.stdout)
        self.assertIn("OVERRIDE", res.stdout)
        self.assertIn("đồ lót", res.stdout)

    # -------------------------------------------------------------------------
    # TEST 6: Canon Conflict Warning vs Authorized Retcon
    # -------------------------------------------------------------------------
    def test_canon_conflict_warning_and_authorized_retcon(self):
        """Test that canon conflicts trigger clear warnings unless explicitly marked as [RETCON]."""
        context_with_canon = (
            "## 当前位置\n第5章\n"
            "## 长期约束\n- Trần Hoài Phong là con một trong gia đình\n"
            "## 核心角色状态\n- Phong: con một\n"
            "## 活跃伏笔\n无\n"
            "## 近三章速记\n第4章 xong\n"
            "## 下一章承诺\n无\n"
            "## 连贯性风险\n无\n"
        )
        self.put('追踪/上下文.md', context_with_canon)

        # 6a: Accidental conflict
        accidental_req = "Cho em trai của Phong xuất hiện gõ cửa căn hộ."
        res_accidental = self.run_build('--request', accidental_req)
        self.assertEqual(res_accidental.returncode, 0, res_accidental.stderr)
        self.assertIn("CANON CONFLICT", res_accidental.stdout)

        # 6b: Authorized retcon
        authorized_retcon = "[RETCON] Thay đổi: Cho em trai của Phong xuất hiện gõ cửa căn hộ."
        res_retcon = self.run_build('--request', authorized_retcon)
        self.assertEqual(res_retcon.returncode, 0, res_retcon.stderr)
        self.assertIn("AUTHORIZED RETCON", res_retcon.stdout)

    # -------------------------------------------------------------------------
    # TEST 7: Boundary Conflict Warning vs Authorized Override
    # -------------------------------------------------------------------------
    def test_boundary_conflict_warning_and_authorized_override(self):
        """Test conflict between current chapter request and long-term confirmed boundaries."""
        self.put('设定/题材定位.md', '## Tác giả đã chốt\n- CẤM: Phong làm bác sĩ phụ khoa.\n')

        # 7a: Accidental boundary breach
        accidental_req = "Phong đến phòng khám làm bác sĩ phụ khoa."
        res_accidental = self.run_build('--request', accidental_req)
        self.assertEqual(res_accidental.returncode, 0, res_accidental.stderr)
        self.assertIn("BOUNDARY CONFLICT", res_accidental.stdout)

        # 7b: Authorized boundary override
        authorized_req = "[OVERRIDE BOUNDARY] Cho Phong đến phòng khám làm bác sĩ phụ khoa."
        res_authorized = self.run_build('--request', authorized_req)
        self.assertEqual(res_authorized.returncode, 0, res_authorized.stderr)
        self.assertIn("AUTHORIZED BOUNDARY OVERRIDE", res_authorized.stdout)

    # -------------------------------------------------------------------------
    # TEST 8: False-Positive Noun Phrases Are Not Treated As Constraints
    # -------------------------------------------------------------------------
    def test_false_positive_noun_phrases_not_treated_as_constraints(self):
        """Test that compound nouns containing 'cấm'/'禁' (e.g. cấm địa, biển cấm, 禁地) are not false positives."""
        boundaries = (
            "## Tác giả đã chốt\n"
            "- Phong và Ân khám phá cấm địa cổ xưa ở bìa rừng.\n"
            "- An từng sống ở cấm cung thời phong kiến.\n"
            "- Chiếc xe mang biển cấm đỗ bên đường.\n"
            "- 主角进入宗门禁地修炼。\n"
        )
        self.put('设定/题材定位.md', boundaries)
        res = self.run_build()
        self.assertEqual(res.returncode, 0, res.stderr)
        # None of these noun phrases should trigger a fake conflict if a chapter request mentions 'cấm địa'
        res_req = self.run_build('--request', 'Phong đi dạo gần cấm địa.')
        self.assertNotIn("BOUNDARY CONFLICT", res_req.stdout)

    # -------------------------------------------------------------------------
    # TEST 9: Request Safety, Precedence, and Chapter Isolation
    # -------------------------------------------------------------------------
    def test_request_source_precedence_and_chapter_isolation(self):
        """Test that --request overrides file sources, stale requests from other chapters are not auto-discovered,
        and missing --request-file errors out cleanly."""
        # 9a: Create chapter 5 request file and chapter 4 request file
        ch5_req_file = self.put('.story/work/第005章/request.md', 'Yêu cầu cho chương 5 từ work dir.')
        self.put('.story/work/第004章/request.md', 'Yêu cầu cũ của chương 4.')
        root_req = self.put('request.md', 'Yêu cầu ở root.')

        # Build chapter 5 without CLI args -> should auto-discover chapter 5 request, NOT chapter 4 or root
        res_auto = self.run_build()
        self.assertEqual(res_auto.returncode, 0, res_auto.stderr)
        self.assertIn("Yêu cầu cho chương 5 từ work dir", res_auto.stdout)
        self.assertNotIn("Yêu cầu cũ của chương 4", res_auto.stdout)
        self.assertNotIn("Yêu cầu ở root", res_auto.stdout)

        # 9b: --request-file overrides auto-discovered chapter work dir
        custom_file = self.put('custom_req.md', 'Yêu cầu từ file đặc biệt.')
        res_file = self.run_build('--request-file', str(custom_file))
        self.assertEqual(res_file.returncode, 0, res_file.stderr)
        self.assertIn("Yêu cầu từ file đặc biệt", res_file.stdout)
        self.assertIn("已覆盖其他来源", res_file.stdout)

        # 9c: --request overrides both --request-file and work dir
        cli_req = "Yêu cầu tối cao từ CLI."
        res_cli = self.run_build('--request', cli_req, '--request-file', str(custom_file))
        self.assertEqual(res_cli.returncode, 0, res_cli.stderr)
        self.assertIn(cli_req, res_cli.stdout)
        self.assertIn("采用 --request，已覆盖其他来源", res_cli.stdout)

        # 9d: Missing --request-file returns non-zero error
        res_missing = self.run_build('--request-file', 'nonexistent_file.md')
        self.assertEqual(res_missing.returncode, 2)
        self.assertIn("指定的文件不存在", res_missing.stderr)

    # -------------------------------------------------------------------------
    # TEST 10: Budget Exhaustion Warning When Critical Rules Exceed 3500 Chars
    # -------------------------------------------------------------------------
    def test_budget_exhaustion_warning_when_critical_rules_exceed_3500_chars(self):
        """Test that when critical constraints exceed 3500 chars, an explicit warning is reported."""
        # Create 50 critical rules, each ~80 chars -> total > 4000 chars of critical rules
        heavy_rules = [f"- CẤM TUYỆT ĐỐI điều số {i:02d}: Không được vi phạm nguyên tắc an toàn số {i:02d} " + "x" * 40 for i in range(50)]
        full_text = "## Tác giả đã chốt\n" + "\n".join(heavy_rules)
        self.assertTrue(len(full_text) > 4000)
        self.put('设定/题材定位.md', full_text)

        res = self.run_build()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("超过 3500", res.stdout)
        self.assertIn("部分高优先条款已截断", res.stdout)

    # -------------------------------------------------------------------------
    # TEST 11: End-to-End Pipeline Integrity Test
    # -------------------------------------------------------------------------
    def test_end_to_end_prompt_pipeline_integrity(self):
        """Test full pipeline from input parameters to archived writer_prompt.md on disk."""
        self.put('设定/题材定位.md', '## Ranh giới sáng tác\n- CẤM: Phong bán bản quyền câu chuyện.\n')
        self.put('docs/作者记忆/nhan_vat.md', '# Ký ức\n- Nhân vật Phong ghét tiền bẩn.\n')
        ch_req = 'CẤM: Không cho Phong ký bất kỳ hợp đồng nào trong chương 5.'
        out_file = self.book / '.story/work/第005章/writer_prompt.md'

        res = self.run_build('--request', ch_req, '--out', str(out_file))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(out_file.is_file(), "Archived writer_prompt.md was not created on disk!")

        content = out_file.read_text(encoding='utf-8')
        # Verify all essential sections are present in the final prompt file on disk
        self.assertIn("——— 作者本轮要求 ———", content)
        self.assertIn(ch_req, content)
        self.assertIn("——— 作者已定", content)
        self.assertIn("CẤM: Phong bán bản quyền câu chuyện", content)
        self.assertIn("——— author_preferences", content)
        self.assertIn("docs/作者记忆/nhan_vat.md", content)
        self.assertIn("Nhân vật Phong ghét tiền bẩn", content)
        self.assertNotIn("与细纲冲突以细纲为准", content)


if __name__ == '__main__':
    unittest.main()
