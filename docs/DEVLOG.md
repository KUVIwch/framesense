# 开发日志

## 2026-10-10 前后：项目萌芽

想法来自 Sony NEX-5N 的日常拍摄：照片“差了点感觉”，想找工具帮忙分析调色方向。

## 2026-10-13：V0.1 Streamlit 原型

- 实现 JPG/PNG/ARW 读取、EXIF、直方图、颜色统计。
- 接入云知声 MaaS（U2 Flash），实现结构化调色方案。
- SQLite 历史 + Markdown 导出。
- 89 项 pytest 通过；至少一次真实模型调用成功。

**遇到的问题：**

- 云知声 U2 Flash 响应慢，30 秒超时直接失败。把超时提高到 300 秒、设置 max_tokens=4000、关闭 `response_format` 后成功。
- 起初误把用户 Key 当 OpenAI 官方 Key，返回 401；改为云知声端点后正常。
- Windows 控制台中文乱码：对 stdout/stderr 做 UTF-8 重配置。
- pytest 的 Windows 临时目录出现权限错误（WinError 5），改用项目内 `--basetemp` 规避。根因未彻底定位。
- Streamlit 长驻进程缓存旧模块，改代码后必须重启；增加代码更新提示。
- UI 测试发现一个真实 bug：Mock 模式下侧边栏“模型模板”仍会用 .env 里的 Key 构造真实客户端，导致误发付费请求；已修复。

## 2026-10-14：产品转向，开始桌面重构

- 重新审视产品方向：不做大而全的修图软件，聚焦仿色学习。
- 初始化 Git 仓库，把 V0.1/V0.2 旧版保存为基线并打标签 `v0.1-streamlit`。
- 安装 PySide6、colour-science、PyInstaller。
- 开始搭建 `framesense/core`（加载、色彩管理、统计、双图对比、区域分析）、`framesense/guidance`（调色指导引擎）、`framesense/learning`（学习会话）。

## 后续阶段

- 阶段 B：色彩分析核心 + 测试。
- 阶段 C：调色教学引擎 + 测试。
- 阶段 D：PySide6 桌面界面。
- 阶段 E：仿色复盘与学习历史。
- 阶段 F：全量测试、文档、打包。
- 阶段 G：GitHub 提交与推送。

本日志会按实际进度继续补充。

## 2026-10-14：断网后继续

- 补完学习会话测试（7 项）。
- 新增离线 CLI（`framesense.cli`）与 PySide6 桌面 UI（`framesense/ui`、`framesense/app.py`）。
- UI 支持：双图导入、缩放/平移/矩形区域选择、直方图与主色样本、三模式指导展示、学习笔记、会话保存/加载、最终作品复盘对比。
- 新增 CLI 测试与 UI 冒烟测试（离屏渲染）。
- 当前测试：51 项通过。
- 下一步：README/BUILD 文档、PyInstaller 打包尝试、GitHub 推送（gh 未安装，需用户授权）。

## 2026-10-14：打包与 GitHub 归档完成

- PyInstaller 打包成功：`dist/FrameSenseColorLab/FrameSenseColorLab.exe`，并完成启动验证（进程正常存活）。
- 使用 Windows 凭据管理器中的 GitHub 凭据，创建公开仓库 `KUVIwch/framesense` 并推送全部提交。
- 最终全量测试：51 项通过。
- 本地与远程 `main` 分支 HEAD 一致（`e861b2b`）。

## 断网检查点：2026-10-14（暂停前状态）

**已完成并提交：**

- 阶段 A：初始化 Git；旧版 V0.1/V0.2 存档（tag `v0.1-streamlit`）；docs 历史文档。
- 阶段 B：离线核心 `framesense/core`（色彩管理/加载/统计/区域/双图对比），31 项测试通过。
- 阶段 C：调色教学引擎 `framesense/guidance`，5 项测试通过。
- 已提交 commit：`chore: archive ...`、`docs: record framesense project history`、`refactor: establish color lab architecture`、`feat: add grading guidance engine`。

**当前未提交（已创建、编译通过）：**

- `framesense/learning/`：学习会话 SQLite 持久化（models + session），**测试尚未编写**。

**下一步待完成：**

1. 补 `tests/learning/` 学习会话测试。
2. 阶段 D：PySide6 桌面 UI（`framesense/ui/`：主窗口、图像视图、直方图/颜色样本控件）。
3. 阶段 E：仿色复盘（导入最终作品、对比、标记有意差异）。
4. 阶段 F：全量测试、README、BUILD 文档、PyInstaller 打包尝试。
5. 阶段 G：GitHub 提交与推送（gh CLI 未安装、未认证，需要用户授权后处理）。

**当前测试状态**：36 项通过（31 core + 5 guidance）；learning 测试待补。

## 本轮产品化改造

基线为9e0ddde，标签baseline-colorlab-20261014；先运行51项原有测试，在项目work/product-baseline内用SQLite备份接口保存现有数据库。工作在feature/colorlab-product-polish分支进行，未重写旧历史。

审查发现不同尺寸双图比较会广播失败；统计多次在GUI线程运行；“拖动平移”和练习提示并未真正实现；区域恢复与成片恢复不完整。本轮逐一替换，保留早期文档与v0.1-streamlit标签。

视觉先做三套SVG并在小尺寸、深浅背景下检查，采用取景框与色彩切片。Qt离屏预览首次出现字体方框，原因是该测试平台枚举不到系统字体；预览脚本注册本机已有字体后修复，没有把字体打包进软件。深浅主题、照片中心布局和原生窗口均查看过。

界面重构后增加后台任务、有界缓存、模式提示、导出、原子草稿和完整记录恢复。独立审查发现恢复结果覆盖新输入、更换照片误更新旧练习、旧成片关联新原片、清除单侧区域还显示旧指导等实际问题，已修复并加回归。恢复记录现在重新分析当前文件，避免图片被外部修改后继续显示旧测量。恢复失败不替换现有草稿备份。

一次UI回归断言错误地要求成片视图显示原片取样框，修正为分别验证内存里的原片区域和当前展示的照片。Windows QTest.qWait在该环境可能让Python工作线程饥饿，测试等待改为处理事件并短暂让出GIL；没有用扩大超时掩盖产品竞态。

最终源代码回归132项通过。编译、格式和敏感路径检查通过；Black只装在项目虚拟环境并列为开发依赖。性能基准见PERFORMANCE：24MP核心工作流9.079→1.852秒，GUI离屏双图11.306→2.170秒；窗口启动略慢，未宣称全部指标改善。打包与最终远程归档状态见QA。

打包验证发现了原报告未覆盖的问题：进程启动并不代表GUI可用。初次实际运行在QtWidgets加载时失败。静态导出符号和独立DLL加载复现确认：构建环境PATH中的Poppler ICU78被误收进包，遮蔽Windows ICU接口，Qt缺少20个无版本后缀符号。Qt、Shiboken和VC库本身与源码环境哈希一致。

没有修改系统或全局PATH。构建脚本只清理子进程的Poppler搜索路径，spec明确排除错误ICU副本；缓存与临时目录也放在项目work内。去除无关OpenCV、pandas、Arrow和旧在线原型依赖后，完整包从旧版约498.5MiB降到约277MiB，仍需保留Qt/NumPy/SciPy运行库。修正后实际分析、保存与界面渲染验证通过，最后再进行干净重建验证。

最后的干净构建在offscreen与Windows原生平台都通过9项exe运行验收，正常退出。实际目录包约243.2MiB，旧dist约498.5MiB；没有把临时手工修包当最终构建。构建spec、PATH隔离、测试与设计性能文档一并归档；合成素材和测试报告留在忽略的work/和outputs/中。
