# FrameSense V0.2

FrameSense 是一个**本地优先的摄影分析与调色建议工具**，以摄影师创作意图为中心：上传一张照片，选择 1-3 个情绪关键词（可选参考作品），系统结合**客观技术数据、创作意图与参考图特征**生成结构化调色方案。

当前版本提供 **Streamlit 本地 Web 应用**与命令行工具两种入口；后续版本计划接入 Photoshop 自动控制（V0.2 阶段一不包含）。

## 核心功能

- **多格式只读输入**：JPG、PNG、Sony ARW（RAW 默认只在本地解码）。
- **自动读取可用 EXIF**：相机/镜头/ISO/快门/光圈/焦距/白平衡等；缺失字段一律不显示、AI 禁止编造。
- **客观图像统计**：亮度直方图、亮暗比例、色彩统计、主色、色偏估计、清晰度代理。
- **创作意图输入**：选择或输入 1-3 个情绪关键词，支持修改后重新生成建议。
- **参考作品分析**：支持 1-3 张参考图，提取统计特征参与调色决策。
- **结构化调色方案（Pydantic 校验）**：全局调整、色彩调整、局部调整、不应破坏的艺术特征、关键词映射、客观技术问题。
- **多种视觉模型 API**：默认 Mock（零网络/零费用）；可通过 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 接入任意 OpenAI 兼容端点。
- **界面内自定义模型 API**：无需改 `.env`，可在侧边栏直接填写 Base URL / API Key / 模型名；Key 仅本次会话内存使用，不落盘、不写入历史。
- **视觉能力验证**：程序生成已知内容图片（红圆+绿矩形），分别测试文本/图片/JSON 兼容性，确认模型是否真的“看得懂图”；结果保存到 `data/vision_capability_results.json`；真实测试默认关闭，需显式授权。
- **错误分类与有限重试**：区分超时/鉴权/限流/5xx/网络/解析错误；仅对限流、5xx、网络错误做有限重试。
- **单独配置视觉模型与文字整理模型**：`OPENAI_MODEL` 用于图片分析，`OPENAI_TEXT_MODEL` 用于格式修复等纯文本任务；支持 `FRAMESENSE_REASONING_EFFORT`。
- **结构化输出增强**：调整项带单位/适用软件/说明；记录模型耗时与 Token 用量；格式错误执行一次修复并标记 `repair`；真实/mock/修复三种状态明确区分。
- **分阶段进度与模型测试按钮**：生成过程显示 ①读取→②统计→③AI→④校验；侧边栏可一键测试当前模型能力并显示耗时与图片理解结果。
- **历史记录与导出**：SQLite 本地保存会话，支持导出 Markdown 报告。
- **隐私安全**：上传预览图到云模型前必须显式勾选授权；只上传最长边 ≤1024 像素的 JPEG 预览；API Key 仅从环境变量/`.env` 读取。

## 安全设计

- 所有文件操作仅发生在当前项目目录内；用户原始照片只在内存中处理，绝不写回。
- AI 不会编造 EXIF 参数；模型输出必须通过 Pydantic 校验，失败时明确报错、绝不伪造分析。
- 区分技术缺陷与刻意艺术表达：暗调/阴郁等意图下不会自动提亮暗部，也不会一律追求“标准白平衡”。
- 默认 Mock 模式不发起任何网络请求；RAW 原图默认只在本地处理。
- 无需管理员权限；依赖仅安装到项目 `.venv`。

## 环境要求

- Python 3.11+
- Windows / macOS / Linux

## 安装

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 快速开始（Web 应用）

```powershell
.venv\Scripts\streamlit run framesense/web/app.py
```

浏览器会自动打开 `http://localhost:8501`。上传照片 → 选择情绪关键词 → （可选）上传参考图 → 勾选是否允许云端预览 → 点击「生成调色建议」。

## 命令行工具（保留）

```powershell
.venv\Scripts\python.exe -m framesense demo           # 生成演示帧并 Mock 分析
.venv\Scripts\python.exe -m framesense analyze <目录> --ai-mode mock
.venv\Scripts\python.exe -m framesense info <图片>
```

## 视觉模型配置（可选）

复制 `.env.example` 为 `.env`，填写：

```
FRAMESENSE_VISION_MODE=openai
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEXT_MODEL=               # 可选：文字整理模型，不填复用 OPENAI_MODEL
FRAMESENSE_REASONING_EFFORT=     # 可选：none | low | medium | high
FRAMESENSE_JSON_MODE=false       # 部分兼容端点不支持 response_format 时设为 false
FRAMESENSE_MAX_TOKENS=4000
FRAMESENSE_REQUEST_TIMEOUT=300
FRAMESENSE_MAX_RETRIES=0
FRAMESENSE_DB_PATH=              # 可选：SQLite 数据库路径
```

`OPENAI_BASE_URL` 可换成任意 OpenAI 兼容端点（vLLM、Ollama、通义等）。不配置则使用 Mock 模式，零费用、零网络调用。

也可以在应用侧边栏的「自定义模型 API」直接填写 Base URL / API Key / 模型名，无需修改 `.env`；Key 只在当前页面内存中使用。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest
```

## 项目结构

```
framesense/
  analysis/           只读加载 / EXIF / 图像统计
  ai/                 AI 客户端（mock / openai 兼容 / unisound）+ 能力验证 + 错误分类
  grading/            调色决策与 Pydantic 输出模型
  web/app.py          Streamlit 本地 Web 应用
  db.py               SQLite 历史记录
  export.py           Markdown 报告导出
  cli.py  config.py  features.py  analyzer.py ...   # 保留的 CLI 工具
tests/               自动化测试
```

## 已知限制（V0.2 阶段一）

- 真实视觉模型需要网络与 API Key；默认 Mock 为规则化方案，非真实 AI 分析。
- ExifTool 为可选增强（将 `exiftool.exe` 放入 `.tools/` 或加入 PATH 即自动启用）；未安装时自动回退到 `exifread`。
- 参考图参与决策时目前使用统计特征；若勾选云端上传，预览图也会发送给模型。
- 暂不包含 Photoshop 自动操作（规划中）。
