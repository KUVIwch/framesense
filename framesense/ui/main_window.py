"""FrameSense · Color Lab 主窗口。"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from framesense.core.compare import compare_images
from framesense.core.loader import load_image
from framesense.core.regions import Region, compute_region_stats, region_difference
from framesense.core.stats import compute_image_stats
from framesense.guidance.engine import generate_guidance
from framesense.learning.models import LearningSession, RegionSpec
from framesense.learning.session import (
    create_session,
    get_session,
    list_sessions,
    update_session,
)
from framesense.ui.image_view import ImageView
from framesense.ui.widgets import ColorSwatchWidget, HistogramWidget


class MainWindow(QMainWindow):
    """主窗口：左侧参考图、中央原片/最终作品、右侧分析与指导。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FrameSense · Color Lab")
        self.resize(1280, 820)
        self._ref = None
        self._src = None
        self._final = None
        self._ref_region: Region | None = None
        self._src_region: Region | None = None
        self._session_id: int | None = None
        self._build_ui()

    # ---------- UI 构建 ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.btn_ref = QPushButton("导入参考图")
        self.btn_src = QPushButton("导入原片")
        self.btn_final = QPushButton("导入最终作品（复盘）")
        self.btn_analyze = QPushButton("生成指导")
        self.btn_save = QPushButton("保存会话")
        self.btn_load = QPushButton("加载会话")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["引导模式", "练习模式", "独立模式"])
        for w in (
            self.btn_ref,
            self.btn_src,
            self.btn_final,
            self.btn_analyze,
            self.btn_save,
            self.btn_load,
        ):
            toolbar.addWidget(w)
        toolbar.addWidget(QLabel("学习模式："))
        toolbar.addWidget(self.mode_combo)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.ref_view = ImageView()
        self.src_view = ImageView()
        right = QTabWidget()
        splitter.addWidget(self._wrap_labeled(self.ref_view, "参考作品"))
        splitter.addWidget(self._wrap_labeled(self.src_view, "原片 / 最终作品"))
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, 1)

        # 右侧标签页
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        self.hist_ref = HistogramWidget()
        self.hist_src = HistogramWidget()
        self.swatch_ref = ColorSwatchWidget()
        self.swatch_src = ColorSwatchWidget()
        self.stats_text = QTextBrowser()
        stats_layout.addWidget(QLabel("参考图直方图"))
        stats_layout.addWidget(self.hist_ref)
        stats_layout.addWidget(QLabel("参考图主色"))
        stats_layout.addWidget(self.swatch_ref)
        stats_layout.addWidget(QLabel("原片直方图"))
        stats_layout.addWidget(self.hist_src)
        stats_layout.addWidget(QLabel("原片主色"))
        stats_layout.addWidget(self.swatch_src)
        stats_layout.addWidget(self.stats_text, 1)
        right.addTab(stats_tab, "客观分析")

        self.guidance_text = QTextBrowser()
        right.addTab(self.guidance_text, "调色指导")

        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("记录你的学习心得、调色过程与疑问……")
        notes_layout.addWidget(self.notes_edit)
        right.addTab(notes_tab, "学习笔记")

        # 信号
        self.btn_ref.clicked.connect(self._import_reference)
        self.btn_src.clicked.connect(self._import_source)
        self.btn_final.clicked.connect(self._import_final)
        self.btn_analyze.clicked.connect(self._analyze)
        self.btn_save.clicked.connect(self._save_session)
        self.btn_load.clicked.connect(self._load_session)
        self.ref_view.region_selected.connect(self._on_ref_region)
        self.src_view.region_selected.connect(self._on_src_region)

    @staticmethod
    def _wrap_labeled(view: QWidget, title: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        layout.addWidget(view)
        return container

    # ---------- 导入 ----------
    def _import_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择参考图", "", "图片 (*.jpg *.jpeg *.png *.arw)"
        )
        if not path:
            return
        try:
            self._ref = load_image(path)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            return
        self.ref_view.set_image(self._ref.rgb)
        self._update_stats()
        self._status(f"已导入参考图：{path}")

    def _import_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择原片", "", "图片 (*.jpg *.jpeg *.png *.arw)"
        )
        if not path:
            return
        try:
            self._src = load_image(path)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            return
        self.src_view.set_image(self._src.rgb)
        self._update_stats()
        self._status(f"已导入原片：{path}")

    def _import_final(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择调色后的最终作品", "", "图片 (*.jpg *.jpeg *.png)"
        )
        if not path:
            return
        try:
            self._final = load_image(path)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            return
        self.src_view.set_image(self._final.rgb)
        self._status(f"已导入最终作品：{path}（可复盘对比）")

    # ---------- 区域选择 ----------
    def _on_ref_region(self, region: object) -> None:
        self._ref_region = region
        if region is not None:
            self._status(f"参考图区域已选：{region}")

    def _on_src_region(self, region: object) -> None:
        self._src_region = region
        if region is not None:
            self._status(f"原片区域已选：{region}")

    # ---------- 分析 ----------
    def _analyze(self) -> None:
        if self._ref is None or self._src is None:
            QMessageBox.warning(self, "缺少图片", "请先导入参考图与原片。")
            return
        ref_stats = compute_image_stats(self._ref.rgb)
        src_stats = compute_image_stats(self._src.rgb)
        region_diffs: list[dict] = []
        if self._ref_region is not None and self._src_region is not None:
            try:
                rr = compute_region_stats(self._ref.rgb, self._ref_region)
                sr = compute_region_stats(self._src.rgb, self._src_region)
                region_diffs = [region_difference(rr, sr)]
            except Exception as exc:
                QMessageBox.warning(self, "区域无效", str(exc))
        guidance = generate_guidance(
            target_stats=ref_stats,
            source_stats=src_stats,
            region_diffs=region_diffs or None,
        )
        self._display_guidance(guidance)
        self._analysis_json = {
            "ref_stats": asdict(ref_stats),
            "src_stats": asdict(src_stats),
            "region_diffs": region_diffs,
        }
        self._status(f"已生成指导：{guidance.summary}")

    def _display_guidance(self, guidance) -> None:
        mode = self.mode_combo.currentText()
        html = [f"<h3>{guidance.summary}</h3>"]
        html.append("<h4>观察</h4><ul>")
        for obs in guidance.observations:
            html.append(f"<li>[{obs.kind}] {obs.description}</li>")
        html.append("</ul>")
        html.append("<h4>操作建议</h4><ol>")
        for step in guidance.steps:
            if mode == "独立模式":
                html.append(f"<li><b>{step.target}</b> ——（独立模式下隐藏具体操作，请先自行尝试）</li>")
            elif mode == "练习模式":
                html.append(
                    f"<li><b>{step.target}</b><br>观察：{step.observed_difference}"
                    f"<br><i>提示：点击展开操作（练习模式默认隐藏）</i></li>"
                )
            else:
                html.append(
                    f"<li><b>{step.target}</b><br>差异：{step.observed_difference}"
                    f"<br>依据：{step.basis}<br>目标：{step.goal}"
                    f"<br>工具：{step.tool}<br>操作：{step.action}"
                    f"<br>预期：{step.expected_effect}<br>副作用：{step.side_effects}"
                    f"<br>调整后观察：{step.observe_after}"
                    f"<br><small>证据等级：{step.evidence_level}</small></li>"
                )
        html.append("</ol>")
        html.append("<h4>前提与警告</h4><ul>")
        for warn in guidance.assumptions + guidance.warnings:
            html.append(f"<li>{warn}</li>")
        html.append("</ul>")
        self.guidance_text.setHtml("".join(html))

    # ---------- 统计展示 ----------
    def _update_stats(self) -> None:
        if self._ref is not None:
            stats = compute_image_stats(self._ref.rgb)
            self.hist_ref.set_histogram(stats.histogram_normalized)
            self.swatch_ref.set_colors(stats.dominant_colors)
        if self._src is not None:
            stats = compute_image_stats(self._src.rgb)
            self.hist_src.set_histogram(stats.histogram_normalized)
            self.swatch_src.set_colors(stats.dominant_colors)
        self._refresh_stats_text()

    def _refresh_stats_text(self) -> None:
        lines = []
        if self._ref is not None:
            s = compute_image_stats(self._ref.rgb)
            lines.append("参考图：" + self._stats_line(s))
        if self._src is not None:
            s = compute_image_stats(self._src.rgb)
            lines.append("原片：" + self._stats_line(s))
        if self._ref is not None and self._src is not None:
            cmp = compare_images(self._ref.rgb, self._src.rgb)
            lines.append(
                f"双图差异：直方图距离 {cmp.histogram_distance:.3f}，"
                f"平均 ΔE76 {cmp.mean_lab_delta_e:.1f}，亮度差 {cmp.mean_luma_delta:+.1f}"
            )
            if self._final is not None:
                cmp_final = compare_images(self._ref.rgb, self._final.rgb)
                lines.append(
                    f"复盘：最终作品与参考图 ΔE76 = {cmp_final.mean_lab_delta_e:.1f}"
                    f"（原片为 {cmp.mean_lab_delta_e:.1f}）"
                )
        self.stats_text.setPlainText("\n".join(lines))

    @staticmethod
    def _stats_line(s) -> str:
        return (
            f"亮度 {s.mean_brightness:.0f}/255，暗部 {s.shadow_ratio * 100:.0f}%，"
            f"亮部 {s.highlight_ratio * 100:.0f}%，饱和度 {s.mean_saturation:.2f}，"
            f"色度 C* {s.mean_chroma:.2f}"
        )

    # ---------- 会话 ----------
    def _save_session(self) -> None:
        if self._ref is None or self._src is None:
            QMessageBox.warning(self, "缺少图片", "请先导入参考图与原片。")
            return
        mode = {"引导模式": "guided", "练习模式": "practice", "独立模式": "independent"}[
            self.mode_combo.currentText()
        ]
        if self._session_id is None:
            self._session_id = create_session(
                reference_path=self._ref.source_path,
                source_path=self._src.source_path,
                mode=mode,
            )
        session = LearningSession(
            id=self._session_id,
            created_at="",
            updated_at="",
            reference_path=self._ref.source_path,
            source_path=self._src.source_path,
            final_path=self._final.source_path if self._final else None,
            mode=mode,
            notes=self.notes_edit.toPlainText(),
            reference_region=RegionSpec(
                x=self._ref_region.x,
                y=self._ref_region.y,
                width=self._ref_region.width,
                height=self._ref_region.height,
            )
            if self._ref_region
            else None,
            source_region=RegionSpec(
                x=self._src_region.x,
                y=self._src_region.y,
                width=self._src_region.width,
                height=self._src_region.height,
            )
            if self._src_region
            else None,
            guidance_json=getattr(self, "_analysis_json", {}),
            analysis_json={},
        )
        # 保留历史 created_at
        old = get_session(self._session_id)
        if old is not None:
            session.created_at = old.created_at
        update_session(session)
        self._status(f"会话已保存 #{self._session_id}")

    def _load_session(self) -> None:
        sessions = list_sessions(limit=50)
        if not sessions:
            QMessageBox.information(self, "无会话", "当前没有已保存的学习会话。")
            return
        items = [f"#{s.id} {s.title or s.reference_path}" for s in sessions]
        from PySide6.QtWidgets import QInputDialog

        choice, ok = QInputDialog.getItem(self, "加载会话", "选择会话：", items, 0, False)
        if not ok:
            return
        index = items.index(choice)
        session = sessions[index]
        self._session_id = session.id
        try:
            self._ref = load_image(session.reference_path)
            self._src = load_image(session.source_path)
            self.ref_view.set_image(self._ref.rgb)
            self.src_view.set_image(self._src.rgb)
            self.notes_edit.setPlainText(session.notes)
            self.mode_combo.setCurrentText(
                {"guided": "引导模式", "practice": "练习模式", "independent": "独立模式"}[session.mode]
            )
            self._update_stats()
            self._status(f"已加载会话 #{session.id}")
        except Exception as exc:
            QMessageBox.warning(self, "加载失败", f"请重新定位文件：{exc}")

    def _status(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)
