"""Offline Qt event-loop benchmark, isolated processes and synthetic photos.

This offscreen test measures readiness and timer delivery, not physical display
FPS, hardware cold-cache startup, monitor DPI, or native input latency.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("FRAMESENSE_GUI_SOURCE_ROOT", str(ROOT)))


def export_baseline(ref):
    destination = ROOT / "work/gui-baseline"
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", "framesense"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    for name in listing.stdout.splitlines():
        if not name.endswith(".py"):
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        content = subprocess.run(
            ["git", "show", f"{ref}:{name}"], cwd=ROOT, capture_output=True, check=True
        )
        target.write_bytes(content.stdout)
    return destination


def fixture_pair():
    from benchmark import make_fixtures
    from PIL import Image

    reference = make_fixtures(ROOT / "work/performance/fixtures")[1]
    source = reference.with_name("synthetic-4912x3264-source.jpg")
    if not source.exists():
        with Image.open(reference) as image:
            transform = (
                [min(255, value + 8) for value in range(256)]
                + list(range(256))
                + [max(0, value - 3) for value in range(256)]
            )
            image.point(transform).save(source, quality=92)
    return reference, source


def worker(mode, reference, source):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    started = time.perf_counter()
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication

    qt_imported = time.perf_counter()
    app = QApplication([])
    app.setApplicationName("FrameSense GUI benchmark")
    if mode == "optimized":
        from framesense.ui.theme import apply_theme

        apply_theme(app)
    from framesense.ui.main_window import MainWindow

    if mode == "optimized":
        import tempfile

        temporary = tempfile.TemporaryDirectory(
            prefix="gui-benchmark-", dir=ROOT / "work"
        )
        temporary_path = Path(temporary.name)
        window = MainWindow(
            db_path=temporary_path / "benchmark.db",
            draft_path=temporary_path / "draft.json",
        )
    else:
        temporary = None
        window = MainWindow()
    window.show()
    app.processEvents()
    shown = time.perf_counter()
    errors = []
    if mode == "optimized":
        window.jobs.error.connect(
            lambda channel, error: errors.append(f"{channel}: {error}")
        )

    timer = QTimer()
    timer.setInterval(10)
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    ticks = []
    previous = [time.perf_counter()]

    def heartbeat():
        now = time.perf_counter()
        ticks.append(now - previous[0])
        previous[0] = now

    timer.timeout.connect(heartbeat)
    timer.start()

    def pump_for(seconds):
        until = time.perf_counter() + seconds
        while time.perf_counter() < until:
            app.processEvents()
            time.sleep(0.001)

    def measure():
        pump_for(0.04)
        ticks.clear()
        previous[0] = time.perf_counter()
        begin = previous[0]
        finished = [None]

        def run():
            try:
                if mode == "optimized":
                    window._guidance = None
                    window.load_path("ref", str(reference))
                    window.load_path("src", str(source))
                else:
                    from framesense.core.loader import load_image

                    window._ref = load_image(reference)
                    window.ref_view.set_image(window._ref.rgb)
                    window._src = load_image(source)
                    window.src_view.set_image(window._src.rgb)
                    window._update_stats()
                    window._analyze()
                    finished[0] = time.perf_counter()
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        QTimer.singleShot(0, run)
        while finished[0] is None:
            app.processEvents()
            if errors:
                raise RuntimeError("; ".join(errors))
            if (
                mode == "optimized"
                and window._guidance is not None
                and not window.jobs.busy
            ):
                finished[0] = time.perf_counter()
            if time.perf_counter() - begin > 180:
                raise TimeoutError(
                    "GUI import/analysis did not become ready within 180 seconds"
                )
            time.sleep(0.001)
        # The first overdue heartbeat after synchronous work is essential: it
        # captures a blocked event loop rather than falsely reporting no samples.
        pump_for(0.04)
        maximum = max(ticks, default=0)
        return {
            "ready_s": finished[0] - begin,
            "timer_interval_s": 0.010,
            "max_timer_gap_s": maximum,
            "max_timer_overdue_s": max(0, maximum - 0.010),
            "delivered_timer_samples": len(ticks),
        }

    first = measure()
    repeated = measure()
    timer.stop()
    from benchmark import peak_memory_bytes

    result = {
        "mode": mode,
        "qt_import_s": qt_imported - started,
        "qapp_window_show_events_s": shown - qt_imported,
        "startup_from_qt_import_s": shown - started,
        "first_pair_import_analysis": first,
        "repeated_pair_import_analysis": repeated,
        "peak_memory_bytes": peak_memory_bytes(),
        "qt_platform": app.platformName(),
        "cache": window.service.cache_info() if mode == "optimized" else None,
    }
    window.close()
    app.processEvents()
    if mode == "optimized":
        window.jobs.pool.waitForDone(5000)
    if temporary is not None:
        temporary.cleanup()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=("baseline", "optimized"))
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--baseline-ref", default="baseline-colorlab-20261014")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "work/gui-performance.json"
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.reference, args.source)))
        return
    reference, source = fixture_pair()
    baseline_source = export_baseline(args.baseline_ref)
    rows = []
    for mode in ("baseline", "optimized"):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.pop("FRAMESENSE_GUI_SOURCE_ROOT", None)
        if mode == "baseline":
            environment["FRAMESENSE_GUI_SOURCE_ROOT"] = str(baseline_source)
        started = time.perf_counter()
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                mode,
                "--reference",
                str(reference),
                "--source",
                str(source),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=420,
        )
        row = json.loads(result.stdout)
        row["process_wall_s"] = time.perf_counter() - started
        rows.append(row)
        print(
            f"{mode}: first ready {row['first_pair_import_analysis']['ready_s']:.3f}s, "
            f"max 10ms timer gap {row['first_pair_import_analysis']['max_timer_gap_s']:.3f}s, "
            f"peak {row['peak_memory_bytes'] / 1048576:.1f} MiB",
            flush=True,
        )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": sys.version,
        "platform": platform.platform(),
        "baseline_ref": args.baseline_ref,
        "fixture": "two distinct synthetic 4912x3264 JPEGs; no private photos",
        "measurement": "offscreen Qt processEvents; 10ms precise QTimer; one process per version; one first and one repeated pair",
        "limits": "not physical cold-cache startup, native display FPS, screen DPI or statistical confidence; timer gaps include OS/Python scheduling",
        "measurements": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
