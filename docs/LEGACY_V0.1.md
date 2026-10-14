# 旧版 FrameSense V0.1 / V0.2 技术档案

本文档记录 Streamlit + AI 版本的技术结构、测试状态与遇到的问题。该版本已存档在 Git 标签 `v0.1-streamlit`，不再作为当前产品基线。

## 技术结构

```
framesense/
  analysis/        # 只读加载（JPG/PNG/ARW）、EXIF、图像统计
  ai/              # OpenAI 兼容视觉客户端（mock/openai/unisound）+ 能力验证 + 错误分类
  grading/         # 调色决策（Pydantic 结构化输出）
  web/app.py      # Streamlit 本地 Web 应用
  db.py            # SQLite 历史记录
  export.py       # Markdown 报告导出
  cli.py          # 命令行工具
```

## 功能

- 支持 JPG、PNG、Sony ARW 输入。
- 自动读取可用 EXIF（缺失不编造）。
- 亮度直方图、亮暗比例、色彩统计。
- 情绪关键词 1-3 个 + 1-3 张参考图。
- 云知声 U2 Flash 视觉模型生成结构化调色方案（Pydantic 校验）。
- 自定义 OpenAI 兼容模型 API。
- SQLite 历史记录、Markdown 导出。

## 测试状态（存档时）

- V0.1：89 项 pytest 通过。
- V0.2 阶段一：109 项 pytest 通过（新增视觉能力验证、错误分类、UI 测试）。

## 遇到的问题（已解决/已规避）

1. 云知声 U2 Flash 响应慢：超时提高到 300 秒、`max_tokens=4000`、关闭 `response_format`。
2. API Key 端点误配：从 OpenAI 官方改为云知声 MaaS。
3. Windows 控制台中文乱码：UTF-8 重配置。
4. pytest Windows 临时目录权限错误：改用项目内 `--basetemp`。
5. Streamlit 模块缓存：改代码后需重启；增加代码更新提示。
6. Mock 模式误发真实请求：UI 测试发现并修复。

## 为什么被替代

产品方向从“AI 自动修图建议”转向“离线仿色学习”。Streamlit + 在线 AI 的架构不再适合新方向，因此被桌面离线架构替代。核心的图像加载、EXIF、统计思路被保留并重写进新的 `framesense/core`。
