# 构建 Windows 预览程序

在项目自己的虚拟环境内运行：

```powershell
.venv\Scripts\python.exe tools/build_windows.py
```

产物为 `outputs/windows-0.3.0-preview/FrameSenseColorLab/FrameSenseColorLab.exe`，需保留整个目录。构建使用项目内PyInstaller，带原创ICO与SVG/PNG资源，排除WebEngine、QML、QtTest等当前不使用的模块。中间文件在work/，不覆盖旧dist/；不会打包.env、私人数据库或用户照片。

程序为目录包，Qt库以独立文件保留。打包后数据位于exe旁data/，不会静默复制开发目录的历史。请把程序放到可写目录；保存失败时状态栏提示，工作台内容保留。

## 可重复验证

源码与打包程序都支持仅用于验证的参数，素材会在指定报告目录生成，完全不接触真实照片和原数据库：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
outputs\windows-0.3.0-preview\FrameSenseColorLab\FrameSenseColorLab.exe --verify-package work\package-check\result.json
```

验证不同尺寸JPG、资源、后台分析、规则指导、SQLite保存、模式、主题与窗口渲染。它不能替代真机鼠标手感、不同DPI或实际RAW兼容性测试。最终结果见QA。

## 回退

旧原型源码基线为标签baseline-colorlab-20261014，早期在线版本为v0.1-streamlit。不要对现有工作区执行破坏性回退；需要旧版时在项目内work/中单独导出Git归档或使用新的检出目录。数据备份位于本机忽略的work/product-baseline/，不上传GitHub。

## 构建依赖隔离

`packaging/colorlab.spec` 与构建脚本共同排除旧原型的OpenCV、pandas、Arrow、Streamlit和OpenAI客户端。构建子进程去掉外部Poppler的PATH项，并排除误收集的icuuc.dll/icudt78.dll，避免遮蔽Qt所需的Windows系统ICU接口。不会复制或改写System32文件，也不会修改全局PATH。

这是实际DLL加载失败后的修复，不是以“exe进程存活”代替验收。应用依赖的库许可证文本随目录包保留在THIRD_PARTY_LICENSES，版本列在THIRD_PARTY_NOTICES.txt。
