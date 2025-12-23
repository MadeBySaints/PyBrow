######################################################################
### A lightweight browser with limited features written in python. ###
###                       MadeBySaints 2025                        ###
######################################################################
import sys
import json
import logging
import datetime
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import quote_plus

from PyQt5.QtCore import QUrl, Qt, QPoint, QSettings, QByteArray
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QTabWidget, QWidget, QVBoxLayout,
    QAction, QMessageBox, QToolBar, QPushButton, QFileDialog, QMenu, QLabel,
    QProgressBar, QComboBox, QTabBar, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QVBoxLayout
)
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineProfile, 
    QWebEngineDownloadItem, QWebEngineSettings
)
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtGui import QIcon, QKeySequence, QImage

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration paths
CONFIG_DIR = Path.home() / ".pybrow"
CONFIG_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = CONFIG_DIR / "settings.ini"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

# Load adblock list (simplified example)
ADBLOCK_LIST = [
    "ads.", "doubleclick.net", "adservice.google.com", 
    "google-analytics.com", "googletagmanager.com",
    "facebook.com/tr/", "twitter.com/i/ads"
]

class AdBlockerInterceptor(QWebEngineUrlRequestInterceptor):
    """Enhanced ad blocker with more comprehensive blocking"""
    def __init__(self, blocklist: List[str]):
        super().__init__()
        self.blocklist = blocklist

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if any(blocked in url for blocked in self.blocklist):
            info.block(True)
            logger.debug(f"Blocked URL: {url}")

class CustomWebEnginePage(QWebEnginePage):
    """Enhanced WebEnginePage with better error handling and JS console management"""
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._error_page_html = """
        <html><body style="font-family: sans-serif; padding: 20px;">
            <h1>Page failed to load</h1>
            <p>Could not load the requested page.</p>
            <p>Error: {error}</p>
            <button onclick="window.history.back()">Go Back</button>
            <button onclick="window.location='https://duckduckgo.com'">Search</button>
        </body></html>
        """

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Filter out common benign JS messages"""
        ignored_substrings = [
            "Content Security Policy directive",
            "preloaded using link preload but not used",
            "prefetch content",
            "Mixed Content"
        ]
        if not any(sub in message for sub in ignored_substrings):
            logger.debug(f"JS console: {message} (line {lineNumber} in {sourceID})")

    def certificateError(self, certificateError):
        """Handle SSL certificate errors"""
        error_url = certificateError.url().toString()
        error_msg = certificateError.errorDescription()
        
        reply = QMessageBox.question(
            self.view(), "SSL Certificate Error",
            f"The site {error_url} has an invalid SSL certificate:\n{error_msg}\n\n"
            "Do you want to proceed anyway?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        return reply == QMessageBox.Yes

class BrowserTab(QWidget):
    """Represents a single browser tab with enhanced functionality"""
    def __init__(self, profile: QWebEngineProfile, url: str = "https://duckduckgo.com"):
        super().__init__()
        self.block_selectors: List[str] = []
        self.profile = profile
        self.zoom_factor: float = 1.0

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create browser view
        self.browser = QWebEngineView()
        self.page = CustomWebEnginePage(self.profile, self)
        self.browser.setPage(self.page)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { border: 0; } QProgressBar::chunk { background-color: #1a73e8; }")
        
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.browser)
        self.setLayout(self.layout)

        # Connect signals
        self.browser.loadStarted.connect(self.on_load_start)
        self.browser.loadProgress.connect(self.on_load_progress)
        self.browser.loadFinished.connect(self.on_load_finish)
        self.browser.urlChanged.connect(self.on_url_changed)
        self.browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self.show_context_menu)
        
        # Initial load
        self.browser.setUrl(QUrl(url))
        
        # Apply default settings
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

    def on_load_start(self):
        """Show loading state"""
        self.progress_bar.setValue(0)
        self.progress_bar.show()

    def on_load_progress(self, progress: int):
        """Update progress bar"""
        self.progress_bar.setValue(progress)

    def on_load_finish(self, ok: bool):
        """Handle page load completion"""
        self.progress_bar.hide()
        if not ok:
            error = self.browser.page().errorString()
            self.browser.setHtml(self.page._error_page_html.format(error=error))

    def on_url_changed(self, url: QUrl):
        """Handle URL changes"""
        self.inject_block_css()

    def show_context_menu(self, pos: QPoint):
        """Enhanced context menu with more options"""
        menu = self.browser.page().createStandardContextMenu()
        
        # Add custom actions
        menu.addSeparator()
        
        # Element blocking
        block_action = QAction("Block this element", self)
        block_action.triggered.connect(lambda: self.block_element(pos))
        menu.addAction(block_action)
        
        # Screenshot
        screenshot_action = QAction("Take screenshot", self)
        screenshot_action.triggered.connect(lambda: self.take_screenshot())
        menu.addAction(screenshot_action)
        
        # Zoom actions
        zoom_in_action = QAction("Zoom in", self)
        zoom_in_action.triggered.connect(lambda: self.set_zoom(self.zoom_factor + 0.1))
        menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom out", self)
        zoom_out_action.triggered.connect(lambda: self.set_zoom(self.zoom_factor - 0.1))
        menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("Reset zoom", self)
        reset_zoom_action.triggered.connect(lambda: self.set_zoom(1.0))
        menu.addAction(reset_zoom_action)
        
        menu.exec_(self.browser.mapToGlobal(pos))

    def block_element(self, pos: QPoint):
        """Block element at given position"""
        js = """
        function getSelector(element) {
            if (!element) return null;
            
            const path = [];
            while (element && element.nodeType === Node.ELEMENT_NODE) {
                let selector = element.nodeName.toLowerCase();
                
                if (element.id) {
                    selector += '#' + element.id;
                    path.unshift(selector);
                    break;
                } else {
                    let sibling = element;
                    let nth = 1;
                    while (sibling !== element.parentNode.firstChild) {
                        sibling = sibling.previousElementSibling;
                        nth++;
                    }
                    selector += ':nth-child(' + nth + ')';
                }
                
                path.unshift(selector);
                element = element.parentNode;
            }
            
            return path.join(' > ');
        }
        
        var element = document.elementFromPoint(%d, %d);
        getSelector(element);
        """ % (pos.x(), pos.y())

        def callback(selector: str):
            if selector and selector not in self.block_selectors:
                self.block_selectors.append(selector)
                self.inject_block_css()
                QMessageBox.information(self, "Blocked", f"Blocked elements matching: {selector}")
            else:
                QMessageBox.warning(self, "Already Blocked", "This element selector is already blocked or invalid.")

        self.browser.page().runJavaScript(js, callback)

    def inject_block_css(self):
        """Inject CSS to block selected elements"""
        if not self.block_selectors:
            return
            
        css = ', '.join(self.block_selectors) + " { display: none !important; }"
        js = """
        var style = document.getElementById('custom-block-style');
        if (!style) {
            style = document.createElement('style');
            style.id = 'custom-block-style';
            document.head.appendChild(style);
        }
        style.textContent = `%s`;
        """ % css
        
        self.browser.page().runJavaScript(js)

    def take_screenshot(self):
        """Take screenshot of current page"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", "", "PNG Images (*.png);;JPEG Images (*.jpg)"
        )
        
        if file_path:
            image = self.browser.grab()
            image.save(file_path)
            QMessageBox.information(self, "Success", f"Screenshot saved to {file_path}")

    def set_zoom(self, factor: float):
        """Set zoom factor for the page"""
        self.zoom_factor = max(0.25, min(5.0, factor))  # Clamp between 0.25 and 5.0
        self.browser.setZoomFactor(self.zoom_factor)

class MainWindow(QMainWindow):
    """Main browser window with tabs and navigation"""
    def __init__(self):
        super().__init__()
        self.settings = QSettings(str(SETTINGS_FILE), QSettings.IniFormat)
        self.bookmarks = self.load_bookmarks()
        self.history = self.load_history()
        
        self.setWindowTitle("PyBrow")
        self.setWindowIcon(QIcon.fromTheme("web-browser"))
        
        # Web profile setup
        self.profile = QWebEngineProfile.defaultProfile()
        self.interceptor = AdBlockerInterceptor(ADBLOCK_LIST)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_ui)
        self.setCentralWidget(self.tabs)
        
        # Setup UI
        self.setup_toolbar()
        self.setup_menu()
        
        # Load initial state
        self.load_settings()
        
        # Add initial tab
        self.add_new_tab()
        self.add_plus_tab()

    def setup_toolbar(self):
        """Create navigation toolbar"""
        self.navtb = QToolBar("Navigation")
        self.navtb.setMovable(False)
        self.navtb.setObjectName("NavigationToolBar")
        self.addToolBar(self.navtb)
        
        # Back button
        self.back_btn = QPushButton()
        self.back_btn.setIcon(QIcon.fromTheme("go-previous"))
        self.back_btn.setToolTip("Back")
        self.back_btn.clicked.connect(self.go_back)
        self.navtb.addWidget(self.back_btn)
        
        # Forward button
        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(QIcon.fromTheme("go-next"))
        self.forward_btn.setToolTip("Forward")
        self.forward_btn.clicked.connect(self.go_forward)
        self.navtb.addWidget(self.forward_btn)
        
        # Refresh button
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_page)
        self.navtb.addWidget(self.refresh_btn)
        
        # Home button
        self.home_btn = QPushButton()
        self.home_btn.setIcon(QIcon.fromTheme("go-home"))
        self.home_btn.setToolTip("Home")
        self.home_btn.clicked.connect(self.go_home)
        self.navtb.addWidget(self.home_btn)
        
        # Address bar
        self.address_bar = QLineEdit()
        self.address_bar.setClearButtonEnabled(True)
        self.address_bar.setPlaceholderText("Search or enter website address")
        self.address_bar.returnPressed.connect(self.load_url)
        self.navtb.addWidget(self.address_bar)
        
        # Search engine selector
        self.search_engine_combo = QComboBox()
        self.search_engine_combo.addItems(["DuckDuckGo", "Google", "Bing", "Yahoo"])
        self.search_engine_combo.setCurrentText(self.settings.value("search_engine", "DuckDuckGo"))
        self.search_engine_combo.currentTextChanged.connect(self.change_search_engine)
        self.navtb.addWidget(QLabel("Search:"))
        self.navtb.addWidget(self.search_engine_combo)
        
        # Style buttons
        for btn in [self.back_btn, self.forward_btn, self.refresh_btn, self.home_btn]:
            btn.setStyleSheet("QPushButton { border: none; padding: 5px; }")
            btn.setCursor(Qt.PointingHandCursor)

    def setup_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_tab_action = QAction("New Tab", self)
        new_tab_action.setShortcut(QKeySequence.AddTab)
        new_tab_action.triggered.connect(lambda: self.add_new_tab())
        file_menu.addAction(new_tab_action)
        
        new_window_action = QAction("New Window", self)
        new_window_action.setShortcut(QKeySequence.New)
        new_window_action.triggered.connect(self.new_window)
        file_menu.addAction(new_window_action)
        
        file_menu.addSeparator()
        
        open_file_action = QAction("Open File...", self)
        open_file_action.setShortcut(QKeySequence.Open)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)
        
        save_page_action = QAction("Save Page As...", self)
        save_page_action.setShortcut(QKeySequence.Save)
        save_page_action.triggered.connect(self.save_page)
        file_menu.addAction(save_page_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        find_action = QAction("Find in Page", self)
        find_action.setShortcut(QKeySequence.Find)
        find_action.triggered.connect(self.find_in_page)
        edit_menu.addAction(find_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        toggle_navbar_action = QAction("Toggle Navigation Bar", self)
        toggle_navbar_action.setCheckable(True)
        toggle_navbar_action.setChecked(True)
        toggle_navbar_action.triggered.connect(self.toggle_navigation_bar)
        view_menu.addAction(toggle_navbar_action)
        
        # Bookmarks menu
        bookmarks_menu = menubar.addMenu("&Bookmarks")
        
        add_bookmark_action = QAction("Add Bookmark", self)
        add_bookmark_action.setShortcut(QKeySequence("Ctrl+D"))
        add_bookmark_action.triggered.connect(self.add_bookmark)
        bookmarks_menu.addAction(add_bookmark_action)
        
        show_bookmarks_action = QAction("Show Bookmarks", self)
        show_bookmarks_action.triggered.connect(self.show_bookmarks)
        bookmarks_menu.addAction(show_bookmarks_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("About PyBrow", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_navigation_bar(self, visible: bool):
        """Toggle navigation bar visibility"""
        self.navtb.setVisible(visible)
        self.settings.setValue("navigation_bar_visible", visible)

    def add_new_tab(self, url: Optional[str] = None):
        """Add a new browser tab"""
        if url is None:
            url = self.settings.value("homepage", "https://duckduckgo.com")
        
        new_tab = BrowserTab(self.profile, url)
        plus_index = self.get_plus_tab_index()
        
        if plus_index == -1:
            index = self.tabs.addTab(new_tab, "New Tab")
        else:
            index = self.tabs.insertTab(plus_index, new_tab, "New Tab")
        
        self.tabs.setCurrentIndex(index)
        
        # Connect signals
        new_tab.browser.titleChanged.connect(self.make_update_tab_title_func(new_tab))
        new_tab.browser.urlChanged.connect(self.update_history)
        
        # Set initial zoom
        zoom = self.settings.value("zoom_factor", 1.0, type=float)
        new_tab.set_zoom(zoom)

    def add_plus_tab(self):
        """Add the '+' tab for creating new tabs"""
        plus_tab = QWidget()
        index = self.tabs.addTab(plus_tab, "+")
        self.tabs.setTabEnabled(index, True)
        self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, None)

    def get_plus_tab_index(self) -> int:
        """Get the index of the '+' tab"""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "+":
                return i
        return -1

    def close_tab(self, index: int):
        """Close tab at given index"""
        if self.tabs.tabText(index) == "+":
            return
            
        if self.tabs.count() <= 2:  # including plus tab
            return
            
        # Clean up the tab
        tab = self.tabs.widget(index)
        tab.browser.setPage(None)
        tab.deleteLater()
        
        self.tabs.removeTab(index)

    def update_ui(self, index: int):
        """Update UI elements when current tab changes"""
        if index == self.get_plus_tab_index():
            self.add_new_tab()
            new_index = self.get_plus_tab_index() - 1
            if new_index >= 0:
                self.tabs.setCurrentIndex(new_index)
            return
            
        current_browser = self.get_current_browser()
        if current_browser:
            # Update address bar
            url = current_browser.browser.url().toString()
            self.address_bar.setText(url)
            self.address_bar.setCursorPosition(0)
            
            # Update navigation buttons
            self.back_btn.setEnabled(current_browser.browser.history().canGoBack())
            self.forward_btn.setEnabled(current_browser.browser.history().canGoForward())

    def get_current_browser(self) -> Optional[BrowserTab]:
        """Get the current browser tab widget"""
        current_widget = self.tabs.currentWidget()
        return current_widget if isinstance(current_widget, BrowserTab) else None

    def make_update_tab_title_func(self, tab: BrowserTab):
        """Create a function to update tab title"""
        def update_tab_title(title: str):
            index = self.tabs.indexOf(tab)
            if index != -1:
                self.tabs.setTabText(index, title[:20] + "..." if len(title) > 20 else title)
        return update_tab_title

    def load_url(self):
        """Load URL from address bar"""
        text = self.address_bar.text().strip()
        
        if not text:
            return
            
        # Check if it's a URL
        if "." in text and " " not in text and not text.startswith(("http://", "https://")):
            text = "https://" + text
            
        if text.startswith(("http://", "https://", "file://")):
            url = text
        else:
            # Search with current search engine
            search_urls = {
                "DuckDuckGo": "https://duckduckgo.com/?q={}",
                "Google": "https://www.google.com/search?q={}",
                "Bing": "https://www.bing.com/search?q={}",
                "Yahoo": "https://search.yahoo.com/search?p={}"
            }
            engine = self.search_engine_combo.currentText()
            url = search_urls.get(engine, search_urls["DuckDuckGo"]).format(quote_plus(text))
        
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.browser.setUrl(QUrl(url))

    def go_back(self):
        """Navigate back in history"""
        current_browser = self.get_current_browser()
        if current_browser and current_browser.browser.history().canGoBack():
            current_browser.browser.back()

    def go_forward(self):
        """Navigate forward in history"""
        current_browser = self.get_current_browser()
        if current_browser and current_browser.browser.history().canGoForward():
            current_browser.browser.forward()

    def refresh_page(self):
        """Refresh current page"""
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.browser.reload()

    def go_home(self):
        """Go to homepage"""
        homepage = self.settings.value("homepage", "https://duckduckgo.com")
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.browser.setUrl(QUrl(homepage))

    def change_search_engine(self, engine: str):
        """Change default search engine"""
        self.settings.setValue("search_engine", engine)

    def update_history(self, url: QUrl):
        """Update browsing history"""
        url_str = url.toString()
        title = self.get_current_browser().browser.page().title() if self.get_current_browser() else ""
        
        if url_str.startswith(("http://", "https://")):
            self.history.append({
                "url": url_str,
                "title": title,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            # Keep history limited
            if len(self.history) > 100:
                self.history = self.history[-100:]
            
            self.save_history()

    def add_bookmark(self):
        """Add current page to bookmarks"""
        current_browser = self.get_current_browser()
        if current_browser:
            url = current_browser.browser.url().toString()
            title = current_browser.browser.page().title()
            
            # Check if already bookmarked
            if any(bm["url"] == url for bm in self.bookmarks):
                QMessageBox.information(self, "Already Bookmarked", "This page is already in your bookmarks.")
                return
                
            self.bookmarks.append({
                "url": url,
                "title": title,
                "timestamp": datetime.datetime.now().isoformat()
            })
            self.save_bookmarks()
            QMessageBox.information(self, "Bookmark Added", f"'{title}' has been added to your bookmarks.")

    def show_bookmarks(self):
        """Show bookmarks dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmarks")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout()
        
        list_widget = QListWidget()
        for bookmark in self.bookmarks:
            item = QListWidgetItem(bookmark["title"])
            item.setData(Qt.UserRole, bookmark["url"])
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                url = selected_items[0].data(Qt.UserRole)
                current_browser = self.get_current_browser()
                if current_browser:
                    current_browser.browser.setUrl(QUrl(url))

    def zoom_in(self):
        """Zoom in current page"""
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.set_zoom(current_browser.zoom_factor + 0.1)

    def zoom_out(self):
        """Zoom out current page"""
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.set_zoom(current_browser.zoom_factor - 0.1)

    def reset_zoom(self):
        """Reset zoom to 100%"""
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.set_zoom(1.0)

    def find_in_page(self):
        """Show find in page dialog"""
        QMessageBox.information(self, "Find in Page", "Find functionality will be implemented in a future version.")

    def open_file(self):
        """Open local HTML file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open HTML File", "", 
            "HTML Files (*.html *.htm);;All Files (*)"
        )
        
        if file_path:
            current_browser = self.get_current_browser()
            if current_browser:
                current_browser.browser.setUrl(QUrl.fromLocalFile(file_path))

    def save_page(self):
        """Save current page to file"""
        current_browser = self.get_current_browser()
        if not current_browser:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Page As", "", 
            "HTML Files (*.html *.htm);;Web Archive (*.mht);;All Files (*)"
        )
        
        if file_path:
            if file_path.endswith((".html", ".htm")):
                current_browser.browser.page().toHtml(lambda html: self.save_to_file(file_path, html))
            elif file_path.endswith(".mht"):
                current_browser.browser.page().save(file_path, QWebEngineDownloadItem.MimeHtmlSaveFormat)
            else:
                current_browser.browser.page().save(file_path)

    def save_to_file(self, path: str, content: str):
        """Save content to file"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Success", f"Page saved to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save file: {str(e)}")

    def new_window(self):
        """Open new browser window"""
        new_window = MainWindow()
        new_window.show()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About PyBrow",
            "<h2>PyBrow</h2>"
            "<p>A simple Python browser built with PyQt5</p>"
            "<p>Version: 1.0</p>"
            "<p>© 2025 Python Browser Project</p>"
            "<p>MadeBySaints</p>"
            '<p><a href="https://github.com/madebysaints">https://github.com/madebysaints</a></p>'
        )

    def load_settings(self):
        """Load application settings"""
        # Load window geometry if it exists
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromHex(geometry.encode()))
        
        # Load window state if it exists
        state = self.settings.value("window_state")
        if state:
            self.restoreState(QByteArray.fromHex(state.encode()))
        
        # Set default homepage if not set
        if not self.settings.contains("homepage"):
            self.settings.setValue("homepage", "https://duckduckgo.com")
        
        # Load navigation bar visibility
        nav_visible = self.settings.value("navigation_bar_visible", True, type=bool)
        self.navtb.setVisible(nav_visible)

    def load_bookmarks(self) -> List[Dict]:
        """Load bookmarks from file"""
        try:
            if BOOKMARKS_FILE.exists():
                with open(BOOKMARKS_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load bookmarks: {e}")
        return []

    def load_history(self) -> List[Dict]:
        """Load history from file"""
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
        return []

    def save_bookmarks(self):
        """Save bookmarks to file"""
        try:
            with open(BOOKMARKS_FILE, "w") as f:
                json.dump(self.bookmarks, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save bookmarks: {e}")

    def save_history(self):
        """Save history to file"""
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Save settings
        self.settings.setValue("window_geometry", bytes(self.saveGeometry().toHex()).decode())
        self.settings.setValue("window_state", bytes(self.saveState().toHex()).decode())
        
        # Save bookmarks and history
        self.save_bookmarks()
        self.save_history()
        
        # Clean up tabs
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, BrowserTab):
                widget.browser.setPage(None)
        
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PyBrow")
    app.setApplicationDisplayName("PyBrow Browser")
    app.setWindowIcon(QIcon.fromTheme("web-browser"))
    
    # Configure web engine settings for CAPTCHA support
    web_settings = QWebEngineSettings.defaultSettings()
    web_settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    web_settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
    web_settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
    web_settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
    web_settings.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
    
    # Set user agent to modern browser
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
