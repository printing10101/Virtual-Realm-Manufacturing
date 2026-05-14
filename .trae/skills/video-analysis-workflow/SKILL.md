---
name: "video-analysis-workflow"
description: "Complete video analysis workflow. Invoke when analyzing videos, generating breakdown reports, analyzing hook segments, or when user mentions video analysis, hook analysis, or needs video reports."
---

# Video Analysis Workflow

Complete video analysis skill combining shot breakdown, hook analysis, and report generation. Provides end-to-end support from video processing to professional analysis reports.

## Core Capabilities

### 1. Shot Breakdown

**Process video and extract shot/segment information:**
```bash
# Run breakdown on video
python scripts/video-breakdown.py "video.mp4" > breakdown.json

# Output contains:
{
  "duration": 30.5,
  "segment_count": 12,
  "resolution": "1920x1080",
  "segments": [...],
  "bgm_analysis": {
    "music_style": {"primary": "流行"},
    "emotion": {"primary": "欢快"},
    "tempo": {"bpm_estimate": 120}
  },
  "scene_analysis": {
    "primary_scene": "室内",
    "video_style": {"overall": "生活方式"},
    "platform_recommendations": [...]
  }
}
```

### 2. Hook Analyzer

**Analyze first 3 seconds of video for engagement:**
```bash
# Extract hook segments from breakdown
python scripts/analyze_hook_segments.py "breakdown.json" > hook_analysis.json

# Output contains:
{
  "overall_score": 7.5,
  "visual_impact": 8.0,
  "language_hook": 7.0,
  "emotion_trigger": 7.5,
  "information_density": 7.0,
  "rhythm_control": 8.0,
  "hook_type": "好奇型",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1"],
  "suggestions": ["建议1", "建议2"],
  "retention_prediction": "中：50-70%"
}
```

**5-Dimension Evaluation:**
- **Visual Impact**: First frame attractiveness
- **Language Hook**: Opening words effectiveness
- **Emotion Trigger**: Emotional resonance
- **Information Density**: Curiosity gap creation
- **Rhythm Control**: Pacing and timing

### 3. Report Generator

**Generate professional Markdown analysis reports:**
```bash
# Full report (breakdown + hook)
python scripts/generate_report.py breakdown.json hook_analysis.json > report.md

# Breakdown only report
python scripts/generate_report.py breakdown.json > report.md
```

**Report Structure:**
```markdown
# 视频分析报告

## 基本信息
- 视频时长、分镜数量、分辨率

## 前三秒钩子分析（核心）
- 综合评分
- 5维度评分表格
- 钩子类型
- 优势/不足/优化建议
- 留存预测

## 分镜概览
- 前10个分镜的概览表格

## BGM 分析
- 音乐风格、情绪基调、节拍

## 场景分析
- 主要场景、视频风格、目标受众
- 平台推荐

报告生成时间
```

## Complete Workflow

**Step 1: Breakdown**
```bash
python scripts/video-breakdown.py "video.mp4" > breakdown.json
```

**Step 2: Hook Analysis**
```bash
python scripts/analyze_hook_segments.py "breakdown.json" > hook_raw.json
# (Apply LLM scoring to hook_raw.json to get hook_analysis.json)
```

**Step 3: Generate Report**
```bash
python scripts/generate_report.py breakdown.json hook_analysis.json > report.md
```

## Use Cases

1. **Video Analysis Delivery**: Generate complete analysis documents for clients
2. **Creative Review**: Create structured video content review reports
3. **Competitive Analysis**: Batch generate competitor video analysis reports
4. **Hook Optimization**: Analyze and improve first 3 seconds engagement

## Input Formats

### breakdown.json (Required)
Must contain: `duration`, `segment_count`, `resolution`, `segments`, `bgm_analysis`, `scene_analysis`

### hook_analysis.json (Optional)
If missing, report shows "暂无数据" for hook analysis section

## Best Practices

- Always run breakdown first to extract video structure
- Hook analysis focuses on first 3 seconds only
- Generate full report only after both breakdown and hook analysis complete
- Use report for client delivery, internal review, or competitive analysis

## Common Triggers

- "Analyze this video"
- "Generate video report"
- "Break down video segments"
- "Analyze hook segments"
- "First 3 seconds analysis"
- "Video creative review"
- "Competitor video analysis"

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Hook analysis empty | Confirm hook_analysis.json was passed |
| Shot table empty | Confirm breakdown.json contains segments |
| BGM/scene shows N/A | Breakdown service may not have returned data |
| Report missing sections | Check both input files have correct format |
