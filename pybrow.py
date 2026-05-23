#!/usr/bin/env python3
"""
PyBrow — A modern, lightweight Python browser.
Built with PyQt5 + QtWebEngine. Follows system light/dark mode.
Compatible with YouTube, Google, Facebook, and most modern sites.
"""

import sys
import os
import json
import logging
import datetime
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import quote_plus

from PyQt5.QtCore import (
    QUrl, Qt, QPoint, QSettings, QByteArray, QTimer, QSize, pyqtSignal
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QAction, QMessageBox, QToolBar,
    QPushButton, QFileDialog, QMenu, QLabel, QProgressBar,
    QComboBox, QTabBar, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QShortcut, QSizePolicy, QFrame, QTextEdit,
    QScrollArea, QSplitter, QStatusBar
)
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineProfile,
    QWebEngineDownloadItem, QWebEngineSettings
)
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtGui import (
    QIcon, QKeySequence, QPixmap, QPalette, QColor, QFont, QFontDatabase
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("pybrow")

# ── Paths ────────────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".pybrow"
CONFIG_DIR.mkdir(exist_ok=True)
SETTINGS_FILE  = CONFIG_DIR / "settings.ini"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
HISTORY_FILE   = CONFIG_DIR / "history.json"
DOWNLOADS_DIR  = Path.home() / "Downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ── User agent (Chrome 124 on Windows — best compatibility) ──────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── Ad-block list ─────────────────────────────────────────────────────────────
# Blocked: pure tracking/ad networks that don't serve content users want.
# NOT blocked: googlevideo.com, ytimg.com, fbcdn.net, etc. — these serve actual
# media. Blocking them breaks YouTube free movies, Facebook video, etc.
ADBLOCK_DOMAINS = {
    # Display ad networks
    "doubleclick.net",
    "adnxs.com",           # AppNexus
    "outbrain.com",
    "taboola.com",
    "criteo.com",
    "moatads.com",
    "adsrvr.org",          # TradeDesk
    "rubiconproject.com",
    "openx.net",
    "pubmatic.com",
    "sharethrough.com",
    "lijit.com",
    "contextweb.com",
    "smartadserver.com",
    "bidswitch.net",
    "casalemedia.com",     # Index Exchange
    "serving-sys.com",     # Sizmek
    "yieldmo.com",
    "triplelift.com",
    "loopme.com",
    # Pure trackers (no content)
    "scorecardresearch.com",
    "quantserve.com",
    "chartbeat.com",
    "parsely.com",
    "hotjar.com",
    "mouseflow.com",
    "luckyorange.com",
    "crazyegg.com",
    # Analytics that don't affect site functionality
    # NOTE: google-analytics.com and googletagmanager.com intentionally excluded
    # because blocking them can break login flows and page JS on many sites.
}

# Paths that are always ads regardless of domain (e.g. /ads/..., /pagead/...)
ADBLOCK_PATH_PATTERNS = {
    "/pagead/",
    "/adserv",
    "/ad_iframe",
    "/doubleclick",
    "/adsystem/",
}

# Domains that must NEVER be blocked — serve real media/content
ADBLOCK_ALLOWLIST = {
    "googlevideo.com",     # YouTube video streams
    "ytimg.com",           # YouTube images/thumbnails
    "yt3.ggpht.com",       # YouTube avatars
    "fbcdn.net",           # Facebook CDN (videos, images)
    "cdninstagram.com",    # Instagram CDN
    "akamaized.net",       # Akamai CDN used by many video sites
    "fastly.net",          # Fastly CDN
    "cloudfront.net",      # AWS CloudFront
    "twimg.com",           # Twitter/X media
    "redd.it",             # Reddit media
    "twitchsvc.net",       # Twitch
    "jtvnw.net",           # Twitch streams
    "vimeocdn.com",        # Vimeo
    "dailymotioncdn.com",  # Dailymotion
}

SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Google":     "https://www.google.com/search?q={}",
    "Bing":       "https://www.bing.com/search?q={}",
    "Brave":      "https://search.brave.com/search?q={}",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Theme helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_dark_mode() -> bool:
    palette = QApplication.palette()
    bg = palette.color(QPalette.Window)
    return bg.lightness() < 128


def build_stylesheet(dark: bool) -> str:
    if dark:
        bg        = "#1c1c1e"
        bg2       = "#2c2c2e"
        bg3       = "#3a3a3c"
        text      = "#f2f2f7"
        text2     = "#aeaeb2"
        accent    = "#0a84ff"
        border    = "#48484a"
        tab_bg    = "#2c2c2e"
        tab_sel   = "#1c1c1e"
        tab_text  = "#aeaeb2"
        tab_stxt  = "#f2f2f7"
        bar_bg    = "#1c1c1e"
        input_bg  = "#2c2c2e"
        btn_hover = "#3a3a3c"
        close_x   = "#636366"
        prog_chunk= "#0a84ff"
        status_bg = "#2c2c2e"
    else:
        bg        = "#f2f2f7"
        bg2       = "#ffffff"
        bg3       = "#e5e5ea"
        text      = "#1c1c1e"
        text2     = "#6e6e73"
        accent    = "#007aff"
        border    = "#d1d1d6"
        tab_bg    = "#e5e5ea"
        tab_sel   = "#ffffff"
        tab_text  = "#6e6e73"
        tab_stxt  = "#1c1c1e"
        bar_bg    = "#f2f2f7"
        input_bg  = "#ffffff"
        btn_hover = "#e5e5ea"
        close_x   = "#8e8e93"
        prog_chunk= "#007aff"
        status_bg = "#f2f2f7"

    return f"""
    /* ── Global ── */
    QMainWindow, QDialog {{
        background: {bg};
        color: {text};
    }}
    QWidget {{
        font-family: -apple-system, "Segoe UI", "SF Pro Display", sans-serif;
        font-size: 13px;
        color: {text};
        background: transparent;
    }}

    /* ── Tab bar ── */
    QTabWidget::pane {{
        border: none;
        background: {bg};
    }}
    QTabWidget::tab-bar {{
        alignment: left;
    }}
    QTabBar {{
        background: {bar_bg};
        border-bottom: 1px solid {border};
    }}
    QTabBar::tab {{
        background: {tab_bg};
        color: {tab_text};
        padding: 7px 14px 7px 10px;
        min-width: 80px;
        max-width: 200px;
        border: none;
        border-right: 1px solid {border};
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background: {tab_sel};
        color: {tab_stxt};
        border-bottom: 2px solid {accent};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        background: {bg3};
        color: {text};
    }}
    QTabBar::close-button {{
        image: none;
    }}

    /* ── Toolbar ── */
    QToolBar {{
        background: {bar_bg};
        border: none;
        border-bottom: 1px solid {border};
        padding: 4px 6px;
        spacing: 4px;
    }}
    QToolBar QToolButton, QToolBar QPushButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 5px 7px;
        color: {text2};
        font-size: 16px;
        min-width: 28px;
        min-height: 28px;
    }}
    QToolBar QToolButton:hover, QToolBar QPushButton:hover {{
        background: {btn_hover};
        color: {text};
    }}
    QToolBar QToolButton:pressed, QToolBar QPushButton:pressed {{
        background: {bg3};
    }}
    QToolBar QToolButton:disabled, QToolBar QPushButton:disabled {{
        color: {border};
    }}

    /* ── Address bar ── */
    #AddressBar {{
        background: {input_bg};
        color: {text};
        border: 1.5px solid {border};
        border-radius: 8px;
        padding: 5px 12px;
        font-size: 13px;
        selection-background-color: {accent};
    }}
    #AddressBar:focus {{
        border-color: {accent};
    }}

    /* ── Find bar ── */
    #FindBar {{
        background: {bg2};
        border-top: 1px solid {border};
        padding: 4px 8px;
    }}
    #FindInput {{
        background: {input_bg};
        color: {text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    #FindInput:focus {{
        border-color: {accent};
    }}
    #FindLabel {{
        color: {text2};
        font-size: 12px;
        padding: 0 6px;
    }}

    /* ── Progress bar ── */
    QProgressBar {{
        border: none;
        background: transparent;
        height: 2px;
    }}
    QProgressBar::chunk {{
        background: {prog_chunk};
        border-radius: 1px;
    }}

    /* ── Menu ── */
    QMenuBar {{
        background: {bar_bg};
        color: {text};
        border-bottom: 1px solid {border};
        padding: 2px;
    }}
    QMenuBar::item:selected {{
        background: {btn_hover};
        border-radius: 4px;
    }}
    QMenu {{
        background: {bg2};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 5px 20px 5px 12px;
        border-radius: 5px;
    }}
    QMenu::item:selected {{
        background: {accent};
        color: white;
    }}
    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 3px 8px;
    }}

    /* ── Dialogs ── */
    QDialog {{
        background: {bg};
    }}
    QListWidget {{
        background: {bg2};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-radius: 5px;
    }}
    QListWidget::item:selected {{
        background: {accent};
        color: white;
    }}
    QListWidget::item:hover:!selected {{
        background: {btn_hover};
    }}
    QDialogButtonBox QPushButton {{
        background: {bg3};
        color: {text};
        border: none;
        border-radius: 6px;
        padding: 6px 16px;
        font-weight: 500;
    }}
    QDialogButtonBox QPushButton:hover {{
        background: {btn_hover};
    }}
    QDialogButtonBox QPushButton:default {{
        background: {accent};
        color: white;
    }}
    QDialogButtonBox QPushButton:default:hover {{
        background: {accent};
        opacity: 0.9;
    }}

    /* ── Combo box ── */
    QComboBox {{
        background: {input_bg};
        color: {text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 24px 4px 8px;
        font-size: 12px;
        min-width: 100px;
    }}
    QComboBox:focus {{
        border-color: {accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background: {bg2};
        color: {text};
        border: 1px solid {border};
        border-radius: 6px;
        selection-background-color: {accent};
        selection-color: white;
    }}

    /* ── Status bar ── */
    QStatusBar {{
        background: {status_bg};
        color: {text2};
        border-top: 1px solid {border};
        font-size: 11px;
        padding: 0 6px;
    }}

    /* ── Scrollbars ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {text2};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {border};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ── Line edit (generic) ── */
    QLineEdit {{
        background: {input_bg};
        color: {text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 8px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus {{
        border-color: {accent};
    }}
    """


# ─────────────────────────────────────────────────────────────────────────────
#  Ad blocker
# ─────────────────────────────────────────────────────────────────────────────

class AdBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, blocked_domains: set, allowed_domains: set, path_patterns: set):
        super().__init__()
        self._blocked  = blocked_domains
        self._allowed  = allowed_domains
        self._paths    = path_patterns
        self.enabled   = True

    def interceptRequest(self, info):
        if not self.enabled:
            return
        url  = info.requestUrl()
        host = url.host()
        path = url.path()

        # Never block allowlisted CDNs / media domains
        if any(host == d or host.endswith("." + d) for d in self._allowed):
            return

        # Block known ad domains
        if any(host == d or host.endswith("." + d) for d in self._blocked):
            info.block(True)
            return

        # Block by path pattern (works across domains)
        if any(pat in path for pat in self._paths):
            info.block(True)


# ─────────────────────────────────────────────────────────────────────────────
#  Custom WebEnginePage — handles permissions, new windows, downloads
# ─────────────────────────────────────────────────────────────────────────────

class BrowserPage(QWebEnginePage):
    # Emitted when a link/script wants to open a new tab.
    # The slot must be connected synchronously and set self._pending_page
    # before createWindow returns, so we use a direct connection.
    open_in_new_tab = pyqtSignal()
    fullscreen_requested = pyqtSignal(bool)

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._pending_page: Optional["BrowserPage"] = None
        self._user_gesture_active = False
        self._gesture_timer = QTimer()
        self._gesture_timer.setSingleShot(True)
        self._gesture_timer.setInterval(2000)  # gesture window: 2 seconds
        self._gesture_timer.timeout.connect(self._clear_gesture)
        self.featurePermissionRequested.connect(self._handle_permission)
        self.fullScreenRequested.connect(self._handle_fullscreen)

    def _clear_gesture(self):
        self._user_gesture_active = False

    def mark_user_gesture(self):
        """Call this on mouse clicks and key presses over the web view."""
        self._user_gesture_active = True
        self._gesture_timer.start()  # resets if already running

    def _handle_permission(self, url, feature):
        self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)

    def _handle_fullscreen(self, request):
        # Only honour requests that came from a real user gesture (click/key).
        # YouTube fires automatic fullscreen requests ~5s after load for ambient
        # mode setup — rejecting non-gesture requests prevents the window stretch.
        if request.toggleOn() and not self._user_gesture_active:
            request.reject()
            return
        request.accept()
        self.fullscreen_requested.emit(request.toggleOn())

    def createWindow(self, window_type):
        # Signal MainWindow to create a new tab. The slot runs synchronously
        # (direct connection) and stores the new tab's page in _pending_page.
        self._pending_page = None
        self.open_in_new_tab.emit()
        if self._pending_page is not None:
            return self._pending_page
        # Fallback: create a detached page (shouldn't normally happen)
        return BrowserPage(self.profile(), self)

    def javaScriptConsoleMessage(self, level, message, line, source):
        pass  # suppress noise

    def certificateError(self, error):
        reply = QMessageBox.warning(
            self.view(), "SSL Certificate Error",
            f"The certificate for <b>{error.url().host()}</b> is invalid.<br><br>"
            f"{error.errorDescription()}<br><br>Proceed anyway?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes


# ─────────────────────────────────────────────────────────────────────────────
#  Find bar widget
# ─────────────────────────────────────────────────────────────────────────────

class FindBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FindBar")
        self._browser: Optional[QWebEngineView] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._input = QLineEdit()
        self._input.setObjectName("FindInput")
        self._input.setPlaceholderText("Find in page…")
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self._search)
        self._input.returnPressed.connect(self._find_next)
        layout.addWidget(self._input)

        self._label = QLabel()
        self._label.setObjectName("FindLabel")
        layout.addWidget(self._label)

        prev_btn = QPushButton("↑")
        prev_btn.setFixedWidth(28)
        prev_btn.clicked.connect(self._find_prev)
        layout.addWidget(prev_btn)

        next_btn = QPushButton("↓")
        next_btn.setFixedWidth(28)
        next_btn.clicked.connect(self._find_next)
        layout.addWidget(next_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(28)
        close_btn.clicked.connect(self.hide_bar)
        layout.addWidget(close_btn)

        self.hide()

    def attach(self, browser: QWebEngineView):
        self._browser = browser

    def show_bar(self):
        self.show()
        self._input.setFocus()
        self._input.selectAll()

    def hide_bar(self):
        if self._browser:
            self._browser.findText("")
        self.hide()
        if self._browser:
            self._browser.setFocus()

    def _search(self, text: str):
        if self._browser:
            self._browser.findText(text)
            self._label.setText("" if not text else "searching…")

    def _find_next(self):
        if self._browser:
            self._browser.findText(self._input.text())

    def _find_prev(self):
        if self._browser:
            self._browser.findText(
                self._input.text(),
                QWebEnginePage.FindBackward
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_bar()
        super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  Single browser tab
# ─────────────────────────────────────────────────────────────────────────────

class BrowserTab(QWidget):
    title_changed   = pyqtSignal(str)
    icon_changed    = pyqtSignal(QIcon)
    url_changed     = pyqtSignal(QUrl)
    loading_changed = pyqtSignal(bool)
    status_message  = pyqtSignal(str)
    fullscreen_requested = pyqtSignal(bool)  # True = enter, False = exit

    def __init__(self, profile: QWebEngineProfile, url: str = ""):
        super().__init__()
        self._zoom = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Progress bar (2px strip at top)
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(2)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.hide()
        layout.addWidget(self._progress)

        # Web view
        self.browser = QWebEngineView()
        self.page = BrowserPage(profile, self)
        self.browser.setPage(self.page)
        # Track user gestures so fullscreen requests can be validated
        self.browser.installEventFilter(self)
        layout.addWidget(self.browser)

        # Find bar at bottom
        self.find_bar = FindBar(self)
        self.find_bar.attach(self.browser)
        layout.addWidget(self.find_bar)

        # Signals
        self.browser.loadStarted.connect(self._on_load_start)
        self.browser.loadProgress.connect(self._on_load_progress)
        self.browser.loadFinished.connect(self._on_load_finish)
        self.browser.titleChanged.connect(self.title_changed)
        self.browser.iconChanged.connect(self.icon_changed)
        self.browser.urlChanged.connect(self.url_changed)
        self.page.fullscreen_requested.connect(self.fullscreen_requested)
        self.browser.page().linkHovered.connect(
            lambda url: self.status_message.emit(url)
        )

        # Settings for compatibility
        s = self.browser.settings()
        for attr in [
            QWebEngineSettings.JavascriptEnabled,
            QWebEngineSettings.PluginsEnabled,
            QWebEngineSettings.FullScreenSupportEnabled,
            QWebEngineSettings.LocalStorageEnabled,
            QWebEngineSettings.JavascriptCanOpenWindows,
            QWebEngineSettings.WebGLEnabled,
            QWebEngineSettings.ScrollAnimatorEnabled,
            QWebEngineSettings.AllowWindowActivationFromJavaScript,
            QWebEngineSettings.PlaybackRequiresUserGesture,
        ]:
            s.setAttribute(attr, True)
        # Allow autoplay (YouTube etc.)
        s.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)

        if url:
            self.browser.setUrl(QUrl(url))

    def eventFilter(self, obj, event):
        if obj is self.browser and event.type() in (
            event.MouseButtonPress,
            event.MouseButtonDblClick,
            event.KeyPress,
        ):
            self.page.mark_user_gesture()
        return super().eventFilter(obj, event)

    # ── Load events ──────────────────────────────────────────────────────────

    def _on_load_start(self):
        self._progress.setValue(0)
        self._progress.show()
        self.loading_changed.emit(True)

    def _on_load_progress(self, pct: int):
        self._progress.setValue(pct)

    def _on_load_finish(self, ok: bool):
        self._progress.hide()
        self.loading_changed.emit(False)
        if not ok:
            url = self.browser.url().toString()
            if not url.startswith("data:"):
                self._show_error_page()

    def _show_error_page(self):
        dark = is_dark_mode()
        bg   = "#1c1c1e" if dark else "#f2f2f7"
        txt  = "#f2f2f7" if dark else "#1c1c1e"
        sub  = "#aeaeb2" if dark else "#6e6e73"
        btn  = "#0a84ff" if dark else "#007aff"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ background:{bg}; color:{txt}; font-family:-apple-system,sans-serif;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; margin:0; }}
  .box {{ text-align:center; max-width:400px; padding:40px; }}
  h1 {{ font-size:40px; margin:0 0 8px; }}
  p  {{ color:{sub}; font-size:15px; margin:0 0 24px; }}
  a  {{ display:inline-block; background:{btn}; color:white; text-decoration:none;
        border-radius:8px; padding:10px 22px; font-size:14px; font-weight:600; }}
</style></head>
<body><div class="box">
  <h1>⚠️</h1>
  <h2>Page couldn't load</h2>
  <p>Check your connection or try again.</p>
  <a href="javascript:history.back()">Go Back</a>
</div></body></html>"""
        self.browser.setHtml(html)

    # ── Zoom ─────────────────────────────────────────────────────────────────

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, factor: float):
        self._zoom = max(0.25, min(5.0, factor))
        self.browser.setZoomFactor(self._zoom)


# ─────────────────────────────────────────────────────────────────────────────
#  Custom tab bar with close buttons
# ─────────────────────────────────────────────────────────────────────────────

class TabWidget(QTabWidget):
    new_tab_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)


# ─────────────────────────────────────────────────────────────────────────────
#  Download manager dialog
# ─────────────────────────────────────────────────────────────────────────────

class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setMinimumSize(500, 300)
        self.resize(600, 400)
        self._downloads: List[QWebEngineDownloadItem] = []

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        layout.addWidget(self._list)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.hide)
        layout.addWidget(btns)

    def add_download(self, item: QWebEngineDownloadItem):
        self._downloads.append(item)
        name = Path(item.path()).name
        lw_item = QListWidgetItem(f"⬇  {name}")
        self._list.addItem(lw_item)
        idx = self._list.count() - 1

        def progress(received, total):
            if total > 0:
                pct = int(received / total * 100)
                lw_item.setText(f"⬇  {name}  {pct}%")
            else:
                lw_item.setText(f"⬇  {name}  …")

        def finished():
            lw_item.setText(f"✓  {name}")

        item.downloadProgress.connect(progress)
        item.finished.connect(finished)
        item.accept()
        self.show()


# ─────────────────────────────────────────────────────────────────────────────
#  History / Bookmarks dialog (shared)
# ─────────────────────────────────────────────────────────────────────────────

class ListDialog(QDialog):
    url_selected = pyqtSignal(str)

    def __init__(self, title: str, items: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(480, 380)
        self.resize(560, 460)

        layout = QVBoxLayout(self)

        # Search field
        search = QLineEdit()
        search.setPlaceholderText("Filter…")
        search.setClearButtonEnabled(True)
        layout.addWidget(search)

        self._list = QListWidget()
        self._all_items = items
        layout.addWidget(self._list)

        self._populate(items)
        search.textChanged.connect(self._filter)

        self._list.itemDoubleClicked.connect(self._open)

        btns = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Open).clicked.connect(self._open_selected)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, items: List[Dict]):
        self._list.clear()
        for entry in reversed(items):
            title = entry.get("title") or entry.get("url", "")
            url   = entry.get("url", "")
            text  = f"{title}\n{url}" if title != url else url
            lw = QListWidgetItem(text)
            lw.setData(Qt.UserRole, url)
            self._list.addItem(lw)

    def _filter(self, text: str):
        filtered = [
            e for e in self._all_items
            if text.lower() in (e.get("title","") + e.get("url","")).lower()
        ]
        self._populate(filtered)

    def _open(self, item: QListWidgetItem):
        self.url_selected.emit(item.data(Qt.UserRole))
        self.accept()

    def _open_selected(self):
        items = self._list.selectedItems()
        if items:
            self._open(items[0])


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings   = QSettings(str(SETTINGS_FILE), QSettings.IniFormat)
        self._bookmarks  = self._load_json(BOOKMARKS_FILE)
        self._history    = self._load_json(HISTORY_FILE)
        self._is_loading = False
        self._fs_overlay = None

        self.setWindowTitle("PyBrow")
        self.resize(1280, 820)

        # ── Profile ──────────────────────────────────────────────────────────
        self._profile = QWebEngineProfile("pybrow", self)
        self._profile.setHttpUserAgent(USER_AGENT)
        self._profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.AllowPersistentCookies
        )
        self._profile.downloadRequested.connect(self._handle_download)

        # Ad blocker
        self._blocker = AdBlocker(ADBLOCK_DOMAINS, ADBLOCK_ALLOWLIST, ADBLOCK_PATH_PATTERNS)
        self._profile.setUrlRequestInterceptor(self._blocker)

        # ── Download dialog ───────────────────────────────────────────────────
        self._dl_dialog = DownloadDialog(self)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = TabWidget()
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

        # ── UI ────────────────────────────────────────────────────────────────
        self._build_toolbar()
        self._build_menu()
        self._build_status_bar()
        self._build_shortcuts()

        # ── Apply theme ───────────────────────────────────────────────────────
        self._apply_theme()

        # ── Restore geometry ──────────────────────────────────────────────────
        # Validate saved geometry before restoring — a previous session may have
        # saved a maximized/multi-monitor rect that would stretch across screens.
        geo = self._settings.value("geometry")
        restored = False
        if geo:
            self.restoreGeometry(QByteArray.fromHex(geo.encode()))
            # Check the restored geometry fits entirely within a single screen
            win_rect = self.frameGeometry()
            for screen in QApplication.screens():
                if screen.availableGeometry().contains(win_rect):
                    restored = True
                    break
            if not restored:
                # Geometry spans screens or is otherwise invalid — reset it
                self.settings_reset_geometry()
        if not restored:
            self.settings_reset_geometry()

        # ── Open first tab ────────────────────────────────────────────────────
        homepage = self._settings.value("homepage", "https://duckduckgo.com")
        self._new_tab(homepage)

    # ─────────────────────────────────────────────────────────────────────────
    #  Theme
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(is_dark_mode()))

    # ─────────────────────────────────────────────────────────────────────────
    #  Toolbar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Navigation")
        tb.setMovable(False)
        tb.setObjectName("NavBar")
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)
        self._toolbar = tb

        def nav_btn(symbol: str, tip: str) -> QPushButton:
            b = QPushButton(symbol)
            b.setToolTip(tip)
            b.setFixedSize(34, 34)
            b.setCursor(Qt.PointingHandCursor)
            return b

        self._btn_back    = nav_btn("←", "Back (Alt+Left)")
        self._btn_forward = nav_btn("→", "Forward (Alt+Right)")
        self._btn_reload  = nav_btn("↻", "Reload (F5)")
        self._btn_home    = nav_btn("⌂", "Home")

        self._btn_back.clicked.connect(self._go_back)
        self._btn_forward.clicked.connect(self._go_forward)
        self._btn_reload.clicked.connect(self._reload)
        self._btn_home.clicked.connect(self._go_home)

        for b in [self._btn_back, self._btn_forward, self._btn_reload, self._btn_home]:
            tb.addWidget(b)

        # Address bar
        self._addr = QLineEdit()
        self._addr.setObjectName("AddressBar")
        self._addr.setPlaceholderText("Search or enter address…")
        self._addr.setClearButtonEnabled(True)
        self._addr.returnPressed.connect(self._navigate)
        self._addr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tb.addWidget(self._addr)

        # Bookmark star
        self._btn_star = QPushButton("☆")
        self._btn_star.setToolTip("Bookmark this page (Ctrl+D)")
        self._btn_star.setFixedSize(34, 34)
        self._btn_star.setCursor(Qt.PointingHandCursor)
        self._btn_star.clicked.connect(self._toggle_bookmark)
        tb.addWidget(self._btn_star)

        # Downloads
        self._btn_dl = QPushButton("⬇")
        self._btn_dl.setToolTip("Downloads")
        self._btn_dl.setFixedSize(34, 34)
        self._btn_dl.setCursor(Qt.PointingHandCursor)
        self._btn_dl.clicked.connect(self._dl_dialog.show)
        tb.addWidget(self._btn_dl)

        # New tab button
        self._btn_new_tab = QPushButton("+")
        self._btn_new_tab.setToolTip("New Tab (Ctrl+T)")
        self._btn_new_tab.setFixedSize(34, 34)
        self._btn_new_tab.setCursor(Qt.PointingHandCursor)
        self._btn_new_tab.clicked.connect(lambda: self._new_tab())
        tb.addWidget(self._btn_new_tab)

    # ─────────────────────────────────────────────────────────────────────────
    #  Menu bar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("&File")
        self._add_action(fm, "New Tab",    "Ctrl+T", lambda: self._new_tab())
        self._add_action(fm, "New Window", "Ctrl+N", self._new_window)
        fm.addSeparator()
        self._add_action(fm, "Open File…", "Ctrl+O", self._open_file)
        self._add_action(fm, "Save Page As…", "Ctrl+S", self._save_page)
        fm.addSeparator()
        self._add_action(fm, "Print…", "Ctrl+P", self._print_page)
        fm.addSeparator()
        self._add_action(fm, "Exit", "Ctrl+Q", self.close)

        # Edit
        em = mb.addMenu("&Edit")
        self._add_action(em, "Find in Page", "Ctrl+F", self._find_in_page)
        em.addSeparator()

        # Search engine submenu
        se_menu = em.addMenu("Search Engine")
        self._se_group = []
        for name in SEARCH_ENGINES:
            a = QAction(name, self, checkable=True)
            cur = self._settings.value("search_engine", "DuckDuckGo")
            a.setChecked(name == cur)
            a.triggered.connect(lambda checked, n=name: self._set_search_engine(n))
            se_menu.addAction(a)
            self._se_group.append(a)

        # View
        vm = mb.addMenu("&View")
        self._add_action(vm, "Zoom In",    "Ctrl++", self._zoom_in)
        self._add_action(vm, "Zoom Out",   "Ctrl+-", self._zoom_out)
        self._add_action(vm, "Reset Zoom", "Ctrl+0", self._zoom_reset)
        vm.addSeparator()
        self._add_action(vm, "Reload", "F5", self._reload)
        self._add_action(vm, "Hard Reload", "Ctrl+Shift+R", self._hard_reload)
        vm.addSeparator()
        self._adblock_action = QAction("Ad Blocker", self, checkable=True, checked=True)
        self._adblock_action.triggered.connect(self._toggle_adblock)
        vm.addAction(self._adblock_action)
        self._toggle_nav_action = QAction("Show Navigation Bar", self, checkable=True, checked=True)
        self._toggle_nav_action.triggered.connect(self._toggle_navbar)
        vm.addAction(self._toggle_nav_action)
        self._add_action(vm, "Toggle Full Screen", "F11", self._toggle_fullscreen)

        # Bookmarks
        bm = mb.addMenu("&Bookmarks")
        self._add_action(bm, "Bookmark This Page", "Ctrl+D", self._toggle_bookmark)
        self._add_action(bm, "Show Bookmarks…",    "Ctrl+Shift+B", self._show_bookmarks)

        # History
        hm = mb.addMenu("&History")
        self._add_action(hm, "Show History…", "Ctrl+H", self._show_history)
        self._add_action(hm, "Clear History", "", self._clear_history)

        # Help
        hlp = mb.addMenu("&Help")
        self._add_action(hlp, "About PyBrow", "", self._about)

    def _add_action(self, menu, label: str, shortcut: str, slot) -> QAction:
        a = QAction(label, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    # ─────────────────────────────────────────────────────────────────────────
    #  Status bar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel()
        sb.addWidget(self._status_label)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setAlignment(Qt.AlignRight)
        sb.addPermanentWidget(self._zoom_label)

    # ─────────────────────────────────────────────────────────────────────────
    #  Shortcuts
    # ─────────────────────────────────────────────────────────────────────────

    def _build_shortcuts(self):
        shortcuts = [
            ("Ctrl+W",           self._close_current_tab),
            ("Ctrl+Tab",         self._next_tab),
            ("Ctrl+Shift+Tab",   self._prev_tab),
            ("Ctrl+L",           self._focus_address),
            ("Alt+Left",         self._go_back),
            ("Alt+Right",        self._go_forward),
            ("F5",               self._reload),
            ("Escape",           self._stop_or_escape),
        ]
        for key, slot in shortcuts:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab management
    # ─────────────────────────────────────────────────────────────────────────

    def _new_tab(self, url: Optional[str] = None, background: bool = False) -> "BrowserTab":
        if url is None:
            url = self._settings.value("homepage", "https://duckduckgo.com")

        tab = BrowserTab(self._profile, url)
        idx = self._tabs.addTab(tab, "New Tab")
        self._tabs.setTabIcon(idx, QIcon())

        # Only switch to the new tab if not opening in background
        if not background:
            self._tabs.setCurrentIndex(idx)

        tab.title_changed.connect(lambda t, tw=tab: self._update_tab_title(tw, t))
        tab.icon_changed.connect(lambda ic, tw=tab: self._update_tab_icon(tw, ic))
        tab.url_changed.connect(lambda u, tw=tab: self._on_url_changed(u, tw))
        tab.loading_changed.connect(lambda loading, tw=tab: self._on_loading_changed(loading, tw))
        tab.fullscreen_requested.connect(self._on_fullscreen_requested)
        tab.status_message.connect(self._status_label.setText)

        # Wire middle-click / target=_blank: when this tab's page calls createWindow,
        # we create a new background tab and hand its page back synchronously.
        def _provide_page_for_new_tab(source_tab=tab):
            new_tab = self._new_tab(url="", background=True)
            # Give the requesting page the new tab's page to load into
            source_tab.page._pending_page = new_tab.page

        tab.page.open_in_new_tab.connect(
            _provide_page_for_new_tab, Qt.DirectConnection
        )

        self._update_nav_buttons()
        return tab

    def _close_tab(self, index: int):
        if self._tabs.count() <= 1:
            return
        widget = self._tabs.widget(index)
        self._tabs.removeTab(index)
        if widget and isinstance(widget, BrowserTab):
            widget.browser.stop()
            widget.page.deleteLater()
            widget.browser.setPage(QWebEnginePage())  # detach custom page first
            widget.deleteLater()

    def _close_current_tab(self):
        self._close_tab(self._tabs.currentIndex())

    def _next_tab(self):
        self._tabs.setCurrentIndex(
            (self._tabs.currentIndex() + 1) % self._tabs.count()
        )

    def _prev_tab(self):
        self._tabs.setCurrentIndex(
            (self._tabs.currentIndex() - 1) % self._tabs.count()
        )

    def _current_tab(self) -> Optional[BrowserTab]:
        w = self._tabs.currentWidget()
        return w if isinstance(w, BrowserTab) else None

    def _update_tab_title(self, tab: BrowserTab, title: str):
        idx = self._tabs.indexOf(tab)
        if idx >= 0:
            short = (title[:22] + "…") if len(title) > 23 else title
            self._tabs.setTabText(idx, short or "New Tab")
            if tab is self._current_tab():
                self.setWindowTitle(f"{title} — PyBrow")

    def _update_tab_icon(self, tab: BrowserTab, icon: QIcon):
        idx = self._tabs.indexOf(tab)
        if idx >= 0 and not icon.isNull():
            self._tabs.setTabIcon(idx, icon)

    # ─────────────────────────────────────────────────────────────────────────
    #  Navigation
    # ─────────────────────────────────────────────────────────────────────────

    def _navigate(self):
        text = self._addr.text().strip()
        if not text:
            return

        # Detect URL vs search query
        if (
            text.startswith(("http://", "https://", "file://", "ftp://"))
            or ("." in text and " " not in text and "/" in text)
            or (text.endswith((".com", ".org", ".net", ".io", ".dev", ".app")) and " " not in text)
        ):
            if not text.startswith(("http", "file", "ftp")):
                text = "https://" + text
            url = text
        else:
            engine = self._settings.value("search_engine", "DuckDuckGo")
            template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["DuckDuckGo"])
            url = template.format(quote_plus(text))

        tab = self._current_tab()
        if tab:
            tab.browser.setUrl(QUrl(url))

    def _go_back(self):
        tab = self._current_tab()
        if tab and tab.browser.history().canGoBack():
            tab.browser.back()

    def _go_forward(self):
        tab = self._current_tab()
        if tab and tab.browser.history().canGoForward():
            tab.browser.forward()

    def _reload(self):
        tab = self._current_tab()
        if tab:
            tab.browser.reload()

    def _hard_reload(self):
        tab = self._current_tab()
        if tab:
            tab.browser.page().triggerAction(QWebEnginePage.ReloadAndBypassCache)

    def _go_home(self):
        homepage = self._settings.value("homepage", "https://duckduckgo.com")
        tab = self._current_tab()
        if tab:
            tab.browser.setUrl(QUrl(homepage))

    def _stop_or_escape(self):
        tab = self._current_tab()
        if tab and self._is_loading:
            tab.browser.stop()
        elif tab:
            tab.find_bar.hide_bar()

    def _focus_address(self):
        self._addr.setFocus()
        self._addr.selectAll()

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab / URL change handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        tab = self._current_tab()
        if tab:
            url = tab.browser.url().toString()
            self._addr.setText("" if url == "about:blank" else url)
            self._addr.setCursorPosition(0)
            self._update_nav_buttons()
            self._update_bookmark_star()
            self._zoom_label.setText(f"{int(tab.zoom * 100)}%")
            title = tab.browser.page().title() or "PyBrow"
            self.setWindowTitle(f"{title} — PyBrow")

    def _on_url_changed(self, url: QUrl, source_tab: "BrowserTab"):
        # Only update UI if the signal came from the currently-visible tab
        current = self._current_tab()
        if source_tab is not current:
            return
        url_str = url.toString()
        if url_str not in ("about:blank", ""):
            self._addr.setText(url_str)
            self._addr.setCursorPosition(0)
        self._update_bookmark_star()
        self._update_nav_buttons()
        # Save history
        if url_str.startswith(("http://", "https://")):
            self._history.append({
                "url":       url_str,
                "title":     source_tab.browser.page().title(),
                "timestamp": datetime.datetime.now().isoformat()
            })
            if len(self._history) > 2000:
                self._history = self._history[-2000:]
            self._save_json(HISTORY_FILE, self._history)

    def _on_loading_changed(self, loading: bool, source_tab: "BrowserTab"):
        if source_tab is not self._current_tab():
            return
        self._is_loading = loading
        self._btn_reload.setText("✕" if loading else "↻")
        self._btn_reload.setToolTip("Stop" if loading else "Reload (F5)")
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        tab = self._current_tab()
        if tab:
            self._btn_back.setEnabled(tab.browser.history().canGoBack())
            self._btn_forward.setEnabled(tab.browser.history().canGoForward())

    # ─────────────────────────────────────────────────────────────────────────
    #  Bookmarks
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_bookmark(self):
        tab = self._current_tab()
        if not tab:
            return
        url = tab.browser.url().toString()
        if not url.startswith("http"):
            return
        title = tab.browser.page().title()

        existing = next((i for i, b in enumerate(self._bookmarks) if b["url"] == url), -1)
        if existing >= 0:
            self._bookmarks.pop(existing)
            self._btn_star.setText("☆")
        else:
            self._bookmarks.append({
                "url":       url,
                "title":     title,
                "timestamp": datetime.datetime.now().isoformat()
            })
            self._btn_star.setText("★")
        self._save_json(BOOKMARKS_FILE, self._bookmarks)

    def _update_bookmark_star(self):
        tab = self._current_tab()
        if tab:
            url = tab.browser.url().toString()
            is_bm = any(b["url"] == url for b in self._bookmarks)
            self._btn_star.setText("★" if is_bm else "☆")

    def _show_bookmarks(self):
        dlg = ListDialog("Bookmarks", self._bookmarks, self)
        dlg.url_selected.connect(self._open_url_in_current_or_new)
        dlg.exec_()

    # ─────────────────────────────────────────────────────────────────────────
    #  History
    # ─────────────────────────────────────────────────────────────────────────

    def _show_history(self):
        dlg = ListDialog("History", self._history, self)
        dlg.url_selected.connect(self._open_url_in_current_or_new)
        dlg.exec_()

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Clear all browsing history?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._history.clear()
            self._save_json(HISTORY_FILE, self._history)

    def _open_url_in_current_or_new(self, url: str):
        tab = self._current_tab()
        if tab:
            tab.browser.setUrl(QUrl(url))
        else:
            self._new_tab(url)

    # ─────────────────────────────────────────────────────────────────────────
    #  View actions
    # ─────────────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        tab = self._current_tab()
        if tab:
            tab.set_zoom(tab.zoom + 0.1)
            self._zoom_label.setText(f"{int(tab.zoom * 100)}%")

    def _zoom_out(self):
        tab = self._current_tab()
        if tab:
            tab.set_zoom(tab.zoom - 0.1)
            self._zoom_label.setText(f"{int(tab.zoom * 100)}%")

    def _zoom_reset(self):
        tab = self._current_tab()
        if tab:
            tab.set_zoom(1.0)
            self._zoom_label.setText("100%")

    def _toggle_adblock(self, enabled: bool):
        self._blocker.enabled = enabled

    def _toggle_navbar(self, visible: bool):
        self._toolbar.setVisible(visible)

    def _on_fullscreen_requested(self, enter: bool):
        """Handle web fullscreen requests (YouTube, Vimeo, etc.).
        We reparent the web view into a frameless overlay widget locked to
        whichever screen the main window is currently on. The main window is
        never resized, so multi-monitor setups stay intact.
        """
        tab = self._current_tab()
        if not tab:
            return

        if enter:
            # Find which screen the window is on
            screen = self.screen() if hasattr(self, 'screen') else \
                     QApplication.screenAt(self.geometry().center())
            if screen is None:
                screen = QApplication.primaryScreen()
            screen_geom = screen.geometry()

            # Create a frameless, always-on-top overlay on that screen only
            self._fs_overlay = QWidget()
            self._fs_overlay.setWindowFlags(
                Qt.Window |
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint
            )
            self._fs_overlay.setAttribute(Qt.WA_DeleteOnClose, False)
            overlay_layout = QVBoxLayout(self._fs_overlay)
            overlay_layout.setContentsMargins(0, 0, 0, 0)
            overlay_layout.setSpacing(0)

            # Reparent the browser view into the overlay
            self._fs_original_parent = tab.layout().takeAt(
                tab.layout().indexOf(tab.browser)
            )
            tab.layout().removeWidget(tab.browser)
            tab.browser.setParent(self._fs_overlay)
            overlay_layout.addWidget(tab.browser)

            # Size to exactly one screen
            self._fs_overlay.setGeometry(screen_geom)
            self._fs_overlay.showFullScreen()
            self._fs_overlay.activateWindow()

            # Escape key exits fullscreen
            self._fs_esc = QShortcut(QKeySequence(Qt.Key_Escape), self._fs_overlay)
            self._fs_esc.activated.connect(lambda: self._on_fullscreen_requested(False))

        else:
            if not hasattr(self, "_fs_overlay") or self._fs_overlay is None:
                return

            # Reparent the browser view back into its tab
            if tab:
                self._fs_overlay.layout().removeWidget(tab.browser)
                tab.browser.setParent(tab)
                # Re-insert at position 1 (after progress bar, before find bar)
                tab.layout().insertWidget(1, tab.browser)

            self._fs_overlay.hide()
            self._fs_overlay.deleteLater()
            self._fs_overlay = None

            if tab:
                tab.browser.setFocus()

    def _toggle_fullscreen(self):
        """F11 — toggle fullscreen for current tab."""
        if hasattr(self, "_fs_overlay") and self._fs_overlay is not None:
            self._on_fullscreen_requested(False)
        else:
            tab = self._current_tab()
            if tab:
                tab.page.triggerAction(QWebEnginePage.ToggleMediaFullscreen)

    def _find_in_page(self):
        tab = self._current_tab()
        if tab:
            tab.find_bar.show_bar()

    # ─────────────────────────────────────────────────────────────────────────
    #  File / Save / Print
    # ─────────────────────────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Web files (*.html *.htm *.mhtml *.mht);;All files (*)"
        )
        if path:
            tab = self._current_tab() or self._new_tab()
            tab.browser.setUrl(QUrl.fromLocalFile(path))

    def _save_page(self):
        tab = self._current_tab()
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Page", "", "HTML (*.html);;All files (*)"
        )
        if path:
            tab.browser.page().toHtml(lambda h: self._write_file(path, h))

    def _write_file(self, path: str, content: str):
        try:
            Path(path).write_text(content, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _print_page(self):
        tab = self._current_tab()
        if tab:
            tab.browser.page().printToPdf(str(Path.home() / "Desktop" / "page.pdf"))
            QMessageBox.information(self, "Print", "Page exported to Desktop/page.pdf")

    # ─────────────────────────────────────────────────────────────────────────
    #  Search engine
    # ─────────────────────────────────────────────────────────────────────────

    def _set_search_engine(self, name: str):
        self._settings.setValue("search_engine", name)
        for a in self._se_group:
            a.setChecked(a.text() == name)

    # ─────────────────────────────────────────────────────────────────────────
    #  Downloads
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_download(self, item: QWebEngineDownloadItem):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Download",
            str(DOWNLOADS_DIR / Path(item.path()).name)
        )
        if path:
            item.setPath(path)
            self._dl_dialog.add_download(item)
        else:
            item.cancel()

    # ─────────────────────────────────────────────────────────────────────────
    #  New window
    # ─────────────────────────────────────────────────────────────────────────

    def _new_window(self):
        w = MainWindow()
        w.show()

    # ─────────────────────────────────────────────────────────────────────────
    #  About
    # ─────────────────────────────────────────────────────────────────────────

    def _about(self):
        QMessageBox.about(
            self, "About PyBrow",
            "<h2>PyBrow</h2>"
            "<p>A modern, lightweight Python browser.<br>"
            "Built with PyQt5 + QtWebEngine.</p>"
            "<p>Follows system light/dark mode.<br>"
            "Ad blocking, tabs, downloads, find-in-page, bookmarks and history.</p>"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Persistence
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_json(path: Path) -> list:
        try:
            if path.exists():
                return json.loads(path.read_text())
        except Exception:
            pass
        return []

    @staticmethod
    def _save_json(path: Path, data):
        try:
            path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Save failed: {e}")

    def settings_reset_geometry(self):
        """Place the window at a sane default size on the primary screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(1280, int(screen.width()  * 0.8))
        h = min(820,  int(screen.height() * 0.8))
        x = screen.x() + (screen.width()  - w) // 2
        y = screen.y() + (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self._settings.remove("geometry")  # don't restore this bad state next time

    # ─────────────────────────────────────────────────────────────────────────
    #  Close
    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Only save geometry if the window fits cleanly on one screen
        win_rect = self.frameGeometry()
        on_single_screen = any(
            s.availableGeometry().contains(win_rect)
            for s in QApplication.screens()
        )
        if on_single_screen and not self.isMaximized() and not self.isFullScreen():
            self._settings.setValue(
                "geometry", bytes(self.saveGeometry().toHex()).decode()
            )
        self._save_json(BOOKMARKS_FILE, self._bookmarks)
        self._save_json(HISTORY_FILE,   self._history)

        # Stop all pages and delete them explicitly before the profile is released.
        # QtWebEngine warns if pages outlive their profile, so we do this carefully:
        # 1. Stop any in-progress loads
        # 2. Set a null page (releases the old BrowserPage)
        # 3. Schedule widget deletion
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, BrowserTab):
                try:
                    w.browser.stop()
                    w.page.deleteLater()
                    w.browser.setPage(QWebEnginePage())  # swap in a default page
                except Exception:
                    pass

        # Process pending deletions before the window fully closes
        QApplication.processEvents()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── Suppress Chromium GPU/GL noise on Windows ─────────────────────────────
    # These are harmless driver-compatibility warnings from the Chromium compositor.
    # Setting --disable-gpu-sandbox and using software rendering fallback prevents
    # the shared-image mailbox errors on many Windows GPU configurations.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-logging "
        "--log-level=3 "                    # only fatal errors from Chromium
        "--disable-gpu-sandbox "            # fixes SharedImageManager errors
        "--ignore-gpu-blocklist "           # use GPU even if blocklisted
        "--disable-features=UseSkiaRenderer"# avoid Skia path that triggers mailbox bugs
    )
    # Redirect Chromium's stderr noise (GL errors come from the GPU process)
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    # High-DPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("PyBrow")
    app.setOrganizationName("PyBrow")

    # Global web engine settings
    ws = QWebEngineSettings.defaultSettings()
    ws.setAttribute(QWebEngineSettings.JavascriptEnabled,  True)
    ws.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
    ws.setAttribute(QWebEngineSettings.PluginsEnabled,      True)
    ws.setAttribute(QWebEngineSettings.WebGLEnabled,        True)
    ws.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
    ws.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
    ws.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()