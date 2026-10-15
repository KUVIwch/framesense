"""照片优先的练习工作台，图像计算通过后台任务交付。"""

from __future__ import annotations
from dataclasses import asdict
from html import escape as esc
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from framesense.core.regions import Region, validate_region
from framesense.core.service import AnalysisService
from framesense.guidance.engine import generate_guidance
from framesense.guidance.models import GradingGuidance
from framesense.learning.draft import read_draft, write_draft
from framesense.learning.models import LearningSession
from framesense.learning.report import practice_markdown
from framesense.learning.session import (
    PROJECT_ROOT,
    create_session,
    get_session,
    list_session_summaries,
    update_session,
)
from framesense.ui.image_view import ImageView
from framesense.ui.resources import app_icon, brand_pixmap
from framesense.ui.tasks import TaskController
from framesense.ui.theme import apply_theme
from framesense.ui.widgets import ColorSwatchWidget, HistogramWidget

MODES = {"引导模式": "guided", "练习模式": "practice", "独立模式": "independent"}
IMAGE_FILTER = "照片 (*.jpg *.jpeg *.png *.arw)"


def text(value, name="muted"):
    widget = QLabel(value)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def btn(value, callback, name="quiet"):
    widget = QPushButton(value)
    widget.setObjectName(name)
    widget.clicked.connect(callback)
    return widget


class MainWindow(QMainWindow):
    def __init__(self, service=None, db_path=None, draft_path=None):
        super().__init__()
        self.setWindowTitle("FrameSense · Color Lab")
        self.setWindowIcon(app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(900, 620)
        self.service = service or AnalysisService()
        self.db_path = db_path
        self.draft_path = Path(
            draft_path or PROJECT_ROOT / "data" / "practice-draft.json"
        )
        self._ref = self._src = self._final = None
        self._ref_stats = self._src_stats = self._final_stats = None
        self._ref_region = self._src_region = None
        self._guidance = None
        self._analysis_json = {}
        self._hint_steps = set()
        self._region_undo = []
        self._session_id = None
        self._revision = 0
        self._closed = False
        self._restoring = False
        self._theme = "dark"
        self._measurement_details = False
        self.jobs = TaskController(self)
        self.jobs.result.connect(self._job_result)
        self.jobs.error.connect(self._job_error)
        self.jobs.busy_changed.connect(self._busy_changed)
        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.setInterval(600)
        self._draft_timer.timeout.connect(self._write_draft)
        self._build_ui()
        self._shortcuts()
        self._draft_available = read_draft(self.draft_path)
        self.restore_btn.setVisible(bool(self._draft_available))
        self._update_flow()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 16, 22, 12)
        root.setSpacing(14)
        header = QHBoxLayout()
        self.brand_label = QLabel()
        self.brand_label.setPixmap(brand_pixmap(180))
        header.addWidget(self.brand_label)
        header.addSpacing(24)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("未命名练习")
        self.title_edit.setMaximumWidth(320)
        self.title_edit.textChanged.connect(self._schedule_draft)
        header.addWidget(self.title_edit, 1)
        header.addStretch()
        self.btn_load = btn("练习记录", self._load_session)
        self.btn_save = btn("保存练习", self._save_session, "default")
        self.theme_btn = btn("浅色", self._toggle_theme)
        for w in (self.btn_load, self.btn_save, self.theme_btn):
            header.addWidget(w)
        root.addLayout(header)
        flow = QFrame()
        flow.setObjectName("toolbar")
        line = QHBoxLayout(flow)
        self.flow_label = text(
            "01  对照    /    02  观察    /    03  调整    /    04  复盘", "eyebrow"
        )
        self.flow_label.setWordWrap(False)
        line.addWidget(self.flow_label, 1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(list(MODES))
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        line.addWidget(self.mode_combo)
        root.addWidget(flow)
        line = QHBoxLayout()
        self.next_label = text("把照片放进来，从观察开始。")
        line.addWidget(self.next_label, 1)
        self.restore_btn = btn("恢复上次工作台", self._restore_draft)
        line.addWidget(self.restore_btn)
        root.addLayout(line)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.ref_view = ImageView()
        self.src_view = ImageView()
        self.ref_info = text("JPG · PNG · Sony ARW")
        self.src_info = text("可随时切换原片与调后作品")
        self.btn_ref = btn("放入参考作品", lambda: self._pick("ref"), "default")
        self.btn_src = btn("放入我的原片", lambda: self._pick("src"), "default")
        self.splitter.addWidget(
            self._photo_panel(
                "01 / REFERENCE", "参考作品", self.ref_view, self.ref_info, self.btn_ref
            )
        )
        self.splitter.addWidget(
            self._photo_panel(
                "02 / MY STUDY",
                "我的作品",
                self.src_view,
                self.src_info,
                self.btn_src,
                True,
            )
        )
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(285)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 16, 16, 12)
        side.setSpacing(10)
        side.addWidget(text("观察，再动手", "sectionTitle"))
        side.addWidget(text("把差异拆开看。每次先处理一件事。"))
        line = QHBoxLayout()
        self.btn_analyze = btn("看看差在哪", self._analyze, "primary")
        self.cancel_btn = btn("取消", self._cancel)
        self.cancel_btn.setEnabled(False)
        line.addWidget(self.btn_analyze, 1)
        line.addWidget(self.cancel_btn)
        side.addLayout(line)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        side.addWidget(self.tabs, 1)
        observation = QWidget()
        layout = QVBoxLayout(observation)
        layout.setContentsMargins(2, 12, 2, 4)
        layout.setSpacing(10)
        self.stats_text = QTextBrowser()
        self.stats_text.setFrameShape(QFrame.Shape.NoFrame)
        self.stats_text.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.stats_text)
        self.stats_text.setOpenLinks(False)
        self.stats_text.anchorClicked.connect(self._measurement_clicked)
        layout.addWidget(text("亮度分布 / 铜色：参考 · 青灰：原片", "eyebrow"))
        self.hist_ref = HistogramWidget()
        self.hist_src = HistogramWidget()
        self.hist_src.hide()
        layout.addWidget(self.hist_ref)
        self.swatch_ref = ColorSwatchWidget()
        self.swatch_src = ColorSwatchWidget()
        layout.addWidget(text("参考主色（前 5 项）", "eyebrow"))
        layout.addWidget(self.swatch_ref)
        layout.addWidget(text("原片主色（前 5 项）", "eyebrow"))
        layout.addWidget(self.swatch_src)
        self.region_text = text("Shift 拖动取样，比较两张照片中含义相近的区域。")
        layout.addWidget(self.region_text)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(observation)
        self.tabs.addTab(scroll, "观察")
        steps = QWidget()
        layout = QVBoxLayout(steps)
        layout.setContentsMargins(2, 12, 2, 4)
        self.focus_combo = QComboBox()
        self.focus_combo.addItems(
            ["全部观察重点", "先看影调", "先看颜色", "只看对应区域"]
        )
        self.focus_combo.currentIndexChanged.connect(self._render_guidance)
        layout.addWidget(self.focus_combo)
        self.guidance_text = QTextBrowser()
        self.guidance_text.setOpenLinks(False)
        self.guidance_text.anchorClicked.connect(self._hint_clicked)
        self.guidance_text.setHtml(
            "<p>放入两张照片后，点「看看差在哪」。</p><p>建议是试调方向，最后由你判断。</p>"
        )
        layout.addWidget(self.guidance_text, 1)
        self.export_btn = btn("导出练习清单…", self._export_report)
        layout.addWidget(self.export_btn)
        self.tabs.addTab(steps, "步骤")
        notes = QWidget()
        layout = QVBoxLayout(notes)
        layout.setContentsMargins(2, 12, 2, 4)
        layout.addWidget(text("这次想学什么", "sectionTitle"))
        self.goal_edit = QLineEdit()
        self.goal_edit.setPlaceholderText("例如：让阴影更冷，保留肤色")
        self.goal_edit.textChanged.connect(self._schedule_draft)
        layout.addWidget(self.goal_edit)
        layout.addWidget(text("我的观察与试调记录", "eyebrow"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "先写下你的判断。调过哪些地方？哪些变化值得保留？"
        )
        self.notes_edit.textChanged.connect(self._schedule_draft)
        layout.addWidget(self.notes_edit, 1)
        layout.addWidget(text("文字自动留在本机草稿中；保存后可从练习记录继续。"))
        self.tabs.addTab(notes, "笔记")
        history = QWidget()
        layout = QVBoxLayout(history)
        layout.setContentsMargins(2, 12, 2, 4)
        layout.addWidget(text("回到一次练习", "sectionTitle"))
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(lambda _: self._open_history())
        layout.addWidget(self.history_list, 1)
        layout.addWidget(btn("打开选中的练习", self._open_history, "default"))
        layout.addWidget(btn("找回切换前的工作台", self._restore_previous))
        self.history_more = btn("再显示 30 条", lambda: self._refresh_history(True))
        layout.addWidget(self.history_more)
        self.tabs.addTab(history, "记录")
        self.tabs.currentChanged.connect(
            lambda i: self._refresh_history() if i == 3 else None
        )
        self.splitter.addWidget(self.sidebar)
        self.splitter.setSizes([440, 490, 350])
        root.addWidget(self.splitter, 1)
        controls = QHBoxLayout()
        self.sync_check = QCheckBox("联动查看")
        self.sync_check.setChecked(True)
        controls.addWidget(self.sync_check)
        self.select_check = QCheckBox("区域取样  R")
        self.select_check.toggled.connect(self.ref_view.set_selection_mode)
        self.select_check.toggled.connect(
            lambda value: self.src_view.set_selection_mode(
                value and self.display_combo.currentIndex() != 1
            )
        )
        controls.addWidget(self.select_check)
        controls.addWidget(btn("清除区域", self._clear_regions))
        controls.addWidget(btn("适合窗口  F", self._fit_both))
        controls.addStretch()
        self.gesture_hint = text("拖动平移 · 滚轮缩放 · Shift 拖动取样")
        self.gesture_hint.setWordWrap(False)
        controls.addWidget(self.gesture_hint)
        root.addLayout(controls)
        self.statusBar().showMessage("照片与练习记录都留在本机。")
        self.ref_view.file_dropped.connect(lambda path: self.load_path("ref", path))
        self.src_view.file_dropped.connect(lambda path: self.load_path("src", path))
        self.ref_view.region_selected.connect(lambda r: self._region_changed("ref", r))
        self.src_view.region_selected.connect(lambda r: self._region_changed("src", r))
        self.ref_view.viewport_changed.connect(
            lambda v: (
                self.src_view.set_viewport(v) if self.sync_check.isChecked() else None
            )
        )
        self.src_view.viewport_changed.connect(
            lambda v: (
                self.ref_view.set_viewport(v) if self.sync_check.isChecked() else None
            )
        )
        self.ref_view.selection_mode_changed.connect(self._selection_changed)
        self.src_view.selection_mode_changed.connect(self._selection_changed)
        self.ref_view.viewport_changed.connect(self._schedule_draft)
        self.src_view.viewport_changed.connect(self._schedule_draft)
        self.sync_check.toggled.connect(self._schedule_draft)
        self.focus_combo.currentIndexChanged.connect(self._schedule_draft)
        self.display_combo.currentIndexChanged.connect(self._schedule_draft)
        self.splitter.splitterMoved.connect(self._schedule_draft)

    def _photo_panel(self, eyebrow, title, view, info, import_btn, source=False):
        panel = QFrame()
        panel.setObjectName("imageWell")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(text(eyebrow, "eyebrow"))
        row = QHBoxLayout()
        row.addWidget(text(title, "sectionTitle"))
        row.addStretch()
        row.addWidget(import_btn)
        layout.addLayout(row)
        layout.addWidget(view, 1)
        layout.addWidget(info)
        if source:
            row = QHBoxLayout()
            self.display_combo = QComboBox()
            self.display_combo.addItems(["原片", "调后作品", "参考叠加"])
            self.display_combo.currentIndexChanged.connect(self._display_changed)
            row.addWidget(self.display_combo, 1)
            self.btn_final = btn("放入调后作品", lambda: self._pick("final"))
            row.addWidget(self.btn_final)
            layout.addLayout(row)
        else:
            layout.addWidget(text("参考是观察的起点，不必成为唯一答案。"))
        return panel

    def _shortcuts(self):
        for key, title, fn in [
            ("Ctrl+O", "参考作品", lambda: self._pick("ref")),
            ("Ctrl+Shift+O", "我的原片", lambda: self._pick("src")),
            ("Ctrl+S", "保存练习", self._save_session),
            ("Ctrl+Return", "分析差异", self._analyze),
            ("Ctrl+E", "导出清单", self._export_report),
            (
                "Ctrl+B",
                "观察栏",
                lambda: self.sidebar.setVisible(not self.sidebar.isVisible()),
            ),
        ]:
            action = QAction(title, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(fn)
            self.addAction(action)
        action = QAction("撤销区域选择", self)
        action.setShortcut(QKeySequence("Alt+Backspace"))
        action.triggered.connect(self._undo_region)
        self.addAction(action)

    def _pick(self, role):
        path, _ = QFileDialog.getOpenFileName(self, "选择照片", "", IMAGE_FILTER)
        if path:
            self.load_path(role, path)

    def _import_reference(self):
        self._pick("ref")

    def _import_source(self):
        self._pick("src")

    def _import_final(self):
        self._pick("final")

    def load_path(self, role, path):
        if role == "final" and (self._src is None or self.jobs.has_task("load:src")):
            self._status("先让原片就位，再放入这张照片的调后作品。")
            return
        if role == "src":
            self.jobs.cancel("load:final")
        self._revision += 1
        self.jobs.cancel("analysis")
        self.jobs.cancel("restore")
        self._status("正在打开照片，可继续查看工作台。")

        def load(token):
            image = self.service.load(path)
            token.check()
            return image, self.service.stats(image)

        self.jobs.submit("load:" + role, load)

    def _job_result(self, channel, result):
        if self._closed:
            return
        if channel.startswith("load:"):
            role = channel.split(":")[1]
            image, stats = result
            old = getattr(self, "_" + role)
            if (
                role in ("ref", "src")
                and old is not None
                and old.file_sha256 != image.file_sha256
            ):
                self._write_draft()
                self._session_id = None
                self._region_undo.clear()
            setattr(self, "_" + role, image)
            setattr(self, "_" + role + "_stats", stats)
            if role in ("ref", "src"):
                setattr(self, "_" + role + "_region", None)
                (self.ref_view if role == "ref" else self.src_view).set_region(None)
                self._guidance = None
                self._analysis_json = {}
                self._hint_steps.clear()
                self._render_guidance()
                if role == "src":
                    self._final = self._final_stats = None
                    self.display_combo.setCurrentIndex(0)
            if role == "ref":
                self.ref_view.set_image(
                    image.preview_rgb, original_size=(image.width, image.height)
                )
            if role == "final":
                self.display_combo.setCurrentIndex(1)
            self._display_changed()
            self._refresh_stats_text()
            self._update_flow()
            self._schedule_draft()
            self._status("照片已就位。可以先观察，也可以查看差异。")
            if self._ref is not None and self._src is not None:
                self._analyze(switch_tab=False)
        elif channel == "analysis":
            if result["revision"] != self._revision:
                return
            self._guidance = result["guidance"]
            self._analysis_json = result["analysis"]
            self._ref_stats, self._src_stats = result["stats"]
            self._render_guidance()
            self._refresh_stats_text()
            self._update_flow()
            self._schedule_draft()
            self._status("差异已整理。建议从影调开始，再看颜色。")
        elif channel == "history":
            rows, append = result
            if not append:
                self.history_list.clear()
            for row in rows:
                item = QListWidgetItem(
                    f"{row['title'] or '未命名练习'}\n{row['updated_at']} · {Path(row['source_path']).name}"
                )
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.history_list.addItem(item)
            self.history_more.setEnabled(len(rows) == 30)
            if not self.history_list.count():
                self._status("还没有保存的练习。照片就位后，按 Ctrl+S 保存。")
        elif channel == "restore":
            payload, images, stats, revision = result
            if revision == self._revision:
                self._apply_restored(payload, images, stats)

    def _job_error(self, channel, error):
        if not self._closed:
            self._status(f"这一步未完成：{error[:220]}。已有照片和笔记仍然保留。")

    def _busy_changed(self, busy):
        self.cancel_btn.setEnabled(busy)

    def _cancel(self):
        self._revision += 1
        self.jobs.cancel()
        self._status("已取消。正在解码的步骤会在结束后释放，结果不会替换当前照片。")

    def _analyze(self, checked=False, switch_tab=True):
        if self._ref is None or self._src is None:
            self._status("先放入参考作品和自己的原片。")
            return
        if switch_tab:
            self.tabs.setCurrentIndex(1)
        ref, src, final = self._ref, self._src, self._final
        rr, sr, revision = self._ref_region, self._src_region, self._revision

        def run(token):
            rs = self.service.stats(ref)
            token.check()
            ss = self.service.stats(src)
            token.check()
            cmp = self.service.compare(ref, src)
            token.check()
            regions = [self.service.regions(ref, rr, src, sr)] if rr and sr else []
            guidance = generate_guidance(rs, ss, regions or None)
            token.check()
            final_cmp = asdict(self.service.compare(ref, final)) if final else None
            return {
                "revision": revision,
                "guidance": guidance,
                "stats": (rs, ss),
                "analysis": {
                    "ref_stats": asdict(rs),
                    "src_stats": asdict(ss),
                    "region_diffs": regions,
                    "comparison": asdict(cmp),
                    "final_comparison": final_cmp,
                },
            }

        self.jobs.submit("analysis", run)

    def _render_guidance(self, *_):
        if not self._guidance:
            self.guidance_text.setHtml(
                "<p>放入照片，点「看看差在哪」。</p><p>也可以先在笔记里写下自己的判断。</p>"
            )
            return
        g = self._guidance
        parts = [f"<p><b>{esc(g.summary)}</b></p>"]
        if self.mode_combo.currentIndex() == 2:
            parts += [
                "<p>先在笔记里写下判断，再去 Camera Raw 试一次。导回调后作品，看看测量怎样变化。</p>"
            ]
        else:
            parts += ["<h4>测量与观察</h4>"]
            for obs in g.observations:
                kind = {"fact": "测量", "inference": "推测", "suggestion": "建议"}[
                    obs.kind
                ]
                parts.append(f"<p><small>{kind}</small><br>{esc(obs.description)}</p>")
            parts.append("<h4>操作建议</h4>")
            for index, s in enumerate(g.steps):
                focus = self.focus_combo.currentIndex()
                tonal = any(
                    word in s.target for word in ("亮度", "影调", "曝光", "对比")
                )
                if (
                    (focus == 1 and not tonal)
                    or (focus == 2 and tonal)
                    or (focus == 3 and "区域" not in s.target)
                ):
                    continue
                parts.append(
                    f"<h4>{s.order:02d}  {esc(s.target)}</h4><p>{esc(s.observed_difference)}</p>"
                )
                if (
                    self.mode_combo.currentIndex() == 1
                    and index not in self._hint_steps
                ):
                    parts.append(
                        f'<p><a href="hint:{index}">先想一想，再看这一步的提示 →</a></p>'
                    )
                    continue
                parts.extend(
                    [
                        f"<p><b>{esc(s.tool)}</b><br>{esc(s.action)}</p>",
                        f"<p><small>为什么</small><br>{esc(s.basis)}<br>{esc(s.goal)}</p>",
                        f"<p><small>调整后检查</small><br>{esc(s.observe_after)}</p>",
                        f"<p><small>留意：{esc(s.side_effects)}</small></p>",
                    ]
                )
        parts += [
            "<hr><p>" + "<br>".join(esc(v) for v in g.assumptions + g.warnings) + "</p>"
        ]
        self.guidance_text.setHtml("".join(parts))

    def _hint_clicked(self, url):
        if url.scheme() == "hint":
            try:
                self._hint_steps.add(int(url.path()))
            except ValueError:
                return
            self._render_guidance()

    def _mode_changed(self, *_):
        self._render_guidance()
        self._schedule_draft()

    def _refresh_stats_text(self):
        rs, ss = self._ref_stats, self._src_stats
        if rs:
            self.swatch_ref.set_colors(rs.dominant_colors)
        if ss:
            self.swatch_src.set_colors(ss.dominant_colors)
        self.hist_ref.set_histogram(
            rs.histogram_normalized if rs else [], ss.histogram_normalized if ss else []
        )
        lines = ["<h4>先看大关系</h4>"]
        for title, s in [("参考", rs), ("原片", ss)]:
            if s:
                lines.append(
                    f"<p>{title}　亮度 {s.mean_brightness:.0f}/255 · 暗部 {s.shadow_ratio*100:.0f}% · 色度 {s.mean_chroma:.1f}</p>"
                )
        cmp = self._analysis_json.get("comparison")
        final = self._analysis_json.get("final_comparison")
        if cmp:
            lines.append(
                f"<p>原片相对参考<br>亮度差 {cmp['mean_luma_delta']:+.1f} L* · 色度差 {cmp['mean_chroma_delta']:+.1f}<br>平均颜色 ΔE76 {cmp['mean_lab_delta_e']:.1f}</p>"
            )
            lines.append(
                '<p><small>全局统计受画面内容影响；请结合对应区域比较。</small> <a href="measure:toggle">测量说明</a></p>'
            )
            if self._measurement_details:
                lines.append(
                    f"<p><small>{esc(cmp.get('note',''))}<br>亮度 /255 使用编码 sRGB 的 Y′，不是线性光亮度或曝光 EV；亮度差 L* 使用 Lab 明度。</small></p>"
                )
        if cmp and final:
            delta = cmp["mean_lab_delta_e"] - final["mean_lab_delta_e"]
            direction = "缩小" if delta > 0 else "增加"
            lines.append(
                f"<h4>调整之后</h4><p>平均颜色差距{direction}了 {abs(delta):.1f} ΔE76。调后亮度差 {final['mean_luma_delta']:+.1f} L*，色度差 {final['mean_chroma_delta']:+.1f}。</p><p>这不是好坏评分。也看看高光、肤色与过渡，保留你有意做出的不同。</p>"
            )
        self.stats_text.setHtml("".join(lines))
        regions = self._analysis_json.get("region_diffs", [])
        self._adjust_stats_height()
        self.region_text.setText(
            f"对应区域 ΔE00 {regions[0]['delta_e_cie2000']:.1f}\n原片亮度差 {regions[0]['luma_delta']:+.1f} L*\n取样只比较你选中的颜色，不判断内容。"
            if regions
            else "Shift 拖动取样，比较含义相近的区域。"
        )

    def _display_changed(self, *_):
        if self._ref:
            self.ref_info.setText(self._image_info(self._ref))
        if self._src is None:
            return
        mode = self.display_combo.currentIndex()
        if mode == 1 and self._final is None:
            self.display_combo.setCurrentIndex(0)
            self._status("先放入调后作品，再来比较。")
            return
        image = self._final if mode == 1 else self._src
        self.src_view.set_image(
            image.preview_rgb,
            original_size=(image.width, image.height),
            preserve_viewport=True,
        )
        self.src_view.set_overlay(
            self._ref.preview_rgb if mode == 2 and self._ref else None, opacity=0.5
        )
        self.src_view.set_region(self._src_region if mode != 1 else None)
        self.src_view.set_selection_mode(self.select_check.isChecked() and mode != 1)
        self.src_info.setText(self._image_info(image))

    @staticmethod
    def _image_info(image):
        profile = {
            "embedded": "ICC → sRGB",
            "assumed": "按 sRGB 查看",
            "rawpy_srgb": "RAW → sRGB",
        }.get(image.profile_source, image.profile_source)
        return (
            f"{Path(image.source_path).name} · {image.width} × {image.height}\n{profile}"
            + (" · 色彩配置未能读取" if image.icc_error else "")
        )

    def _fit_both(self):
        self.ref_view.zoom_fit()
        self.src_view.zoom_fit()

    def _region_changed(self, role, region):
        if role == "src" and self.display_combo.currentIndex() == 1:
            return
        self._region_undo.append((self._ref_region, self._src_region))
        self._region_undo = self._region_undo[-30:]
        setattr(self, "_" + role + "_region", region)
        self._revision += 1
        self.jobs.cancel("analysis")
        self._schedule_draft()
        self._guidance = None
        self._render_guidance()
        self._update_flow()
        self._analysis_json.pop("region_diffs", None)
        self._refresh_stats_text()
        if self._ref is not None and self._src is not None:
            self._analyze(switch_tab=False)

    def _selection_changed(self, value):
        self.select_check.setChecked(value)
        if self.display_combo.currentIndex() == 1:
            self.src_view.set_selection_mode(False)

    def _undo_region(self):
        if not self._region_undo:
            return
        self._ref_region, self._src_region = self._region_undo.pop()
        self.ref_view.set_region(self._ref_region)
        self._display_changed()
        self._revision += 1
        self._analyze(switch_tab=False)
        self._schedule_draft()

    def _clear_regions(self):
        self._region_undo.append((self._ref_region, self._src_region))
        self._region_undo = self._region_undo[-30:]
        self._ref_region = self._src_region = None
        self.ref_view.set_region(None)
        self.src_view.set_region(None)
        self._revision += 1
        self._analyze(switch_tab=False)
        self._schedule_draft()

    def _update_flow(self):
        ready = self._ref is not None and self._src is not None
        self.btn_analyze.setEnabled(ready)
        self.btn_save.setEnabled(ready)
        self.export_btn.setEnabled(bool(self._guidance))
        value = "01 / 对照  把照片拖进对应位置，也可以点按钮选择。"
        if self._final is not None:
            value = "04 / 复盘  看看哪些变化值得保留，再记下自己的判断。"
        elif self._guidance:
            value = "03 / 调整  带着一两个重点去 Camera Raw，再放回调后作品。"
        elif ready:
            value = "02 / 观察  先看最大的差别，或选两块对应区域。"
        self.next_label.setText(value)

    def _snapshot(self):
        return {
            "schema": 1,
            "id": self._session_id,
            "title": self.title_edit.text(),
            "goal": self.goal_edit.text(),
            "notes": self.notes_edit.toPlainText(),
            "mode": MODES[self.mode_combo.currentText()],
            "theme": self._theme,
            "reference_path": self._ref.source_path if self._ref else "",
            "source_path": self._src.source_path if self._src else "",
            "final_path": self._final.source_path if self._final else None,
            "reference_region": asdict(self._ref_region) if self._ref_region else None,
            "source_region": asdict(self._src_region) if self._src_region else None,
            "guidance_json": self._guidance.model_dump() if self._guidance else {},
            "analysis_json": self._analysis_json,
            "hint_steps": sorted(self._hint_steps),
            "viewport_ref": self.ref_view.viewport(),
            "viewport_src": self.src_view.viewport(),
            "display": self.display_combo.currentIndex(),
            "sync": self.sync_check.isChecked(),
            "focus": self.focus_combo.currentIndex(),
            "splitter": self.splitter.sizes(),
        }

    def _schedule_draft(self, *_):
        if not self._restoring and not self._closed:
            if self.jobs.has_task("restore"):
                self._revision += 1
                self.jobs.cancel("restore")
            self._draft_timer.start()

    def _write_draft(self):
        payload = self._snapshot()
        if not any(
            payload[k]
            for k in ("reference_path", "source_path", "notes", "title", "goal")
        ):
            return
        try:
            write_draft(self.draft_path, payload)
        except OSError:
            self._status("草稿暂时无法写入，可用「保存练习」保留记录。")

    def _save_session(self):
        if self._ref is None or self._src is None:
            self._status("先放入参考作品和原片，再保存这次练习。")
            return
        p = self._snapshot()
        try:
            if self._session_id is None:
                self._session_id = create_session(
                    p["reference_path"],
                    p["source_path"],
                    p["mode"],
                    p["title"],
                    self.db_path,
                )
            old = get_session(self._session_id, self.db_path)
            session = LearningSession(
                id=self._session_id,
                title=p["title"],
                created_at=old.created_at if old else "",
                updated_at="",
                reference_path=p["reference_path"],
                source_path=p["source_path"],
                final_path=p["final_path"],
                mode=p["mode"],
                notes=p["notes"],
                reference_region=p["reference_region"],
                source_region=p["source_region"],
                guidance_json=p["guidance_json"],
                analysis_json={
                    **self._analysis_json,
                    "practice": {
                        k: p[k]
                        for k in (
                            "goal",
                            "hint_steps",
                            "viewport_ref",
                            "viewport_src",
                            "display",
                            "sync",
                            "focus",
                            "theme",
                            "splitter",
                        )
                    },
                },
            )
            update_session(session, self.db_path)
            self._write_draft()
            self._status("练习已保存 · " + (session.title or "未命名练习"))
        except Exception as exc:
            self._status(f"练习未能保存：{str(exc)[:150]}。工作台内容仍在。")

    def _load_session(self):
        self.tabs.setCurrentIndex(3)

    def _refresh_history(self, append=False):
        offset = self.history_list.count() if append else 0
        self.jobs.submit(
            "history",
            lambda token: (list_session_summaries(30, offset, self.db_path), append),
        )

    def _open_history(self):
        item = self.history_list.currentItem()
        if item is None:
            self._status("先选一条练习记录。")
            return
        session = get_session(item.data(Qt.ItemDataRole.UserRole), self.db_path)
        if session:
            payload = session.model_dump()
            payload.update(session.analysis_json.get("practice", {}))
            self.restore_payload(payload)

    def _restore_draft(self):
        if self._draft_available:
            self.restore_payload(self._draft_available)

    def _restore_previous(self):
        previous = read_draft(self.draft_path.with_name("previous-practice.json"))
        if previous:
            self.restore_payload(previous)
        else:
            self._status("还没有切换前的工作台。")

    def restore_payload(self, payload):
        payload = dict(payload)
        for key, title in [
            ("reference_path", "参考作品"),
            ("source_path", "原片"),
            ("final_path", "调后作品"),
        ]:
            if payload.get(key) and not Path(payload[key]).is_file():
                path, _ = QFileDialog.getOpenFileName(
                    self,
                    "重新找到" + title + "（取消会保留当前工作台）",
                    "",
                    IMAGE_FILTER,
                )
                if not path:
                    self._status("恢复暂未完成。当前练习仍保留。")
                    return
                payload[key] = path
        self._write_draft()
        self._revision += 1
        self.jobs.cancel()
        revision = self._revision

        def restore(token):
            images = {}
            stats = {}
            for role, key in [
                ("ref", "reference_path"),
                ("src", "source_path"),
                ("final", "final_path"),
            ]:
                token.check()
                if payload.get(key):
                    images[role] = self.service.load(payload[key])
                    token.check()
                    stats[role] = self.service.stats(images[role])
            return payload, images, stats, revision

        self.jobs.submit("restore", restore)
        self._status("正在恢复练习，照片就位后一起切换。")

    def _apply_restored(self, payload, images, stats):
        current = self._snapshot()
        if any(
            current[k]
            for k in ("reference_path", "source_path", "notes", "title", "goal")
        ):
            try:
                write_draft(
                    self.draft_path.with_name("previous-practice.json"), current
                )
            except OSError:
                self._status("无法备份当前工作台，暂未切换。")
                return
        self._restoring = True
        try:
            for role in ("ref", "src", "final"):
                setattr(self, "_" + role, images.get(role))
                setattr(self, "_" + role + "_stats", stats.get(role))
            self._session_id = payload.get("id")
            self.title_edit.setText(payload.get("title", ""))
            self.goal_edit.setText(payload.get("goal", ""))
            self.notes_edit.setPlainText(payload.get("notes", ""))
            self.mode_combo.setCurrentText(
                next(
                    (k for k, v in MODES.items() if v == payload.get("mode")),
                    "引导模式",
                )
            )
            self._ref_region = (
                Region(**payload["reference_region"])
                if payload.get("reference_region")
                else None
            )
            self._src_region = (
                Region(**payload["source_region"])
                if payload.get("source_region")
                else None
            )
            for role in ("ref", "src"):
                image = getattr(self, "_" + role)
                region = getattr(self, "_" + role + "_region")
                if image is not None and region is not None:
                    try:
                        setattr(
                            self,
                            "_" + role + "_region",
                            validate_region(region, (image.height, image.width)),
                        )
                    except ValueError:
                        setattr(self, "_" + role + "_region", None)
            self._hint_steps = set(payload.get("hint_steps", []))
            # Paths can point at files edited outside this app. Always recompute
            # from the decoded bytes instead of pairing old measurements with new photos.
            self._guidance = None
            self._analysis_json = {}
            if self._ref:
                self.ref_view.set_image(
                    self._ref.preview_rgb,
                    original_size=(self._ref.width, self._ref.height),
                )
            else:
                self.ref_view.clear()
            self.ref_view.set_region(self._ref_region)
            self.display_combo.setCurrentIndex(
                payload.get("display", 0)
                if self._final or payload.get("display") != 1
                else 0
            )
            if self._src:
                self._display_changed()
            else:
                self.src_view.clear()
            self._region_undo.clear()
            self.sync_check.setChecked(payload.get("sync", True))
            self.focus_combo.setCurrentIndex(payload.get("focus", 0))
            if payload.get("splitter"):
                self.splitter.setSizes(payload["splitter"])
            if payload.get("viewport_ref"):
                self.ref_view.set_viewport(payload["viewport_ref"])
            if payload.get("viewport_src"):
                self.src_view.set_viewport(payload["viewport_src"])
            self._theme = (
                payload.get("theme", "dark")
                if payload.get("theme") in ("dark", "light")
                else "dark"
            )
            apply_theme(QApplication.instance(), self._theme)
            self.brand_label.setPixmap(brand_pixmap(180, light=self._theme == "light"))
            self.theme_btn.setText("深色" if self._theme == "light" else "浅色")
            self._render_guidance()
            self._refresh_stats_text()
            self._update_flow()
            self.restore_btn.hide()
            self.tabs.setCurrentIndex(2)
        finally:
            self._restoring = False
        self._write_draft()
        self._status("练习已恢复。照片、取样区域与文字都已就位。")
        if self._ref is not None and self._src is not None:
            self._analyze(switch_tab=False)

    def _export_report(self):
        if not self._guidance:
            self._status("先看看差异，再导出清单。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存练习清单", "仿色练习.md", "Markdown (*.md)"
        )
        if path:
            try:
                Path(path).write_text(
                    practice_markdown(
                        self.title_edit.text(),
                        self.goal_edit.text(),
                        self._guidance,
                        self.notes_edit.toPlainText(),
                        self._analysis_json,
                    ),
                    encoding="utf-8",
                )
                self._status("练习清单已导出。")
            except OSError as exc:
                self._status(f"文件暂时无法保存：{exc}")

    def _toggle_theme(self):
        self._theme = "light" if self._theme == "dark" else "dark"
        apply_theme(QApplication.instance(), self._theme)
        self.brand_label.setPixmap(brand_pixmap(180, light=self._theme == "light"))
        self.theme_btn.setText("深色" if self._theme == "light" else "浅色")
        self._schedule_draft()

    def _status(self, value):
        self.statusBar().showMessage(value)

    def _measurement_clicked(self, url):
        if url.scheme() == "measure":
            self._measurement_details = not self._measurement_details
            self._refresh_stats_text()

    def _adjust_stats_height(self):
        self.stats_text.document().setTextWidth(
            max(200, self.stats_text.viewport().width())
        )
        self.stats_text.setFixedHeight(
            max(130, min(1000, int(self.stats_text.document().size().height()) + 32))
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "gesture_hint"):
            self.gesture_hint.setVisible(self.width() >= 1200)
            QTimer.singleShot(0, self._adjust_stats_height)

    def closeEvent(self, event):
        self._draft_timer.stop()
        self._write_draft()
        self._closed = True
        self.jobs.cancel()
        super().closeEvent(event)
