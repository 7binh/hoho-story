# Agent Note: 长篇拆文文档五步精修

Status: implemented
Date: 2026-10-15

## Problem

16 份文档存在提取顺序混用、摘要缺口路由误写、合成阶段回读边界不一致，以及文风分项预算超过总预算的问题。部分方法说明把经验判断写成没有样本条件的结论。

## Decision

16 份文档逐文依次完成语言、赘述、歧义、信息断点、逻辑断点五步；以现有脚本和已落地管道为依据修正文档，保留阶段编号、字段、原文示例与网文专业术语。

## Alternatives considered

- 只改语句能缩小差异，但无法消除错误路由和前后矛盾，因此同时修复可核实的契约说明。

## Consequences

收益是章节提取、旧成果复用和文风生成的读取边界一致；代价是旧文档中的经验数值需要明确适用范围，不能继续充当普适质量结论。


## Verification

对照 manage_analysis_run.py 的 min_plot_points、stage_required_outputs、mark_stage_command，以及现有索引/旧成果路由核对。保留所有命令、枚举和阶段编号；经验比例仍保留作复核线索。修正摘要缺口路由、文本披露顺序、原文回读边界、散落情节归档和文风预算（1800+2100+100=4000）。原文案例和专业术语保留，去掉没有样本依据的通用倍速保证。

## Coverage

每份文档均按顺序完成：1 语言；2 赘述；3 歧义；4 代码/资料回查；5 逻辑核对。

| 文件 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `skills/story-long-analyze/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/author-facing.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/deconstruction-notes.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/final-checks.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/index-rebuild.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/inspiration-library.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/pipeline-ops.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/semantic-acceptance-fixtures.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/stage1-golden-chapters.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/stage2-extraction.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/stage3-plot-rhythm.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/stage4-characters-settings.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/stage5-report.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/style-profile-generator.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/style-profile-protocol.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `skills/story-long-analyze/references/synthesis-inputs.md` | ✓ | ✓ | ✓ | ✓ | ✓ |
