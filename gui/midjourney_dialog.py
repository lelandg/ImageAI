"""Midjourney embedded web interface dialog."""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QDialogButtonBox, QMessageBox,
    QSplitter, QWidget, QGroupBox, QToolBar, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QDesktopServices

from PySide6.QtWebEngineWidgets import QWebEngineView

# Optional core classes for request interception
try:
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    WEBENGINE_CORE = True
except Exception:
    WEBENGINE_CORE = False

try:
    # Profiles, pages, and settings live in QtWebEngineCore (not Widgets)
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
    WEBENGINE_ENHANCED = True
except Exception:
    WEBENGINE_ENHANCED = False

logger = logging.getLogger(__name__)
console = logging.getLogger("console")

# Shared persistent profile for all Midjourney dialogs
# This ensures cookies/auth persist across dialog instances
_SHARED_MIDJOURNEY_PROFILE = None


def _handle_download(download):
    """Handle file downloads from Midjourney."""
    try:
        from PySide6.QtCore import QStandardPaths
        import os

        # Get default download location
        download_path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if not download_path:
            download_path = os.path.expanduser("~/Downloads")

        # Get suggested filename
        suggested_name = download.downloadFileName() if hasattr(download, 'downloadFileName') else download.suggestedFileName()
        file_path = os.path.join(download_path, suggested_name)

        # Set download path
        download.setDownloadDirectory(download_path)
        download.setDownloadFileName(suggested_name)

        # Accept the download
        download.accept()

        logger.info(f"Download started: {suggested_name} -> {file_path}")
        console.info(f"Downloading: {suggested_name}")

        # Connect state changed signal to track completion
        def on_state_change(state):
            try:
                # QWebEngineDownloadRequest.DownloadCompleted = 2
                if int(state) == 2:
                    logger.info(f"Download finished: {suggested_name}")
                    console.info(f"✓ Downloaded: {suggested_name}")
                elif int(state) == 3:  # DownloadCancelled
                    logger.warning(f"Download cancelled: {suggested_name}")
                elif int(state) == 4:  # DownloadInterrupted
                    logger.error(f"Download interrupted: {suggested_name}")
            except Exception as e:
                logger.debug(f"State change handler error: {e}")

        try:
            download.stateChanged.connect(on_state_change)
        except Exception as e:
            logger.debug(f"Could not connect state change handler: {e}")

    except Exception as e:
        logger.error(f"Download handler error: {e}")
        try:
            download.accept()  # Try to accept anyway
        except Exception:
            pass


def get_shared_midjourney_profile():
    """Get or create the shared persistent Midjourney profile."""
    global _SHARED_MIDJOURNEY_PROFILE

    if _SHARED_MIDJOURNEY_PROFILE is None and WEBENGINE_ENHANCED:
        try:
            import os
            import platform as _platform
            from PySide6.QtCore import QStandardPaths
            from PySide6.QtWebEngineCore import QWebEngineProfile

            # Create persistent profile (no parent - lives for app lifetime)
            profile = QWebEngineProfile("MidjourneyPersistent")

            # User-Agent
            sysname = _platform.system()
            if sysname == "Windows":
                platform_ua = "Windows NT 10.0; Win64; x64"
            elif sysname == "Darwin":
                platform_ua = "Macintosh; Intel Mac OS X 10_15_7"
            else:
                platform_ua = "X11; Linux x86_64"
            chrome_ua = (
                f"Mozilla/5.0 ({platform_ua}) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
            profile.setHttpUserAgent(chrome_ua)
            profile.setHttpAcceptLanguage("en-US,en;q=0.9")

            # Persistence
            app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            cache_path = os.path.join(app_data, "midjourney_web_cache")
            storage_path = os.path.join(app_data, "midjourney_web_storage")
            os.makedirs(cache_path, exist_ok=True)
            os.makedirs(storage_path, exist_ok=True)
            profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
            profile.setCachePath(cache_path)
            profile.setPersistentStoragePath(storage_path)
            profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)

            # Enable downloads
            try:
                profile.downloadRequested.connect(_handle_download)
                logger.info("Download handler connected")
            except Exception as e:
                logger.warning(f"Could not connect download handler: {e}")

            _SHARED_MIDJOURNEY_PROFILE = profile
            logger.info("Created persistent shared Midjourney profile")
        except Exception as e:
            logger.error(f"Failed to create shared profile: {e}")

    return _SHARED_MIDJOURNEY_PROFILE


class MidjourneyWebDialog(QDialog):
    """Dialog for Midjourney web interface with instructions."""

    imageGenerated = Signal(str)  # Emitted when user confirms image is generated
    sessionStarted = Signal(str, str)  # prompt, command - for session tracking
    sessionEnded = Signal()  # Emitted when dialog closes

    def __init__(self, web_url: str, slash_command: str, prompt: str = "", parent=None):
        """
        Initialize Midjourney web dialog.

        Args:
            web_url: URL of Midjourney web interface
            slash_command: Generated slash command to paste
            prompt: The original prompt (for session tracking)
            parent: Parent widget
        """
        super().__init__(parent)
        self.web_url = web_url

        # For Midjourney web UI, remove the Discord "/imagine prompt:" prefix
        # The web UI only needs the prompt and parameters
        if slash_command.startswith("/imagine prompt:"):
            self.web_command = slash_command.replace("/imagine prompt:", "", 1).strip()
        else:
            self.web_command = slash_command

        self.slash_command = slash_command  # Keep original for Discord mode
        self.prompt = prompt or self._extract_prompt_from_command(slash_command)
        self._popups = []
        self.setup_ui()
        self._suppress_qt_warnings()
        self.load_url()

        # Emit session started signal
        self.sessionStarted.emit(self.prompt, self.slash_command)

    def _suppress_qt_warnings(self):
        """Suppress common Qt WebEngine warnings that clutter the console."""
        try:
            import os
            import sys

            # Suppress Qt logging for specific categories
            # Set environment variables to reduce Qt warning output
            os.environ['QT_LOGGING_RULES'] = (
                'qt.webenginecontext.debug=false;'
                'qt.webengine.permissions.debug=false;'
                'qt.webengine.chromium.debug=false'
            )

            # Create a custom logging filter for qt logger
            qt_logger = logging.getLogger('qt')

            class QtWarningFilter(logging.Filter):
                def filter(self, record):
                    # Filter out common harmless Qt warnings
                    message = record.getMessage().lower()
                    suppress_patterns = [
                        'permissions-policy header',
                        'browsing-topics',
                        'interest-cohort',
                        'unrecognized feature',
                        'webgpu context provider',
                        'font-size:0;color:transparent',
                    ]

                    for pattern in suppress_patterns:
                        if pattern in message:
                            return False  # Suppress this message

                    return True  # Allow other messages

            # Add the filter to the qt logger
            qt_logger.addFilter(QtWarningFilter())

            logger.debug("Qt warning suppression configured")

        except Exception as e:
            logger.debug(f"Could not configure Qt warning suppression: {e}")

    def _extract_prompt_from_command(self, command: str) -> str:
        """Extract prompt from slash command."""
        if "/imagine prompt:" in command:
            # Extract everything between prompt: and first --
            parts = command.split("prompt:", 1)
            if len(parts) > 1:
                prompt_part = parts[1].split("--")[0].strip()
                return prompt_part
        return command

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Midjourney Image Generation")
        self.setModal(False)  # Non-modal so user can interact with main window
        self.resize(1400, 900)

        # Main layout
        layout = QVBoxLayout(self)

        # Create splitter for web view and instructions
        splitter = QSplitter(Qt.Horizontal)

        # Left side - Web view
        web_container = QWidget()
        web_layout = QVBoxLayout(web_container)
        web_layout.setContentsMargins(0, 0, 0, 0)

        # Web view with enhanced settings for Midjourney compatibility
        self.web_view = QWebEngineView()
        self.web_view.setMinimumWidth(900)

        # Enable focus and keyboard input
        self.web_view.setFocusPolicy(Qt.StrongFocus)
        self.web_view.setFocus()

        self._configure_web_view()
        web_layout.addWidget(self.web_view)

        splitter.addWidget(web_container)

        # Right side - Instructions and command
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Instructions group
        instructions_group = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout(instructions_group)

        instructions = QLabel(
            "<b>How to generate your image:</b><br><br>"
            "1. Wait for Midjourney to load and log in if needed<br>"
            "2. Navigate to your desired server/channel<br>"
            "3. Click in the message box at the bottom<br>"
            "4. Paste the command (Ctrl+V)<br>"
            "5. Press Enter to generate<br>"
            "6. Wait for image generation (30-60 seconds)<br>"
            "7. When satisfied, click 'Image Ready' below<br><br>"
            "<i>Notes:</i><br>"
            "• The command is already copied to your clipboard<br>"
            "• <b>Google login:</b> Will open in external browser (security requirement)<br>"
            "• <b>Discord login:</b> Use 'Login with Discord (Popup)' button below<br>"
            "• If view gets stuck after login, click 'Reload Page' button"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { padding: 10px; }")
        instructions_layout.addWidget(instructions)

        right_layout.addWidget(instructions_group)

        # Command display group
        command_group = QGroupBox("Your Command (Already Copied)")
        command_layout = QVBoxLayout(command_group)

        self.command_display = QTextEdit()
        self.command_display.setPlainText(self.web_command)  # Use web_command (no /imagine prefix)
        self.command_display.setReadOnly(True)
        self.command_display.setMaximumHeight(150)
        self.command_display.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 10pt; background-color: #f0f0f0; }"
        )
        command_layout.addWidget(self.command_display)

        # Copy button
        copy_btn = QPushButton("📋 Copy Command Again")
        copy_btn.clicked.connect(self.copy_command)
        command_layout.addWidget(copy_btn)

        right_layout.addWidget(command_group)

        # Open in browser button
        browser_btn = QPushButton("🌐 Open in External Browser")
        browser_btn.clicked.connect(self.open_in_browser)
        right_layout.addWidget(browser_btn)

        # Manual reload button
        reload_btn = QPushButton("🔄 Reload Page")
        reload_btn.setToolTip("Manually reload the Midjourney page (useful if stuck after login)")
        reload_btn.clicked.connect(self.web_view.reload)
        right_layout.addWidget(reload_btn)

        # Reset session (clear cookies/cache)
        reset_btn = QPushButton("🧹 Reset Session (Clear Cookies)")
        reset_btn.setToolTip("Clears cookies and cache for Midjourney domain to retrigger human verification/login")
        reset_btn.clicked.connect(self._reset_session)
        right_layout.addWidget(reset_btn)

        # Direct Discord login helper (embedded popup)
        discord_popup_btn = QPushButton("🔑 Login with Discord (Popup)")
        discord_popup_btn.setToolTip("Opens an embedded Discord login window using the same session/profile")
        discord_popup_btn.clicked.connect(self._open_discord_login_popup)
        right_layout.addWidget(discord_popup_btn)

        # Import downloaded images button
        import_btn = QPushButton("📥 Import Downloaded Images")
        import_btn.setToolTip("Scan Downloads folder for Midjourney images and import them to ImageAI")
        import_btn.clicked.connect(self._import_downloaded_images)
        import_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        right_layout.addWidget(import_btn)

        # Add stretch to push buttons to bottom
        right_layout.addStretch()

        # Status/tips
        tips_group = QGroupBox("Tips")
        tips_layout = QVBoxLayout(tips_group)

        tips_label = QLabel(
            "• Use U1-U4 buttons to upscale images<br>"
            "• Use V1-V4 for variations<br>"
            "• Right-click images to save<br>"
            "• Check your subscription at Account → Manage"
        )
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet("QLabel { font-size: 9pt; color: #666; }")
        tips_layout.addWidget(tips_label)

        right_layout.addWidget(tips_group)

        # Dialog buttons
        button_box = QDialogButtonBox()

        self.ready_btn = QPushButton("✓ Image Ready")
        self.ready_btn.setToolTip("Click when your image is generated and ready")
        self.ready_btn.clicked.connect(self.on_image_ready)
        button_box.addButton(self.ready_btn, QDialogButtonBox.AcceptRole)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_box.addButton(cancel_btn, QDialogButtonBox.RejectRole)

        right_layout.addWidget(button_box)

        splitter.addWidget(right_panel)

        # Set splitter sizes (70% web, 30% instructions)
        splitter.setSizes([980, 420])
        splitter.setStretchFactor(0, 1)  # Web view can stretch
        splitter.setStretchFactor(1, 0)  # Instructions panel fixed

        layout.addWidget(splitter)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_to_web)
        QShortcut(QKeySequence("Escape"), self, self.reject)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.on_image_ready)

        # Auto-copy command on dialog open
        QTimer.singleShot(100, self.copy_command)

    def _configure_web_view(self):
        """Configure the web view for better Midjourney compatibility.

        Attaches a custom profile with a modern Chrome UA, persistent
        storage/cookies, and a page subclass that supports popups and
        external auth redirects.
        """
        try:
            if WEBENGINE_ENHANCED:
                try:
                    # Use shared persistent profile
                    profile = get_shared_midjourney_profile()
                    if profile is None:
                        raise Exception("Failed to get shared profile")

                    self._profile = profile
                    logger.info(f"WebEngine User-Agent (override): {profile.httpUserAgent()}")

                    # Third‑party cookies (if supported)
                    try:
                        if hasattr(QWebEngineProfile, 'setThirdPartyCookiePolicy'):
                            for name in (
                                'AllowAllThirdPartyCookies',
                                'AlwaysAllowThirdPartyCookies',
                                'ThirdPartyCookiesAllow',
                                'AllowThirdPartyCookies'
                            ):
                                if hasattr(QWebEngineProfile, name):
                                    profile.setThirdPartyCookiePolicy(getattr(QWebEngineProfile, name))
                                    break
                    except Exception:
                        pass

                    # Request logging (optional)
                    if WEBENGINE_CORE:
                        try:
                            class _RequestLogger(QWebEngineUrlRequestInterceptor):
                                def interceptRequest(self, info):
                                    try:
                                        url = info.requestUrl().toString()
                                        method = bytes(info.requestMethod()).decode('utf-8', 'ignore')
                                    except Exception:
                                        url = str(info.requestUrl())
                                        method = 'GET'
                                    logger.debug(f"WEB REQ {method} {url}")
                            self._req_logger = _RequestLogger()
                            profile.setUrlRequestInterceptor(self._req_logger)
                        except Exception as e:
                            logger.debug(f"Could not attach request interceptor: {e}")

                    # Cookie logging (optional)
                    try:
                        store = profile.cookieStore()
                        def _cookie_name(c):
                            try:
                                return bytes(c.name()).decode('utf-8','ignore')
                            except Exception:
                                return str(c.name())
                        store.cookieAdded.connect(lambda c: logger.debug(f"COOKIE added: {_cookie_name(c)} domain={c.domain()} path={c.path()} secure={c.isSecure()}"))
                        store.cookieRemoved.connect(lambda c: logger.debug(f"COOKIE removed: {_cookie_name(c)} domain={c.domain()}"))
                    except Exception as e:
                        logger.debug(f"Cookie logging attach failed: {e}")

                    # Page subclass with popup + auth handling
                    class _LoggingWebPage(QWebEnginePage):
                        def __init__(self, prof, parent, owner_dialog):
                            super().__init__(prof, parent)
                            self._owner = owner_dialog

                        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
                            try:
                                lvl = int(level)
                            except Exception:
                                lvl = 0
                            msg = f"JS[{lvl}] {sourceID}:{lineNumber} {message}"
                            logger.info(msg)

                        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                            s = url.toString()
                            try:
                                nav_kind = int(nav_type)
                            except Exception:
                                nav_kind = str(nav_type)
                            logger.info(f"NAV type={nav_kind} main={is_main_frame} url={s}")

                            # Send Google auth to external browser
                            try:
                                host = url.host().lower()
                            except Exception:
                                host = ""
                            if any(part in host for part in (
                                'accounts.google.com', 'signin.google.com', 'oauth2.googleapis.com'
                            )):
                                try:
                                    self._owner._open_external_auth(url)
                                except Exception:
                                    pass
                                return False

                            # OAuth redirect back to midjourney.com is handled by _AuthPopupDialog._on_url
                            # Don't reload here to avoid duplicate reloads
                            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

                        def createWindow(self, wintype):
                            try:
                                wt = int(wintype)
                            except Exception:
                                wt = str(wintype)
                            logger.info(f"POPUP window requested: type={wt}")

                            try:
                                popup_page = _LoggingWebPage(self.profile(), self, self._owner)
                            except Exception:
                                popup_page = QWebEnginePage(self.profile(), self)
                            try:
                                popup = _AuthPopupDialog(self._owner, popup_page)
                                self._owner._register_popup(popup)
                                popup.show()
                            except Exception as e:
                                logger.debug(f"Failed to create embedded popup: {e}")
                            return popup_page

                    # Attach page
                    page = _LoggingWebPage(profile, self.web_view, self)
                    self._page = page
                    self.web_view.setPage(page)

                    # Feature permissions
                    try:
                        from PySide6.QtWebEngineCore import QWebEnginePage as _QWEP
                        def _on_feature(url, feature):
                            try:
                                logger.info(f"FEATURE request: {int(feature)} for {url.toString()}")
                            except Exception:
                                logger.info(f"FEATURE request: {feature} for {url.toString()}")
                            grantable = {
                                getattr(_QWEP, 'Notifications', None),
                                getattr(_QWEP, 'Geolocation', None),
                                getattr(_QWEP, 'MouseLock', None)
                            }
                            if feature in grantable:
                                page.setFeaturePermission(url, feature, getattr(_QWEP, 'PermissionGrantedByUser', 0))
                            else:
                                page.setFeaturePermission(url, feature, getattr(_QWEP, 'PermissionUnknown', 0))
                        page.featurePermissionRequested.connect(_on_feature)
                    except Exception:
                        pass

                    # Settings
                    settings = page.settings()
                    settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
                    settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
                    settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
                    settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
                    settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
                    settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
                    settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
                    try:
                        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
                        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
                    except Exception:
                        pass

                    try:
                        actual_ua = profile.httpUserAgent()
                    except Exception:
                        actual_ua = "<unavailable>"
                    logger.info("Web view configured with custom profile + Chrome UA")
                    logger.info(f"Effective User-Agent: {actual_ua}")
                    logger.info(f"WEBENGINE_ENHANCED={WEBENGINE_ENHANCED}, WEBENGINE_CORE={WEBENGINE_CORE}")
                    console.info("Web view enhanced for Midjourney")
                except Exception as e:
                    logger.info(f"Profile setup failed; falling back to default page: {e}")
                    page = self.web_view.page()
                    if page:
                        s = page.settings()
                        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
                        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
                        s.setAttribute(QWebEngineSettings.AutoLoadImages, True)
                        s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
                        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
                        s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
                        s.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
                        logger.info("Using default profile with enhanced settings")
                    else:
                        logger.info("Using basic web view configuration")
                        console.info("Using basic web view")
            else:
                logger.info("Enhanced WebEngine features not available")
                console.info("Using basic web view")
                try:
                    page = self.web_view.page()
                    prof = page.profile()
                    prof.setHttpUserAgent(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    )
                    try:
                        prof.setHttpAcceptLanguage("en-US,en;q=0.9")
                    except Exception:
                        pass
                    s = page.settings()
                    s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
                    s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
                    s.setAttribute(QWebEngineSettings.AutoLoadImages, True)
                    s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
                    s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
                    s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
                    s.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
                except Exception as e:
                    logger.debug(f"Basic UA/settings apply failed: {e}")
        except Exception as e:
            logger.error(f"Error configuring web view: {e}")
            console.info("Using basic web view due to configuration error")

        # Connect web view signals for logging (connect only once during initialization)
        try:
            self.web_view.loadStarted.connect(lambda: logger.info("LOAD started"))
            self.web_view.loadFinished.connect(lambda ok: (logger.info(f"LOAD finished ok={ok}"), self._post_load_check(ok), self.web_view.setFocus()))
            self.web_view.urlChanged.connect(lambda u: logger.info(f"URL changed -> {u.toString() or '<invalid>'}"))
        except Exception as e:
            logger.debug(f"Could not connect web view signals: {e}")

    def load_url(self):
        """Load the Midjourney web interface."""
        try:
            url = QUrl(self.web_url)
            self.web_view.load(url)
            logger.info(f"Loading Midjourney web interface: {self.web_url}")
            console.info(f"Opening Midjourney web interface...")
        except Exception as e:
            logger.error(f"Failed to load web interface: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load web interface:\n{str(e)}")

    def copy_command(self):
        """Copy slash command to clipboard."""
        try:
            from PySide6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self.web_command)  # Copy web_command (no /imagine prefix)

            # Visual feedback
            self.command_display.selectAll()
            QTimer.singleShot(200, self.command_display.clearFocus)

            console.info("Command copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def paste_to_web(self):
        """Attempt to paste into web view (may not work due to security)."""
        # This is a placeholder - direct paste to web view is usually blocked
        # User will need to manually paste
        console.info("Please click in the message box and paste (Ctrl+V)")

    def open_in_browser(self):
        """Open Midjourney in external browser."""
        try:
            QDesktopServices.openUrl(QUrl(self.web_url))
            console.info("Opened in external browser")
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    def _open_discord_login_popup(self):
        """Open Discord login in an embedded popup with the same profile.

        This helps bypass sites that suppress the login button popup.
        """
        try:
            # Reuse the existing profile
            try:
                profile = self._page.profile() if hasattr(self, '_page') and self._page else None
            except Exception:
                profile = None
            if profile is None and hasattr(self, '_profile'):
                profile = self._profile

            if profile is None:
                # Fallback to current page profile
                try:
                    profile = self.web_view.page().profile()
                except Exception:
                    profile = None

            # Create a page for the popup
            if profile is not None:
                page = QWebEnginePage(profile, self)
            else:
                page = QWebEnginePage(self)

            popup = _AuthPopupDialog(self, page)
            try:
                page.load(QUrl("https://discord.com/login"))
            except Exception:
                pass
            self._register_popup(popup)
            popup.show()
            console.info("Opened Discord login popup")
        except Exception as e:
            logger.error(f"Failed to open Discord login popup: {e}")

    def _import_downloaded_images(self, auto_import=False):
        """Scan Downloads folder and import Midjourney images matching the prompt.

        Args:
            auto_import: If True, auto-imports matches without showing dialog
        """
        try:
            from PySide6.QtCore import QStandardPaths
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            from pathlib import Path
            import shutil
            from datetime import datetime
            import re

            # Get downloads folder
            downloads_path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            if not downloads_path:
                downloads_path = str(Path.home() / "Downloads")

            downloads_dir = Path(downloads_path)
            if not downloads_dir.exists():
                if not auto_import:
                    QMessageBox.warning(self, "Not Found", f"Downloads folder not found: {downloads_dir}")
                return

            # Extract key words from prompt to match against filenames
            # Clean the prompt and get significant words (4+ chars, first 5 words)
            prompt_words = re.findall(r'\b\w{4,}\b', self.prompt.lower())[:5]

            midjourney_images = []

            for img_file in downloads_dir.glob("*.png"):
                # Check if it's a Midjourney image (contains job ID pattern with underscores)
                if "_" in img_file.stem and len(img_file.stem) > 20:
                    filename_lower = img_file.stem.lower()
                    # Match if filename contains some of our prompt words
                    matches = sum(1 for word in prompt_words if word in filename_lower)
                    if matches >= min(2, len(prompt_words)):  # At least 2 words match, or all if less than 2
                        midjourney_images.append(img_file)

            if not midjourney_images:
                if not auto_import:
                    QMessageBox.information(self, "No Images Found",
                        f"No Midjourney images found matching this prompt.\n\n"
                        f"Looking for files containing: {', '.join(prompt_words[:3])}")
                return

            # Sort by modification time (newest first)
            midjourney_images.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # If auto-importing, skip the selection dialog
            if auto_import:
                selected_images = midjourney_images
            else:
                # Let user select which images to import
                from PySide6.QtWidgets import QListWidget, QDialog, QVBoxLayout, QDialogButtonBox

                dialog = QDialog(self)
                dialog.setWindowTitle("Select Images to Import")
                dialog.resize(600, 400)

                layout = QVBoxLayout(dialog)
                layout.addWidget(QLabel(f"Found {len(midjourney_images)} Midjourney image(s) matching this prompt:"))

                list_widget = QListWidget()
                list_widget.setSelectionMode(QListWidget.MultiSelection)
                for img in midjourney_images:
                    mtime = datetime.fromtimestamp(img.stat().st_mtime)
                    time_str = mtime.strftime("%I:%M:%S %p")
                    list_widget.addItem(f"{img.name} ({time_str})")
                list_widget.selectAll()  # Select all by default
                layout.addWidget(list_widget)

                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                layout.addWidget(buttons)

                if dialog.exec() != QDialog.Accepted:
                    return

                # Get selected indices
                selected_indices = [item.row() for item in list_widget.selectedIndexes()]
                if not selected_indices:
                    return

                selected_images = [midjourney_images[idx] for idx in selected_indices]

            # Import selected images
            parent = self.parent()
            if not parent or not hasattr(parent, 'output_dir'):
                if not auto_import:
                    QMessageBox.warning(self, "Error", "Cannot access output directory")
                return

            output_dir = Path(parent.output_dir)
            imported_count = 0

            for src_path in selected_images:
                dest_path = output_dir / src_path.name

                # Avoid overwriting - add number if needed
                counter = 1
                while dest_path.exists():
                    dest_path = output_dir / f"{src_path.stem}_{counter}{src_path.suffix}"
                    counter += 1

                try:
                    shutil.copy2(src_path, dest_path)

                    # Create metadata file
                    metadata = {
                        "prompt": self.prompt,
                        "provider": "midjourney",
                        "model": "midjourney",
                        "timestamp": datetime.now().isoformat(),
                        "command": self.slash_command,
                        "source_file": str(src_path)
                    }

                    import json
                    metadata_path = dest_path.with_suffix('.json')
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2)

                    logger.info(f"Imported Midjourney image: {dest_path.name}")
                    imported_count += 1

                except Exception as e:
                    logger.error(f"Failed to import {src_path.name}: {e}")

            if imported_count > 0:
                console.info(f"✓ Imported {imported_count} Midjourney image(s)")
                if not auto_import:
                    QMessageBox.information(self, "Import Complete",
                        f"Successfully imported {imported_count} image(s) to:\n{output_dir}")

                # Refresh parent window history if possible
                if hasattr(parent, 'load_history'):
                    try:
                        parent.load_history()
                    except Exception:
                        pass

            return imported_count

        except Exception as e:
            logger.error(f"Failed to import images: {e}")
            if not auto_import:
                console.error(f"Import failed: {e}")
                QMessageBox.critical(self, "Import Error", f"Failed to import images:\n{str(e)}")
            return 0

    # ---- Helpers for external auth / popups ----
    def _post_load_check(self, ok: bool):
        """After-load sanity checks to recover from blank/404 pages.

        Some bot-protected flows sometimes render an empty page instead of
        the verification challenge. If we detect obviously empty content or
        a 404-like title, we trigger a soft reload. This keeps behavior
        ToS‑safe — no automation beyond standard reload.
        """
        try:
            if not ok:
                # Only try one soft reload per dialog open; then fallback
                if not getattr(self, "_reloaded_once", False):
                    self._reloaded_once = True
                    logger.info("Post-load: not ok, scheduling single reload")
                    QTimer.singleShot(700, self.web_view.reload)
                else:
                    logger.info("Post-load: still failing → opening in external browser")
                    QDesktopServices.openUrl(QUrl(self.web_url))
                return

            page = self.web_view.page()
            def _inspect(result):
                try:
                    title, text = result or ("", "")
                except Exception:
                    title, text = ("", "")
                title_l = (title or "").lower()
                txt = (text or "").lower()
                # Reload only for explicit 404 signatures; avoid false positives
                if ("404" in title_l) or ("not been /imagine" in txt and "404" in txt):
                    if not getattr(self, "_reloaded_once", False):
                        self._reloaded_once = True
                        logger.info("Post-load: detected 404 → single reload")
                        self.web_view.reload()
                    else:
                        logger.info("Post-load: 404 persists → opening in external browser")
                        QDesktopServices.openUrl(QUrl(self.web_url))
            try:
                page.runJavaScript(
                    "[document.title, (document.body && document.body.innerText) || '']",
                    _inspect
                )
            except Exception as e:
                logger.debug(f"Post-load JS check failed: {e}")
        except Exception as e:
            logger.debug(f"Post-load check error: {e}")

    def _reset_session(self):
        """Clear cookies/cache for the dialog profile and reload.

        Use this when Cloudflare or login gets stuck and verification no
        longer appears. This keeps the dialog self‑contained.
        """
        try:
            if hasattr(self, '_profile') and self._profile:
                logger.info("RESET SESSION: clearing cookies + cache")
                try:
                    self._profile.clearHttpCache()
                except Exception:
                    pass
                try:
                    store = self._profile.cookieStore()
                    store.deleteAllCookies()
                except Exception:
                    pass
            self.web_view.reload()
        except Exception as e:
            logger.error(f"Reset session failed: {e}")

    def _handle_popup_url(self, url: QUrl):
        try:
            s = url.toString()
            logger.info(f"POPUP navigated -> {s}; opening externally")
            QDesktopServices.openUrl(url)
        finally:
            # No return; popup page will be GC'd
            pass

    def _open_external_auth(self, url: QUrl):
        s = url.toString()
        logger.info(f"AUTH domain detected -> opening externally: {s}")
        console.info("Login requires external browser; opening now...")
        try:
            QDesktopServices.openUrl(url)
        except Exception as e:
            logger.error(f"Failed to open external auth URL: {e}")

    # -- popup management --
    def _register_popup(self, popup_dialog: '._AuthPopupDialog'):
        try:
            self._popups.append(popup_dialog)
            # Don't reload on popup close - _on_url already handles reload when OAuth succeeds
            # popup_dialog.finished.connect(lambda _=None: self.web_view.reload())
        except Exception:
            pass

    def on_image_ready(self):
        """Handle when user indicates image is ready."""
        reply = QMessageBox.question(
            self,
            "Confirm Image Ready",
            "Have you successfully generated your image in Midjourney?\n\n"
            "Note: You'll need to save the image manually from the web interface.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.imageGenerated.emit("Midjourney image generated")
            self.accept()

    def closeEvent(self, event):
        """Handle close event."""
        # Auto-import any downloaded images matching this prompt
        try:
            imported = self._import_downloaded_images(auto_import=True)
            if imported > 0:
                logger.info(f"Auto-imported {imported} Midjourney image(s) on dialog close")
        except Exception as e:
            logger.debug(f"Auto-import on close failed: {e}")

        # Emit session ended signal
        self.sessionEnded.emit()

        # Clean up popup dialogs only
        # Don't destroy the profile/page - they're shared and persistent
        try:
            for p in getattr(self, '_popups', []) or []:
                try:
                    p.close()
                except Exception:
                    pass
            self._popups = []
        except Exception:
            pass

        super().closeEvent(event)


class _AuthPopupDialog(QDialog):
    """Small dialog to host popup auth windows inside the app.

    Uses the same QWebEngineProfile so cookies and auth propagate back
    to the main Midjourney view.
    """

    def __init__(self, parent_dialog: MidjourneyWebDialog, page: 'QWebEnginePage'):
        super().__init__(parent_dialog)
        self.setWindowTitle("Authentication")
        self.resize(720, 720)
        self.setModal(False)

        v = QVBoxLayout(self)
        tb = QToolBar()
        v.addWidget(tb)

        self.addr = QLineEdit()
        self.addr.setReadOnly(True)
        self.addr.setPlaceholderText("Loading…")

        btn_back = QPushButton("←")
        btn_fwd = QPushButton("→")
        btn_reload = QPushButton("⟳")
        btn_ext = QPushButton("Open in Browser")

        tb.addWidget(btn_back)
        tb.addWidget(btn_fwd)
        tb.addWidget(btn_reload)
        tb.addWidget(self.addr)
        tb.addWidget(btn_ext)

        self.view = QWebEngineView()
        self.view.setPage(page)
        v.addWidget(self.view)

        try:
            page.windowCloseRequested.connect(self.accept)
            page.urlChanged.connect(self._on_url)
        except Exception:
            pass

        btn_back.clicked.connect(self.view.back)
        btn_fwd.clicked.connect(self.view.forward)
        btn_reload.clicked.connect(self.view.reload)
        btn_ext.clicked.connect(lambda: QDesktopServices.openUrl(self.view.url()))

    def _on_url(self, u: QUrl):
        s = u.toString()
        self.addr.setText(s)
        logger.info(f"POPUP URL -> {s}")
        # When OAuth handler completes and redirects back to home, close popup
        try:
            host = u.host().lower()
        except Exception:
            host = ""

        try:
            # Wait for the OAuth handler to complete its work and redirect to /home
            # Don't close on the /auth/handler URL - wait for the redirect after processing
            if host.endswith('midjourney.com'):
                path = u.path().lower() if hasattr(u, 'path') else ''

                # If we're back at /home after OAuth, that means auth succeeded and cookies are set
                if path == '/home' or path == '/' or 'redirectUrl=' in s:
                    # Check if we came from an auth flow (popup will have auth state)
                    if hasattr(self, '_from_auth_flow') and self._from_auth_flow:
                        try:
                            from PySide6.QtCore import QTimer
                            owner = self.parent()
                            if owner is not None and hasattr(owner, 'web_view'):
                                # Close popup and reload main view
                                QTimer.singleShot(500, self.accept)
                                QTimer.singleShot(800, owner.web_view.reload)
                                logger.info("OAuth complete (redirected to home), closing popup and reloading main view")
                                console.info("Login successful! Reloading main view...")
                        except Exception as e:
                            logger.debug(f"Failed to reload main view after OAuth: {e}")
                elif 'auth/handler' in s and ('code=' in s or 'token=' in s):
                    # Mark that we're in an auth flow, but don't close yet
                    self._from_auth_flow = True
                    logger.info("OAuth callback detected, waiting for redirect to home...")
        except Exception as e:
            logger.debug(f"Error in _on_url: {e}")

    def page(self):
        return self.view.page()
