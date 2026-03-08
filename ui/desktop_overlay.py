"""
desktop_overlay.py — BilalAgent v3.1 Phase 12
Always-on-top floating PyQt5 overlay that works over every application.
Replaces Chrome extension as the primary interaction UI.

Launch: python ui/desktop_overlay.py
   or:  python agent.py --overlay

Hotkeys:
    Ctrl+Space      — toggle show/hide
    Ctrl+Shift+S    — emergency stop
    Ctrl+Shift+B    — snap screen + open overlay
"""

import os
import sys
import json
import time
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QScrollArea,
    QGraphicsDropShadowEffect, QProgressBar, QFrame, QToolTip
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QPoint, QRect, QSize, QEasingCurve
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QCursor, QIcon,
    QPixmap, QTextCursor, QPalette, QFontDatabase
)

import psutil

# ─── Colors ──────────────────────────────────────────
BG_MAIN    = "#0d0d1a"
BG_TITLE   = "#1a1a2e"
BG_INPUT   = "#16162b"
BG_MSG_USR = "#4ECDC4"
BG_MSG_AGT = "#2d2d44"
BG_MSG_SYS = "#1a1a33"
FG         = "#e8e8f0"
FG_DIM     = "#7a7a9e"
ACCENT     = "#4ECDC4"
RED        = "#FF6B6B"
GREEN      = "#27ae60"
YELLOW     = "#f1c40f"
BLUE       = "#45B7D1"
ORANGE     = "#e67e22"

PERM_COLORS = {
    "click":         "#FF6B6B",
    "type":          "#4ECDC4",
    "scroll":        "#45B7D1",
    "extract":       "#96CEB4",
    "open_browser":  "#FFEAA7",
}


# ─── Overlay Singleton ────────────────────────────────

_overlay_instance = None


def get_overlay_instance():
    """Return the running AgentOverlay instance, or None if not started."""
    return _overlay_instance


# ─── Position Persistence ────────────────────────────
POS_FILE = os.path.join(PROJECT_ROOT, "memory", "overlay_position.json")

def load_position():
    try:
        with open(POS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None

def save_position(x, y):
    os.makedirs(os.path.dirname(POS_FILE), exist_ok=True)
    with open(POS_FILE, "w") as f:
        json.dump({"x": x, "y": y}, f)


# ═══════════════════════════════════════════════════════
#  AGENT WORKER — QThread
# ═══════════════════════════════════════════════════════

class AgentWorker(QThread):
    """Runs agent commands in background so the UI never freezes."""
    message_ready     = pyqtSignal(str, str)   # (text, type: "agent"|"user"|"system"|"error")
    permission_needed = pyqtSignal(dict)        # action dict
    action_complete   = pyqtSignal(dict)        # result dict
    status_update     = pyqtSignal(str, str)    # (text, color)
    screen_annotate   = pyqtSignal(dict)        # annotation instruction

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task = ""
        self._stop_flag = False

    def set_task(self, task: str):
        self._task = task
        self._stop_flag = False

    def emergency_stop(self):
        self._stop_flag = True

    def run(self):
        import io
        import contextlib

        task = self._task
        self.status_update.emit("Thinking...", YELLOW)

        capture = io.StringIO()
        try:
            from memory.db import init_db
            init_db()

            import yaml
            profile = {}
            try:
                profile_path = os.path.join(PROJECT_ROOT, "config", "profile.yaml")
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile = yaml.safe_load(f) or {}
            except Exception:
                pass

            if self._stop_flag:
                self.message_ready.emit("⛔ Stopped by user.", "system")
                self.status_update.emit("Ready", GREEN)
                return

            with contextlib.redirect_stdout(capture):
                from agent import handle_command
                result = handle_command(task, profile)

            output = capture.getvalue()
            # Extract the RESULT section if present
            if "RESULT:" in output:
                result_part = output.split("RESULT:")[-1].strip()
                # Also grab any useful prefix info
                prefix_lines = []
                for line in output.split("\n"):
                    if "Routing" in line or "TIMING" in line or "STEP" in line:
                        prefix_lines.append(line.strip())
                if prefix_lines:
                    self.message_ready.emit("\n".join(prefix_lines), "system")
                self.message_ready.emit(result_part.split("─" * 10)[0].strip(), "agent")
            elif output.strip():
                self.message_ready.emit(output.strip()[:2000], "agent")
            else:
                self.message_ready.emit("Done (no output).", "system")

        except Exception as e:
            self.message_ready.emit(f"Error: {e}", "error")
        finally:
            self.status_update.emit("Ready", GREEN)


# ═══════════════════════════════════════════════════════
#  SCREEN ANNOTATION — transparent full-screen overlay
# ═══════════════════════════════════════════════════════

class ScreenAnnotation(QWidget):
    """Full-screen transparent overlay for drawing crosshairs and regions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self._annotations = []  # list of dicts
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_out)

    def show_target(self, x, y, color="#FF6B6B", label=""):
        self._annotations = [{
            "type": "target", "x": x, "y": y,
            "color": color, "label": label, "pulse": 3
        }]
        self.show()
        self.raise_()
        self._fade_timer.start(2000)

    def show_region(self, x, y, w, h, color="#4ECDC4", label=""):
        self._annotations = [{
            "type": "region", "x": x, "y": y, "w": w, "h": h,
            "color": color, "label": label
        }]
        self.show()
        self.raise_()
        self._fade_timer.start(2000)

    def show_reading(self, x, y, w, h):
        self._annotations = [{
            "type": "reading", "x": x, "y": y, "w": w, "h": h
        }]
        self.show()
        self.raise_()
        self._fade_timer.start(1500)

    def _fade_out(self):
        self._fade_timer.stop()
        self._annotations = []
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for ann in self._annotations:
            if ann["type"] == "target":
                color = QColor(ann["color"])
                x, y = ann["x"], ann["y"]
                # Crosshair lines
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawLine(x - 30, y, x + 30, y)
                painter.drawLine(x, y - 30, x, y + 30)
                # Circle
                pen.setWidth(2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPoint(x, y), 18, 18)
                # Label
                if ann.get("label"):
                    painter.setPen(Qt.white)
                    painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                    text_rect = painter.fontMetrics().boundingRect(ann["label"])
                    bg_rect = QRect(x - text_rect.width()//2 - 6, y - 40,
                                     text_rect.width() + 12, text_rect.height() + 6)
                    painter.drawRoundedRect(bg_rect, 4, 4)
                    painter.drawText(bg_rect, Qt.AlignCenter, ann["label"])

            elif ann["type"] == "region":
                color = QColor(ann["color"])
                pen = QPen(color, 2, Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(ann["x"], ann["y"], ann["w"], ann["h"])
                if ann.get("label"):
                    painter.setPen(Qt.white)
                    painter.setFont(QFont("Segoe UI", 9))
                    painter.drawText(ann["x"] + 4, ann["y"] - 4, ann["label"])

            elif ann["type"] == "reading":
                pen = QPen(QColor(BLUE), 2)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(69, 183, 209, 30)))
                painter.drawRect(ann["x"], ann["y"], ann["w"], ann["h"])
                painter.setPen(Qt.white)
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(ann["x"] + 4, ann["y"] + ann["h"]//2, "Reading...")

        painter.end()


# ═══════════════════════════════════════════════════════
#  PERMISSION POPUP — cursor-positioned approval window
# ═══════════════════════════════════════════════════════

class PermissionPopup(QWidget):
    """Floating permission popup that appears near cursor."""

    decision_made = pyqtSignal(str, str)  # (task_id, decision)

    def __init__(self, action: dict, parent=None):
        super().__init__(parent)
        self.action = action
        self.task_id = action.get("task_id", "unknown")

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(380)

        self._build_ui()
        self._position_near_cursor()

        # Countdown timer
        self._timeout = 300  # 5 minutes
        self._elapsed = 0
        self._countdown = QTimer(self)
        self._countdown.timeout.connect(self._tick)
        self._countdown.start(1000)

    def _position_near_cursor(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.primaryScreen().geometry()
        x = cursor_pos.x() + 20
        y = cursor_pos.y() + 20
        # Keep on screen
        if x + 380 > screen.width():
            x = cursor_pos.x() - 400
        if y + self.sizeHint().height() > screen.height():
            y = cursor_pos.y() - self.sizeHint().height() - 20
        self.move(x, y)

    def _build_ui(self):
        action_type = self.action.get("action_type", "unknown")
        description = self.action.get("description", "No description")
        confidence = self.action.get("confidence", 0)
        border_color = PERM_COLORS.get(action_type, "#FF6B6B")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Container with border
        container = QFrame(self)
        container.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(20, 20, 40, 245);
                border: 2px solid {border_color};
                border-radius: 10px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(8)
        container_layout.setContentsMargins(14, 12, 14, 12)

        # Row 1: badge + description
        row1 = QHBoxLayout()
        badge = QLabel(action_type.upper())
        badge.setStyleSheet(f"""
            background-color: {border_color};
            color: #0d0d1a;
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: bold;
            font-size: 10px;
        """)
        badge.setFixedHeight(22)
        row1.addWidget(badge)
        row1.addStretch()
        container_layout.addLayout(row1)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {FG}; font-size: 13px;")
        container_layout.addWidget(desc_label)

        # Row 2: target coordinates
        ax, ay = self.action.get("x"), self.action.get("y")
        if ax is not None and ay is not None:
            coord_label = QLabel(f"🎯 at position ({ax}, {ay})")
            coord_label.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
            container_layout.addWidget(coord_label)

        # Row 3: confidence bar
        if confidence > 0:
            conf_layout = QHBoxLayout()
            conf_text = QLabel(f"Confidence: {int(confidence * 100)}%")
            conf_text.setStyleSheet(f"color: {FG_DIM}; font-size: 10px;")
            conf_layout.addWidget(conf_text)

            conf_bar = QProgressBar()
            conf_bar.setRange(0, 100)
            conf_bar.setValue(int(confidence * 100))
            bar_color = GREEN if confidence > 0.8 else (YELLOW if confidence > 0.5 else RED)
            conf_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #1a1a33;
                    border: none;
                    border-radius: 3px;
                    height: 6px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 3px;
                }}
            """)
            conf_bar.setTextVisible(False)
            conf_bar.setFixedHeight(6)
            conf_layout.addWidget(conf_bar)
            container_layout.addLayout(conf_layout)

        # Row 4: buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        btns = [
            ("Allow Once",    GREEN,    "allow"),
            ("Allow All 30m", ORANGE,   "allow_all"),
            ("Skip",          "#7f8c8d", "skip"),
            ("Stop",          RED,       "stop"),
            ("Edit →",        BLUE,      "edit"),
        ]
        for label, color, decision in btns:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 10px;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    opacity: 0.85;
                }}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, d=decision: self._decide(d))
            btn_layout.addWidget(btn)
        container_layout.addLayout(btn_layout)

        # Shortcuts hint
        hint = QLabel("Enter=Allow  A=All  S=Skip  Esc=Stop")
        hint.setStyleSheet(f"color: {FG_DIM}; font-size: 9px;")
        hint.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(hint)

        # Row 5: countdown
        self.countdown_label = QLabel(f"Auto-stopping in 5:00")
        self.countdown_label.setStyleSheet(f"color: {FG_DIM}; font-size: 9px;")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.countdown_label)

        self.countdown_bar = QProgressBar()
        self.countdown_bar.setRange(0, self._timeout)
        self.countdown_bar.setValue(self._timeout)
        self.countdown_bar.setTextVisible(False)
        self.countdown_bar.setFixedHeight(3)
        self.countdown_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #1a1a33; border: none; }}
            QProgressBar::chunk {{ background-color: {FG_DIM}; }}
        """)
        container_layout.addWidget(self.countdown_bar)

        main_layout.addWidget(container)

    def _tick(self):
        self._elapsed += 1
        remaining = self._timeout - self._elapsed
        if remaining <= 0:
            self._decide("stop")
            return
        mins, secs = divmod(remaining, 60)
        self.countdown_label.setText(f"Auto-stopping in {mins}:{secs:02d}")
        self.countdown_bar.setValue(remaining)

    def _decide(self, decision):
        self._countdown.stop()
        self.decision_made.emit(self.task_id, decision)
        # Post to bridge
        try:
            import requests
            requests.post("http://localhost:8000/permission/result", json={
                "task_id": self.task_id,
                "decision": decision
            }, timeout=2)
        except Exception:
            pass
        self.close()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Y):
            self._decide("allow")
        elif key == Qt.Key_A:
            self._decide("allow_all")
        elif key == Qt.Key_S:
            self._decide("skip")
        elif key == Qt.Key_Escape:
            self._decide("stop")
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════
#  MAIN OVERLAY WINDOW
# ═══════════════════════════════════════════════════════

class AgentOverlay(QMainWindow):
    """Floating always-on-top agent interface."""

    # Thread-safe signals — emitted from any thread, delivered on main thread
    permission_signal = pyqtSignal(dict)    # → _handle_permission_request
    progress_signal   = pyqtSignal(str, int)  # stage_text, percent → _update_progress

    def __init__(self):
        super().__init__()

        # Register singleton so PermissionGate can reach this window from any thread
        global _overlay_instance
        _overlay_instance = self
        self._permission_decisions = {}  # task_id -> decision string

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(380, 280)
        self.resize(400, 320)

        # Dragging state
        self._dragging = False
        self._drag_offset = QPoint()

        # Idle fade
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._go_idle)
        self._idle_timer.start(8000)
        self._is_idle = False

        # Worker
        self.worker = AgentWorker(self)
        self.worker.message_ready.connect(self._on_message)
        self.worker.status_update.connect(self._on_status)
        self.worker.permission_needed.connect(self._on_permission)
        self.permission_signal.connect(self._handle_permission_request)
        self.progress_signal.connect(self._update_progress)

        # Screen annotation layer
        self.annotation = ScreenAnnotation()

        # Active permission popup reference
        self._perm_popup = None

        # Build UI
        self._build_ui()

        # Position
        self._load_position()

        # RAM timer
        self._ram_timer = QTimer(self)
        self._ram_timer.timeout.connect(self._update_ram)
        self._ram_timer.start(5000)
        self._update_ram()

        # Hotkeys
        self._register_hotkeys()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container frame
        self.container = QFrame(central)
        self.container.setStyleSheet(f"""
            QFrame#overlayContainer {{
                background-color: rgba(13, 13, 26, 240);
                border: 1px solid #333366;
                border-radius: 12px;
            }}
        """)
        self.container.setObjectName("overlayContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ─── Section 1: Title Bar ────────────────────
        title_bar = QFrame()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_TITLE};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)

        title_label = QLabel("🤖 BilalAgent")
        title_label.setStyleSheet(f"color: white; font-size: 11px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Minimize button
        btn_min = QPushButton("─")
        btn_min.setFixedSize(24, 24)
        btn_min.setStyleSheet(self._title_btn_style("#555"))
        btn_min.clicked.connect(self._minimize_to_tray)
        btn_min.setCursor(Qt.PointingHandCursor)
        title_layout.addWidget(btn_min)

        # Screen watch toggle
        self.btn_watch = QPushButton("◉")
        self.btn_watch.setFixedSize(24, 24)
        self.btn_watch.setStyleSheet(self._title_btn_style(BLUE))
        self.btn_watch.setToolTip("Toggle screen watch")
        self.btn_watch.setCursor(Qt.PointingHandCursor)
        self.btn_watch.clicked.connect(self._toggle_screen_watch)
        self._screen_watching = False
        title_layout.addWidget(self.btn_watch)

        # Close (hide) button
        btn_close = QPushButton("×")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(self._title_btn_style(RED))
        btn_close.clicked.connect(self.hide)
        btn_close.setCursor(Qt.PointingHandCursor)
        title_layout.addWidget(btn_close)

        container_layout.addWidget(title_bar)

        # ─── Section 2: Conversation Area ────────────
        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_MAIN};
                color: {FG};
                border: none;
                padding: 8px;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QScrollBar:vertical {{
                width: 4px;
                background: {BG_MAIN};
            }}
            QScrollBar::handle:vertical {{
                background: #333366;
                border-radius: 2px;
            }}
        """)
        container_layout.addWidget(self.conversation, 1)

        # Welcome message
        self._add_message("BilalAgent ready. Type a command below.", "system")

        # ─── Section 3: Input Bar ────────────────────
        input_frame = QFrame()
        input_frame.setFixedHeight(46)
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_INPUT};
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(4)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("What do you want to do...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_MAIN};
                color: {FG};
                border: 1px solid #333366;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-family: 'Segoe UI';
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
            }}
        """)
        self.input_field.returnPressed.connect(self._send_command)
        input_layout.addWidget(self.input_field, 1)

        # Voice button
        btn_voice = QPushButton("🎤")
        btn_voice.setFixedSize(32, 32)
        btn_voice.setStyleSheet(self._icon_btn_style())
        btn_voice.setToolTip("Voice input (coming soon)")
        btn_voice.setCursor(Qt.PointingHandCursor)
        input_layout.addWidget(btn_voice)

        # Snap screen button
        btn_snap = QPushButton("📸")
        btn_snap.setFixedSize(32, 32)
        btn_snap.setStyleSheet(self._icon_btn_style())
        btn_snap.setToolTip("Snap current screen")
        btn_snap.setCursor(Qt.PointingHandCursor)
        btn_snap.clicked.connect(self._snap_screen)
        input_layout.addWidget(btn_snap)

        # Send button
        btn_send = QPushButton("→")
        btn_send.setFixedSize(32, 32)
        btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {BG_MAIN};
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3db8b0;
            }}
        """)
        btn_send.setCursor(Qt.PointingHandCursor)
        btn_send.clicked.connect(self._send_command)
        input_layout.addWidget(btn_send)

        container_layout.addWidget(input_frame)

        # ─── Section 3b: Stage + Progress ────────────
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet(
            f"color: {FG_DIM}; font-size: 10px; padding: 0 8px;"
        )
        self.stage_label.hide()
        container_layout.addWidget(self.stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {BG_MAIN};
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT};
                border-radius: 1px;
            }}
        """)
        self.progress_bar.hide()
        container_layout.addWidget(self.progress_bar)

        # ─── Section 4: Status Bar ───────────────────
        status_frame = QFrame()
        status_frame.setFixedHeight(26)
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #111126;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 0, 12, 0)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {GREEN}; font-size: 10px;")
        status_layout.addWidget(self.status_dot)

        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet(f"color: {FG_DIM}; font-size: 10px;")
        status_layout.addWidget(self.status_text)

        status_layout.addStretch()

        self.ram_label = QLabel("RAM: --")
        self.ram_label.setStyleSheet(f"color: {FG_DIM}; font-size: 10px;")
        status_layout.addWidget(self.ram_label)

        self.mode_label = QLabel("Local")
        self.mode_label.setStyleSheet(f"color: {ACCENT}; font-size: 10px; font-weight: bold;")
        status_layout.addWidget(self.mode_label)

        container_layout.addWidget(status_frame)
        main_layout.addWidget(self.container)

    # ─── Styles ──────────────────────────────────────
    def _title_btn_style(self, color):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.1);
                border-radius: 4px;
            }}
        """

    def _icon_btn_style(self):
        return f"""
            QPushButton {{
                background-color: {BG_MAIN};
                border: 1px solid #333366;
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                border: 1px solid {ACCENT};
            }}
        """

    # ─── Conversation ────────────────────────────────
    def _add_message(self, text, msg_type="agent"):
        color_map = {
            "user":   BG_MSG_USR,
            "agent":  "#d4f5d4",
            "system": FG_DIM,
            "error":  RED,
        }
        align = "right" if msg_type == "user" else "left"
        text_color = "#0d0d1a" if msg_type == "user" else FG
        bg = BG_MSG_USR if msg_type == "user" else (BG_MSG_AGT if msg_type == "agent" else "transparent")

        # Sanitize HTML
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        if msg_type in ("user", "agent"):
            html = f"""
                <div style="text-align:{align}; margin: 4px 0;">
                    <span style="background-color:{bg}; color:{text_color};
                        padding: 6px 10px; border-radius: 10px;
                        display: inline-block; max-width: 320px;
                        font-size: 12px; line-height: 1.4;">
                        {safe_text}
                    </span>
                </div>
            """
        elif msg_type == "error":
            html = f"""
                <div style="text-align:left; margin: 2px 0;">
                    <span style="color: {RED}; font-size: 11px;">⚠ {safe_text}</span>
                </div>
            """
        else:
            html = f"""
                <div style="text-align:left; margin: 2px 0;">
                    <span style="color: {FG_DIM}; font-size: 10px;">{safe_text}</span>
                </div>
            """

        cursor = self.conversation.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.conversation.setTextCursor(cursor)
        self.conversation.insertHtml(html)
        self.conversation.ensureCursorVisible()

    # ─── Slots ───────────────────────────────────────
    def _send_command(self):
        text = self.input_field.text().strip()
        if not text or self.worker.isRunning():
            return
        self.input_field.clear()
        self._add_message(text, "user")
        self.worker.set_task(text)
        self.worker.start()

    def _on_message(self, text, msg_type):
        self._add_message(text, msg_type)

    def _on_status(self, text, color):
        self.status_text.setText(text)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px;")

    def _on_permission(self, action):
        self._perm_popup = PermissionPopup(action)
        self._perm_popup.decision_made.connect(self._on_perm_decision)
        self._perm_popup.show()

    def _on_perm_decision(self, task_id, decision):
        self._add_message(f"Permission: {decision.upper()} ({task_id})", "system")
        self._perm_popup = None

    # ─── Permission Gate Integration ──────────────────

    def show_permission_request(self, action: dict):
        """
        Thread-safe entry point called by PermissionGate from the worker thread.
        Emits signal → handled on main thread.
        """
        self.permission_signal.emit(action)

    def get_permission_decision(self, task_id: str):
        """
        Called by PermissionGate (worker thread) to check if overlay recorded a decision.
        Returns decision string or None if still pending.
        """
        return self._permission_decisions.get(task_id)

    def _handle_permission_request(self, action: dict):
        """
        Main-thread handler. Adds a notification to conversation and shows popup.
        """
        # Normalise keys — gate sends "action", PermissionPopup expects "action_type"
        action_type = action.get("action", action.get("action_type", "action")).upper()
        description = action.get("description", "Agent wants to perform an action")
        task_id     = action.get("task_id", "?")
        confidence  = action.get("confidence", 1.0)
        conf_pct    = int(confidence * 100)

        # Add waiting message to conversation
        self._add_message(
            f"🔐 [{action_type}] {conf_pct}% — {description}",
            "system"
        )

        # Build normalised dict for PermissionPopup (expects "action_type" key)
        normalised = dict(action)
        normalised["action_type"] = action_type.lower()

        # Show the existing PermissionPopup near cursor
        popup = PermissionPopup(normalised, parent=None)
        popup.decision_made.connect(self._on_gate_popup_decision)
        popup.show()
        popup.raise_()
        popup.activateWindow()
        # Keep reference so it is not garbage-collected
        self._perm_popup = popup

    def _on_gate_popup_decision(self, task_id: str, decision: str):
        """Slot for PermissionPopup.decision_made — records and shows result."""
        self._record_permission_decision(task_id, decision)

    def _record_permission_decision(self, task_id: str, decision: str):
        """Store decision so PermissionGate can pick it up during polling."""
        self._permission_decisions[task_id] = decision
        labels = {
            "allow":     "✓ ALLOWED",
            "allow_all": "⚡ ALLOW ALL (30m)",
            "skip":      "⏭ SKIPPED",
            "stop":      "✕ STOPPED",
            "edit":      "✏ EDIT",
        }
        self._add_message(f"  → {labels.get(decision, decision.upper())}", "system")
        print(f"  [OVERLAY] Permission {task_id}: {decision}")

    # ─── Progress Bar ──────────────────────────────────

    def _update_progress(self, stage: str, percent: int):
        """Update stage label and progress bar. Must run on main thread (via signal)."""
        if stage:
            self.stage_label.setText(stage)
            self.stage_label.show()
            self.progress_bar.setValue(max(0, min(100, percent)))
            self.progress_bar.show()
        else:
            self.stage_label.hide()
            self.progress_bar.hide()

    def _snap_screen(self):
        try:
            from tools.uitars_runner import capture_screen
            screen_b64 = capture_screen()
            self._add_message(f"📸 Screen captured ({len(screen_b64)//1024}KB)", "system")
            # Show reading animation
            screen = QApplication.primaryScreen().geometry()
            self.annotation.show_reading(0, 0, screen.width(), screen.height())
        except Exception as e:
            self._add_message(f"Snap failed: {e}", "error")

    def _toggle_screen_watch(self):
        self._screen_watching = not self._screen_watching
        if self._screen_watching:
            self.btn_watch.setStyleSheet(self._title_btn_style(GREEN))
            self._add_message("Screen watch: ON", "system")
        else:
            self.btn_watch.setStyleSheet(self._title_btn_style(BLUE))
            self._add_message("Screen watch: OFF", "system")

    def _minimize_to_tray(self):
        self.hide()

    def _update_ram(self):
        mem = psutil.virtual_memory()
        used = mem.used / (1024 ** 3)
        total = mem.total / (1024 ** 3)
        self.ram_label.setText(f"RAM: {used:.1f}/{total:.1f}GB")

    # ─── Dragging ────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 32:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            save_position(self.x(), self.y())

    # ─── Idle Fade ───────────────────────────────────
    def enterEvent(self, event):
        self._is_idle = False
        self.setWindowOpacity(0.95)
        self._idle_timer.start(8000)

    def leaveEvent(self, event):
        self._idle_timer.start(5000)

    def _go_idle(self):
        if not self.worker.isRunning():
            self._is_idle = True
            self.setWindowOpacity(0.4)

    # ─── Position ────────────────────────────────────
    def _load_position(self):
        pos = load_position()
        if pos:
            self.move(pos["x"], pos["y"])
        else:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.width() - 420, screen.height() - 360)

    # ─── Hotkeys ─────────────────────────────────────
    def _register_hotkeys(self):
        try:
            import keyboard as kb
            kb.add_hotkey("ctrl+space", self._toggle_visibility, suppress=False)
            kb.add_hotkey("ctrl+shift+s", self._emergency_stop, suppress=False)
            kb.add_hotkey("ctrl+shift+b", self._snap_and_show, suppress=False)
        except Exception:
            pass  # Hotkeys optional — may need admin on Windows

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.setWindowOpacity(0.95)
            self.input_field.setFocus()

    def _emergency_stop(self):
        self.worker.emergency_stop()
        self._add_message("⛔ Emergency stop triggered!", "error")
        self._on_status("Stopped", RED)

    def _snap_and_show(self):
        self.show()
        self.raise_()
        self.setWindowOpacity(0.95)
        self._snap_screen()
        self.input_field.setFocus()

    # ─── Test mode ───────────────────────────────────
    @staticmethod
    def run_test_mode():
        """Launch overlay for 4 seconds, then quit (for automated testing)."""
        app = QApplication(sys.argv)
        overlay = AgentOverlay()
        overlay.show()
        QTimer.singleShot(4000, app.quit)
        return app.exec_()


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = AgentOverlay()
    overlay.show()

    # Check/start bridge
    try:
        import requests
        resp = requests.get("http://localhost:8000/", timeout=2)
    except Exception:
        import subprocess
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "bridge.server:app", "--port", "8000", "--log-level", "warning"],
            cwd=PROJECT_ROOT,
            creationflags=0x08000000  # CREATE_NO_WINDOW on Windows
        )

    sys.exit(app.exec_())


if __name__ == "__main__":
    if "--test-mode" in sys.argv:
        sys.exit(AgentOverlay.run_test_mode())
    else:
        main()
