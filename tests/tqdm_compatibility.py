"""
Complete tqdm demonstration with a split-screen PySide6 viewer.

Left pane: this source code.
Right pane: live tqdm output from an isolated worker process.

Install:
    python -m pip install tqdm PySide6
Optional integrations:
    python -m pip install pandas
    python -m pip install dask
    python -m pip install tensorflow

Run:
    python tqdm_complete_demo.py

Run the demonstrations directly in a terminal:
    python tqdm_complete_demo.py --worker

Notes:
- Progress bars are forced on in the worker because redirected output is not a TTY.
- Optional integrations are skipped cleanly when their dependencies are absent.
- The download demonstration uses a local HTTP server; it does not contact the internet.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import logging
import math
import os
import re
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from tqdm.contrib.concurrent import process_map, thread_map
from tqdm.contrib.logging import logging_redirect_tqdm

from widgets.progress import tqdm
from widgets.progress import tqdm as trange
from widgets.progress.asyncio import tqdm_asyncio

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOGGER = logging.getLogger("tqdm_complete_demo")


def configure_logging() -> None:
    """Configure console logging; tqdm-aware redirection is used during demos."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
        force=True,
    )


# ---------------------------------------------------------------------------
# Small reusable workloads
# ---------------------------------------------------------------------------


def simulated_work(value: int) -> int:
    """Top-level function so it can also be used by process_map on Windows."""
    time.sleep(0.025)
    return value * value


def async_work(value: int) -> tuple[int, float]:
    """An asynchronous task with a small, variable delay."""
    return value, awaitable_delay(value)


def awaitable_delay(value: int) -> float:
    """Placeholder used only by the synchronous examples."""
    return math.sqrt(value)


async def async_job(value: int) -> tuple[int, int]:
    """An actual coroutine used by tqdm_asyncio.gather."""
    await asyncio.sleep(0.04 + (value % 4) * 0.015)
    return value, value * value


def number_generator(count: int) -> Iterator[int]:
    """A generator has no length, so its tqdm total must be supplied."""
    yield from range(count)


def log_section(title: str) -> None:
    """Print a visible section separator without corrupting active bars."""
    tqdm.write("")
    tqdm.write("=" * 72)
    tqdm.write(f"  {title}")
    tqdm.write("=" * 72)


# ---------------------------------------------------------------------------
# 1. Basic iterable progress bars, trange, and common iterables
# ---------------------------------------------------------------------------


def demo_iterables() -> None:
    log_section("1. ITERABLES: range, list, dict, trange, enumerate and zip")

    # tqdm automatically detects the length of ranges, lists and dictionaries.
    values = list(range(25))
    for value in tqdm(values, desc="List iteration", unit="item", disable=False):
        _ = value * value
        time.sleep(0.025)

    # trange is a convenient shorthand for tqdm(range(...)).
    for value in trange(15, desc="trange shorthand", unit="step", disable=False):
        _ = value + 1
        time.sleep(0.02)

    # Dictionaries iterate over keys unless .items() is used.
    records = {f"record-{i:02d}": i for i in range(12)}
    for key in tqdm(records, desc="Dictionary keys", unit="key", disable=False):
        _ = records[key]
        time.sleep(0.015)

    # tqdm wraps enumerate and zip without changing their values.
    names = [f"file_{i}.txt" for i in range(12)]
    sizes = [1024 * (i + 1) for i in range(12)]
    for index, (name, size) in enumerate(
        tqdm(
            zip(names, sizes, strict=False),
            total=len(names),
            desc="zip + enumerate",
            unit="file",
            disable=False,
        ),
        start=1,
    ):
        _ = (index, name, size)
        time.sleep(0.02)

    # A generator has no known length. Supply total to get percentage and ETA.
    for value in tqdm(
        number_generator(18),
        total=18,
        desc="Generator with total",
        unit="item",
        disable=False,
    ):
        _ = value
        time.sleep(0.02)


# ---------------------------------------------------------------------------
# 2. Manual progress, byte units, context managers and file I/O
# ---------------------------------------------------------------------------


def demo_manual_and_file_io() -> None:
    log_section("2. MANUAL UPDATE, BYTE UNITS, FILE I/O AND CONTEXT MANAGERS")

    # Manual update is useful when progress is driven by callbacks or events.
    with tqdm(total=100, desc="Manual task", unit="unit", disable=False) as bar:
        for completed in (5, 10, 15, 20, 25, 25):
            time.sleep(0.06)
            bar.update(completed)

    # Create a temporary file and read it in chunks, reporting bytes processed.
    payload = os.urandom(512 * 1024)
    with tempfile.TemporaryDirectory(prefix="tqdm-demo-") as temp_dir:
        file_path = Path(temp_dir) / "sample.bin"
        file_path.write_bytes(payload)
        file_size = file_path.stat().st_size

        with (
            file_path.open("rb") as source,
            tqdm(
                total=file_size,
                desc="Reading file",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                disable=False,
            ) as bar,
        ):
            while True:
                chunk = source.read(16 * 1024)
                if not chunk:
                    break
                # Update by actual bytes read, including a shorter final chunk.
                bar.update(len(chunk))
                time.sleep(0.015)


# ---------------------------------------------------------------------------
# 3. Appearance, custom format, postfix, dynamic description and tqdm.write
# ---------------------------------------------------------------------------


def demo_customization() -> None:
    log_section("3. CUSTOM FORMATTING, POSTFIX, ASCII, DYNAMIC DESC AND WRITE")

    # bar_format controls which fields appear. The available fields include
    # percentage, n, total, elapsed, remaining, rate and rate_fmt.
    custom_format = (
        "{desc}: {percentage:3.0f}% |{bar:30}| "
        "{n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
    )

    with tqdm(
        total=30,
        desc="Custom format",
        unit="row",
        bar_format=custom_format,
        ncols=110,
        mininterval=0.1,
        disable=False,
    ) as bar:
        for index in range(30):
            time.sleep(0.025)
            bar.update(1)
            # Postfix displays changing metrics to the right of the bar.
            bar.set_postfix(
                loss=f"{1 / (index + 1):.3f}",
                accuracy=f"{(index + 1) / 30:.1%}",
                refresh=False,
            )
            if index in (9, 19):
                # tqdm.write is safe while a bar is active; print() is not.
                tqdm.write(f"Checkpoint reached: {index + 1}/30")

    # ASCII bars are useful in consoles that do not render Unicode blocks.
    for _ in tqdm(
        range(18),
        desc="ASCII compatibility",
        unit="step",
        ascii=True,
        disable=False,
    ):
        time.sleep(0.02)

    # Dynamic descriptions can be changed as the task moves through stages.
    with tqdm(total=12, desc="Stage: initialise", unit="task", disable=False) as bar:
        for index in range(12):
            if index == 4:
                bar.set_description("Stage: transform")
            elif index == 8:
                bar.set_description("Stage: validate")
            time.sleep(0.035)
            bar.update(1)


# ---------------------------------------------------------------------------
# 4. Nested progress bars
# ---------------------------------------------------------------------------


def demo_nested_bars() -> None:
    log_section("4. NESTED PROGRESS BARS WITH position AND leave")

    # position assigns a terminal row. The outer bar remains visible while
    # the inner bar is refreshed on the next row.
    for chapter in tqdm(
        range(3),
        desc="Outer: chapters",
        position=0,
        leave=True,
        unit="chapter",
        disable=False,
    ):
        for _segment in tqdm(
            range(8),
            desc=f"Chapter {chapter + 1}: segments",
            position=1,
            leave=False,
            unit="segment",
            disable=False,
        ):
            time.sleep(0.035)


# ---------------------------------------------------------------------------
# 5. Performance controls: mininterval, miniters, smoothing and refresh
# ---------------------------------------------------------------------------


def demo_performance_controls() -> None:
    log_section("5. PERFORMANCE CONTROLS")

    # mininterval limits display refresh frequency. miniters controls how many
    # iterations occur between refresh checks. Leave dynamic miniters enabled
    # unless you have measured a reason to tune it manually.
    total = 20_000
    accumulator = 0
    for value in tqdm(
        range(total),
        desc="Fast loop (throttled)",
        unit="item",
        mininterval=0.5,
        miniters=1_000,
        smoothing=0.2,
        disable=False,
    ):
        accumulator += value

    tqdm.write(f"Fast-loop checksum: {accumulator}")

    # Dynamic_ncols adapts to the terminal width. ncols fixes it explicitly.
    for value in tqdm(
        range(15),
        desc="Fixed width",
        ncols=90,
        dynamic_ncols=False,
        unit="item",
        disable=False,
    ):
        _ = value
        time.sleep(0.02)

    # leave=False removes the completed bar; disable=True suppresses it.
    for value in tqdm(
        range(8),
        desc="Temporary bar (leave=False)",
        leave=False,
        unit="item",
        disable=False,
    ):
        _ = value
        time.sleep(0.025)

    # A disabled bar leaves the loop's behaviour unchanged.
    for value in tqdm(range(5), desc="Disabled example", disable=True):
        _ = value


# ---------------------------------------------------------------------------
# 6. pandas integration
# ---------------------------------------------------------------------------


def demo_pandas() -> None:
    log_section("6. PANDAS progress_apply (optional dependency)")

    try:
        import pandas as pd
    except ImportError:
        tqdm.write("SKIPPED: pandas is not installed. Install with: pip install pandas")
        return

    from tqdm import tqdm as base_tqdm

    # This patches pandas with progress_apply / progress_map methods.
    base_tqdm.pandas(desc="pandas progress_apply", mininterval=0.1)

    frame = pd.DataFrame(
        {
            "a": range(40),
            "b": [value * 3 for value in range(40)],
        }
    )

    def calculate_row(row):
        time.sleep(0.015)
        return math.sqrt(row["a"] ** 2 + row["b"] ** 2)

    frame["magnitude"] = frame.progress_apply(calculate_row, axis=1)
    tqdm.write(
        f"pandas result rows: {len(frame)}; last magnitude: {frame['magnitude'].iloc[-1]:.2f}"
    )


# ---------------------------------------------------------------------------
# 7. Asyncio integration
# ---------------------------------------------------------------------------


def demo_asyncio() -> None:
    log_section("7. ASYNCIO WITH tqdm.asyncio")

    async def run_tasks():
        tasks = [async_job(index) for index in range(18)]

        # tqdm_asyncio.gather tracks completion of asynchronous tasks.
        results = await tqdm_asyncio.gather(
            *tasks,
            desc="Async tasks",
            unit="task",
            disable=False,
        )
        return results

    results = asyncio.run(run_tasks())
    tqdm.write(f"Async tasks completed: {len(results)}")


# ---------------------------------------------------------------------------
# 8. Thread and process concurrency helpers
# ---------------------------------------------------------------------------


def demo_concurrency() -> None:
    log_section("8. CONCURRENT MAPPING: thread_map AND process_map")

    # thread_map is useful for I/O-bound tasks. It returns results in input order.
    thread_results = thread_map(
        simulated_work,
        range(16),
        max_workers=4,
        chunksize=1,
        desc="Thread pool",
        unit="task",
        disable=False,
    )
    tqdm.write(f"thread_map results: {len(thread_results)}")

    # process_map is useful for CPU-bound work. On Windows, keep process-starting
    # code behind the __main__ guard (as this demo does).
    process_results = process_map(
        simulated_work,
        range(12),
        max_workers=2,
        chunksize=1,
        desc="Process pool",
        unit="task",
        disable=False,
    )
    tqdm.write(f"process_map results: {len(process_results)}")


# ---------------------------------------------------------------------------
# 9. Logging integration
# ---------------------------------------------------------------------------


def demo_logging() -> None:
    log_section("9. LOGGING REDIRECTED THROUGH tqdm")

    logger = logging.getLogger("tqdm_complete_demo.example")
    logger.setLevel(logging.INFO)

    # logging_redirect_tqdm redirects logging output through tqdm.write(),
    # preventing log messages from corrupting the active progress bar.
    with logging_redirect_tqdm():
        for index in tqdm(range(8), desc="Logging-aware loop", unit="item", disable=False):
            logger.info("Processed item %d", index + 1)
            time.sleep(0.08)


# ---------------------------------------------------------------------------
# 10. Download callback integration (local HTTP server; no internet needed)
# ---------------------------------------------------------------------------


def demo_download_callback() -> None:
    log_section("10. DOWNLOAD CALLBACK WITH urllib.urlretrieve")

    data = os.urandom(384 * 1024)

    class DemoHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()

            # Stream the response in chunks to make the callback observable.
            for offset in range(0, len(data), 8 * 1024):
                self.wfile.write(data[offset : offset + 8 * 1024])
                self.wfile.flush()
                time.sleep(0.01)

        def log_message(self, format: str, *args: Any) -> None:
            # Keep the HTTP server's default request log out of the demo output.
            return

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        cast(type[BaseHTTPRequestHandler], DemoHandler),
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        from urllib.request import urlretrieve

        url = f"http://127.0.0.1:{server.server_port}/demo.bin"

        with tempfile.TemporaryDirectory(prefix="tqdm-download-") as temp_dir:
            destination = str(Path(temp_dir) / "download.bin")

            with tqdm(
                total=len(data),
                desc="Local download",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                disable=False,
            ) as bar:

                def report_hook(blocks_transferred=1, block_size=1, total_size=None):
                    # urlretrieve reports cumulative bytes. Update only the delta.
                    if total_size and bar.total != total_size:
                        bar.total = total_size
                        bar.refresh()
                    transferred = blocks_transferred * block_size
                    delta = transferred - bar.n
                    if delta > 0:
                        bar.update(min(delta, (bar.total or transferred) - bar.n))

                urlretrieve(url, destination, reporthook=report_hook)

            downloaded_size = Path(destination).stat().st_size
            tqdm.write(f"Downloaded {downloaded_size:,} bytes from the local test server.")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


# ---------------------------------------------------------------------------
# 11. Optional Keras and Dask integration patterns
# ---------------------------------------------------------------------------


def demo_optional_integrations() -> None:
    log_section("11. OPTIONAL KERAS AND DASK INTEGRATIONS")

    # Keras:
    #   from tqdm.keras import TqdmCallback
    #   model.fit(
    #       x_train, y_train,
    #       epochs=10,
    #       callbacks=[TqdmCallback(verbose=1)],
    #   )
    #
    # This is a callback integration, not a replacement for Keras metrics.
    try:
        from tqdm.keras import TqdmCallback

        tqdm.write("Keras tqdm callback is available (TensorFlow/Keras training not started).")
    except Exception as exc:
        tqdm.write(f"Keras integration unavailable: {type(exc).__name__}: {exc}")

    # Dask:
    #   from dask.diagnostics import ProgressBar
    #   from tqdm.dask import TqdmCallback
    #   with TqdmCallback(desc="Dask computation"):
    #       result = dask.compute(delayed_result)
    try:
        from tqdm.dask import TqdmCallback  # noqa: F401

        tqdm.write("Dask tqdm callback is available (no distributed job started).")
    except Exception as exc:
        tqdm.write(f"Dask integration unavailable: {type(exc).__name__}: {exc}")

    # Notebook-specific imports:
    #   from tqdm.notebook import tqdm as notebook_tqdm
    #   from tqdm.auto import tqdm as auto_tqdm
    #
    # tqdm.auto selects a notebook-friendly or console implementation based
    # on the environment. In this desktop app we use ordinary terminal tqdm.
    try:
        from tqdm.auto import tqdm as auto_tqdm  # noqa: F401

        tqdm.write("tqdm.auto is available for automatic notebook/terminal selection.")
    except Exception as exc:
        tqdm.write(f"tqdm.auto unavailable: {exc}")

    # tqdm.gui is an experimental GUI progress bar in a separate window.
    # This demo instead embeds normal tqdm output in the right-hand GUI pane.


# ---------------------------------------------------------------------------
# 12. Environment variables and test-friendly operation
# ---------------------------------------------------------------------------


def demo_environment_controls() -> None:
    log_section("12. ENVIRONMENT AND TEST-FRIENDLY CONTROLS")

    tqdm.write(f"tqdm version: {__import__('tqdm').__version__}")
    tqdm.write(f"TQDM_DISABLE environment value: {os.getenv('TQDM_DISABLE', '<not set>')}")
    tqdm.write("Set TQDM_DISABLE=1 to suppress tqdm output in automated test runs.")
    tqdm.write("For tests, you can also pass disable=True or inject a progress-bar class.")
    tqdm.write("The GUI worker forces bars on for this visual demonstration.")


# ---------------------------------------------------------------------------
# Execution tracing for the split-screen GUI
# ---------------------------------------------------------------------------


def enable_gui_execution_trace() -> None:
    """Send source line events to stdout for live highlighting in the GUI.

    tqdm and logging write to stderr. Keeping trace markers on stdout means the
    GUI can show executed source lines separately from progress-bar output.
    """
    source_file = str(Path(__file__).resolve())

    def trace(frame, event, arg):
        if event == "line":
            try:
                if str(Path(frame.f_code.co_filename).resolve()) == source_file:
                    # The GUI recognises this marker and does not display it as text.
                    sys.stdout.write(f"@@EXEC_LINE:{frame.f_lineno}\n")
                    sys.stdout.flush()
            except (OSError, RuntimeError):
                # Tracing must never interrupt the workload.
                pass
        return trace

    sys.settrace(trace)


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------


def run_all_demos() -> None:
    """Run every demonstration in a predictable order."""
    configure_logging()

    # Keep logging output and progress bars readable when they share stderr.
    with logging_redirect_tqdm():
        log_section("TQDM COMPLETE DEMONSTRATION")
        demo_iterables()
        demo_manual_and_file_io()
        demo_customization()
        demo_nested_bars()
        demo_performance_controls()
        demo_pandas()
        demo_asyncio()
        demo_concurrency()
        demo_logging()
        demo_download_callback()
        demo_optional_integrations()
        demo_environment_controls()
        log_section("ALL DEMONSTRATIONS COMPLETED")
        tqdm.write("The demo has finished successfully.")


# ---------------------------------------------------------------------------
# PySide6 split-screen viewer
# ---------------------------------------------------------------------------


def run_gui() -> int:
    """Display source on the left and live progress output on the right."""
    try:
        from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print(
            "PySide6 is required for the split-screen viewer.\n"
            "Install it with: python -m pip install PySide6",
            file=sys.stderr,
        )
        return 2

    class TqdmDemoWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Complete tqdm Demonstration — Code | Live Progress")
            self.resize(1500, 900)
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            self.process.readyReadStandardOutput.connect(self.read_execution_events)
            self.process.readyReadStandardError.connect(self.read_worker_output)
            self.process.finished.connect(self.worker_finished)
            self.process.errorOccurred.connect(self.worker_error)

            self.output_lines: list[str] = []
            self.current_line = ""
            self.active_source_line = 0
            self.progress_by_source_line: dict[int, str] = {}
            self.log_messages: list[str] = []
            self._stderr_buffer = ""

            root = QWidget()
            self.setCentralWidget(root)
            outer = QVBoxLayout(root)

            toolbar = QHBoxLayout()
            self.run_button = QPushButton("Run all demonstrations")
            self.stop_button = QPushButton("Stop")
            self.clear_button = QPushButton("Clear output")
            self.stop_button.setEnabled(False)
            self.status = QLabel("Ready")
            toolbar.addWidget(self.run_button)
            toolbar.addWidget(self.stop_button)
            toolbar.addWidget(self.clear_button)
            toolbar.addStretch(1)
            toolbar.addWidget(self.status)
            outer.addLayout(toolbar)

            splitter = QSplitter(Qt.Orientation.Horizontal)

            left_panel = QWidget()
            left_layout = QVBoxLayout(left_panel)
            left_layout.addWidget(QLabel("LEFT — Python source code"))
            self.source_view = QPlainTextEdit()
            self.source_view.setReadOnly(True)
            self.source_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.source_view.setFont(QFont("Consolas", 9))
            # Index only demo_* functions. The viewer switches to the function
            # currently executing instead of displaying the entire application.
            self.full_source = Path(__file__).read_text(encoding="utf-8")
            self.full_source_lines = self.full_source.splitlines()
            self.demo_functions: list[tuple[int, int, str]] = []
            syntax_tree = ast.parse(self.full_source)
            for node in syntax_tree.body:
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name.startswith("demo_"):
                    self.demo_functions.append(
                        (node.lineno, node.end_lineno or node.lineno, node.name)
                    )
            self.display_start_line = 1
            self.progress_anchor_line = 1
            self.current_demo_name = ""
            self.source_view.setPlainText("Select Run to display the active tqdm demo.")
            left_layout.addWidget(self.source_view)

            right_panel = QWidget()
            right_layout = QVBoxLayout(right_panel)
            right_layout.addWidget(
                QLabel("RIGHT — tqdm output aligned with the executing source line")
            )
            self.output_view = QPlainTextEdit()
            self.output_view.setReadOnly(True)
            self.output_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.output_view.setFont(QFont("Consolas", 9))
            right_layout.addWidget(self.output_view)

            splitter.addWidget(left_panel)
            splitter.addWidget(right_panel)
            splitter.setSizes([750, 750])
            outer.addWidget(splitter, 1)

            self.run_button.clicked.connect(self.start_worker)
            self.stop_button.clicked.connect(self.stop_worker)
            self.clear_button.clicked.connect(self.clear_output)

        def start_worker(self):
            if self.process.state() != QProcess.ProcessState.NotRunning:
                return

            self.output_lines.clear()
            self.current_line = ""
            self.progress_by_source_line.clear()
            self.log_messages.clear()
            self._stderr_buffer = ""
            self.current_demo_name = ""
            self.source_view.setPlainText("Waiting for the first tqdm demo…")
            self.output_view.clear()
            self.status.setText("Running…")
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            environment = QProcessEnvironment.systemEnvironment()
            environment.insert("PYTHONUNBUFFERED", "1")
            # Ensure progress bars remain enabled when output is captured by QProcess.
            environment.insert("TQDM_DISABLE", "0")
            self.process.setProcessEnvironment(environment)
            self.process.start(sys.executable, [str(Path(__file__).resolve()), "--worker"])

        def read_execution_events(self):
            """Consume source-line markers and highlight the currently executing line."""
            raw = self.process.readAllStandardOutput()
            text = raw.data().decode("utf-8", errors="replace")
            for line in text.splitlines():
                if line.startswith("@@EXEC_LINE:"):
                    try:
                        self.highlight_source_line(int(line.partition(":")[2]))
                    except ValueError:
                        continue

        def show_demo_function(self, line_number: int) -> None:
            """Show only the demo_* function containing the executing source line."""
            for start_line, end_line, function_name in self.demo_functions:
                if start_line <= line_number <= end_line:
                    if function_name != self.current_demo_name:
                        self.current_demo_name = function_name
                        self.display_start_line = start_line
                        self.progress_anchor_line = start_line
                        self.progress_by_source_line.clear()

                        snippet = "\n".join(self.full_source_lines[start_line - 1 : end_line])
                        self.source_view.setPlainText(snippet)
                        self.output_view.setPlainText("\n" * max(0, end_line - start_line))
                    return

        def highlight_source_line(self, line_number: int):
            """Highlight the active line and remember the tqdm call for bar alignment."""
            self.active_source_line = line_number
            self.show_demo_function(line_number)

            # Keep the anchor on the line that creates the current tqdm bar.
            # The trace then moves through the loop body while the bar continues
            # updating, so the last tqdm(...) line remains the correct row.
            if 1 <= line_number <= len(self.full_source_lines):
                code_line = self.full_source_lines[line_number - 1]
                if "tqdm(" in code_line or "trange(" in code_line:
                    self.progress_anchor_line = line_number

            from PySide6.QtGui import QTextCursor, QTextFormat
            from PySide6.QtWidgets import QTextEdit

            local_line = line_number - self.display_start_line + 1
            if local_line < 1 or local_line > self.source_view.document().blockCount():
                return

            cursor = QTextCursor(self.source_view.document())
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.MoveAnchor,
                local_line - 1,
            )

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.format.setBackground(self.palette().alternateBase())
            self.source_view.setExtraSelections([selection])
            self.source_view.setTextCursor(cursor)
            self.source_view.ensureCursorVisible()
            self.render_aligned_progress()

        def render_aligned_progress(self):
            """Show only actual tqdm bars, aligned with their tqdm source statements."""
            from PySide6.QtGui import QTextCursor

            source_line_count = self.source_view.document().blockCount()
            rows = [""] * source_line_count

            for absolute_line, progress_text in self.progress_by_source_line.items():
                local_line = absolute_line - self.display_start_line + 1
                if 1 <= local_line <= source_line_count:
                    rows[local_line - 1] = "│  " + progress_text

            self.output_view.setPlainText("\n".join(rows))

            # Scroll the output pane to the executing source row without adding
            # unrelated log messages or the rest of the application source.
            local_active_line = self.active_source_line - self.display_start_line + 1
            right_cursor = self.output_view.textCursor()
            right_cursor.movePosition(QTextCursor.MoveOperation.Start)
            right_cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.MoveAnchor,
                max(0, local_active_line - 1),
            )
            self.output_view.setTextCursor(right_cursor)
            self.output_view.ensureCursorVisible()

        def read_worker_output(self):
            """Capture tqdm redraws and place only progress-bar text beside its code."""
            raw = self.process.readAllStandardError()
            text = raw.data().decode("utf-8", errors="replace")
            # Strip terminal control sequences; the GUI presents aligned bars,
            # not general console output or worker logging.
            text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)

            for char in text:
                if char in ("\r", "\n"):
                    line = self._stderr_buffer.strip()
                    if line and ("|" in line or "%" in line or "it/s" in line or "B/s" in line):
                        self.progress_by_source_line[self.progress_anchor_line] = line
                    self._stderr_buffer = ""
                else:
                    self._stderr_buffer += char

            # tqdm often leaves the latest redraw without a newline.
            pending = self._stderr_buffer.strip()
            if pending and (
                "|" in pending or "%" in pending or "it/s" in pending or "B/s" in pending
            ):
                self.progress_by_source_line[self.progress_anchor_line] = pending

            self.render_aligned_progress()

        def worker_finished(self, exit_code, exit_status):
            self.read_execution_events()
            self.read_worker_output()
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            if exit_code == 0:
                self.status.setText("Completed")
            else:
                self.status.setText(f"Finished with exit code {exit_code}")
                QMessageBox.warning(
                    self,
                    "Demo finished",
                    f"The worker exited with code {exit_code} ({exit_status}).",
                )

        def worker_error(self, error):
            self.status.setText(f"Worker error: {error}")
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)

        def stop_worker(self):
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.process.terminate()
                if not self.process.waitForFinished(1500):
                    self.process.kill()
                self.status.setText("Stopped")

        def clear_output(self):
            self.output_lines.clear()
            self.current_line = ""
            self.progress_by_source_line.clear()
            self.log_messages.clear()
            self._stderr_buffer = ""
            self.output_view.clear()

        def closeEvent(self, event):
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.process.kill()
                self.process.waitForFinished(1000)
            event.accept()

    app = QApplication(sys.argv)
    window = TqdmDemoWindow()

    # Centre the window and use approximately 90% of available screen space.
    screen = app.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        width = int(geometry.width() * 0.90)
        height = int(geometry.height() * 0.90)
        window.resize(width, height)
        window.move(
            geometry.x() + (geometry.width() - width) // 2,
            geometry.y() + (geometry.height() - height) // 2,
        )

    window.show()
    return app.exec()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete tqdm feature demonstration.")
    parser.add_argument(
        "--worker",
        action="store_true",
        help="Run demonstrations in the terminal instead of opening the GUI.",
    )
    args = parser.parse_args()

    if args.worker:
        try:
            enable_gui_execution_trace()
            run_all_demos()
            return 0
        except KeyboardInterrupt:
            tqdm.write("Demo interrupted by user.")
            return 130
        except Exception:
            traceback.print_exc()
            return 1

    return run_gui()


if __name__ == "__main__":
    # Required on Windows when process_map starts child processes.
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())
