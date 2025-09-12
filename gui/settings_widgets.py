"""Advanced settings widgets for ImageAI."""

from typing import Dict, Any, Optional, Tuple
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QSlider, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QGroupBox, QButtonGroup,
    QRadioButton, QToolButton, QFrame, QScrollArea,
    QSizePolicy, QLineEdit
)


class AspectRatioSelector(QWidget):
    """Visual aspect ratio selector with preview rectangles and manual input."""
    
    ratioChanged = Signal(str)
    
    ASPECT_RATIOS = {
        "1:1": {"label": "Square", "icon": "⬜", "use": "Social media, avatars"},
        "3:4": {"label": "Portrait", "icon": "📱", "use": "Phone wallpapers"},
        "4:3": {"label": "Classic", "icon": "🖼️", "use": "Photos, presentations"},
        "16:9": {"label": "Wide", "icon": "🖥️", "use": "Desktop, videos"},
        "9:16": {"label": "Tall", "icon": "📲", "use": "Stories, Reels"},
        "21:9": {"label": "Ultra", "icon": "🎬", "use": "Cinematic"},
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_ratio = "1:1"
        self.buttons = {}
        self.custom_button = None
        self.custom_input = None
        self._using_custom = False
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Preset buttons row
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(3)
        
        for ratio, info in self.ASPECT_RATIOS.items():
            button = self._create_ratio_button(ratio, info)
            self.buttons[ratio] = button
            buttons_layout.addWidget(button)
        
        # Add custom button
        self.custom_button = self._create_custom_button()
        buttons_layout.addWidget(self.custom_button)
        
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)
        
        # Manual input row (initially hidden)
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)
        
        self.custom_label = QLabel("Custom AR:")
        self.custom_label.setVisible(False)
        input_layout.addWidget(self.custom_label)
        
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("e.g., 16:10 or 1.6")
        self.custom_input.setMaximumWidth(100)
        self.custom_input.setVisible(False)
        self.custom_input.setToolTip("Enter aspect ratio as W:H (e.g., 16:9) or decimal (e.g., 1.78)")
        
        # Add validator for aspect ratio input
        from PySide6.QtCore import QRegularExpression
        regex = QRegularExpression(r"^\d+(\.\d+)?(:?\d+(\.\d+)?)?$")
        validator = QRegularExpressionValidator(regex)
        self.custom_input.setValidator(validator)
        
        self.custom_input.editingFinished.connect(self._on_custom_input_changed)
        input_layout.addWidget(self.custom_input)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.setMaximumWidth(60)
        self.apply_button.setVisible(False)
        self.apply_button.clicked.connect(self._apply_custom_ratio)
        input_layout.addWidget(self.apply_button)
        
        input_layout.addStretch()
        main_layout.addLayout(input_layout)
        
        # Select default
        self.set_ratio("1:1")
    
    def _create_ratio_button(self, ratio: str, info: dict) -> QToolButton:
        """Create a visual button for aspect ratio selection."""
        button = QToolButton()
        button.setCheckable(True)
        button.setToolTip(f"{info['label']}\n{info['use']}")
        button.setMinimumSize(55, 55)  # Even smaller for single row
        button.setMaximumSize(60, 60)  # Constrain max size
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Create visual preview
        width, height = map(int, ratio.split(':'))
        max_size = 30  # Even smaller preview for single row
        if width > height:
            w = max_size
            h = int(max_size * height / width)
        else:
            h = max_size
            w = int(max_size * width / height)
        
        # Create pixmap with aspect ratio preview
        pixmap = QPixmap(55, 45)  # Smaller pixmap for smaller buttons
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        
        # Draw rectangle
        rect_color = QColor("#4CAF50")
        painter.fillRect((55-w)//2, (45-h)//2 - 5, w, h, rect_color)
        
        # Draw label with dark text on white background for visibility
        painter.setPen(Qt.black)  # Dark text
        font = QFont()
        font.setPixelSize(10)  # Smaller font for smaller buttons
        font.setBold(True)  # Bold for better visibility
        painter.setFont(font)
        
        # Draw white background for text
        text_rect = painter.fontMetrics().boundingRect(ratio)
        text_x = (55 - text_rect.width()) // 2
        text_y = 45 - 10
        painter.fillRect(text_x - 2, text_y - 2, text_rect.width() + 4, 12, QColor(255, 255, 255, 200))
        
        # Draw the ratio text
        painter.drawText(pixmap.rect(), Qt.AlignBottom | Qt.AlignHCenter, ratio)
        painter.end()
        
        button.setIcon(pixmap)
        button.setIconSize(QSize(55, 45))
        button.clicked.connect(lambda: self._on_ratio_clicked(ratio))
        button.setProperty('ratio', ratio)
        
        # Add custom style for better selected state visibility
        button.setStyleSheet("""
            QToolButton {
                border: 2px solid transparent;
                border-radius: 4px;
                background: rgba(0, 0, 0, 0.02);
            }
            QToolButton:hover {
                background: rgba(76, 175, 80, 0.1);
                border: 2px solid rgba(76, 175, 80, 0.3);
            }
            QToolButton:checked {
                background: rgba(76, 175, 80, 0.2);
                border: 2px solid #4CAF50;
            }
        """)
        
        return button
    
    def _create_custom_button(self) -> QToolButton:
        """Create custom aspect ratio button."""
        button = QToolButton()
        button.setCheckable(True)
        button.setToolTip("Custom aspect ratio\nClick to enter a custom value")
        button.setMinimumSize(55, 55)
        button.setMaximumSize(60, 60)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Create pixmap with "Custom" text
        pixmap = QPixmap(55, 45)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        
        # Draw custom icon
        rect_color = QColor("#FF9800")  # Orange for custom
        painter.fillRect(10, 10, 35, 20, rect_color)
        
        # Draw text
        painter.setPen(Qt.black)
        font = QFont()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        # Draw white background for text
        text = "Custom"
        text_rect = painter.fontMetrics().boundingRect(text)
        text_x = (55 - text_rect.width()) // 2
        text_y = 45 - 10
        painter.fillRect(text_x - 2, text_y - 2, text_rect.width() + 4, 12, QColor(255, 255, 255, 200))
        painter.drawText(pixmap.rect(), Qt.AlignBottom | Qt.AlignHCenter, text)
        painter.end()
        
        button.setIcon(pixmap)
        button.setIconSize(QSize(55, 45))
        button.clicked.connect(self._on_custom_clicked)
        
        # Same style as other buttons
        button.setStyleSheet("""
            QToolButton {
                border: 2px solid transparent;
                border-radius: 4px;
                background: rgba(0, 0, 0, 0.02);
            }
            QToolButton:hover {
                background: rgba(255, 152, 0, 0.1);
                border: 2px solid rgba(255, 152, 0, 0.3);
            }
            QToolButton:checked {
                background: rgba(255, 152, 0, 0.2);
                border: 2px solid #FF9800;
            }
        """)
        
        return button
    
    def _on_ratio_clicked(self, ratio: str):
        """Handle ratio button click."""
        # Hide custom input when selecting preset
        self._show_custom_input(False)
        self._using_custom = False
        self.custom_button.setChecked(False)
        self.set_ratio(ratio)
        self.ratioChanged.emit(ratio)
    
    def _on_custom_clicked(self):
        """Handle custom button click."""
        if self.custom_button.isChecked():
            # Show custom input
            self._show_custom_input(True)
            self._using_custom = True
            # Uncheck all preset buttons
            for button in self.buttons.values():
                button.setChecked(False)
            # Set focus to input
            self.custom_input.setFocus()
        else:
            # Hide custom input and select default
            self._show_custom_input(False)
            self._using_custom = False
            self.set_ratio("1:1")
            self.ratioChanged.emit("1:1")
    
    def _show_custom_input(self, show: bool):
        """Show or hide custom input controls."""
        self.custom_label.setVisible(show)
        self.custom_input.setVisible(show)
        self.apply_button.setVisible(show)
    
    def _on_custom_input_changed(self):
        """Handle custom input text change."""
        # Enable apply button when text changes
        text = self.custom_input.text().strip()
        self.apply_button.setEnabled(bool(text))
    
    def _apply_custom_ratio(self):
        """Apply the custom aspect ratio."""
        text = self.custom_input.text().strip()
        if not text:
            return
        
        # Parse the input - could be "16:9" or "1.78"
        if ':' in text:
            # Format: W:H
            parts = text.split(':')
            if len(parts) == 2:
                try:
                    w = float(parts[0])
                    h = float(parts[1])
                    if h > 0:
                        # Normalize to W:H format
                        ratio = f"{w:.1f}:{h:.1f}".replace('.0:', ':').replace('.0', '')
                        self.current_ratio = ratio
                        self._using_custom = True
                        self.ratioChanged.emit(ratio)
                except ValueError:
                    pass
        else:
            # Format: decimal (e.g., 1.78)
            try:
                decimal = float(text)
                if decimal > 0:
                    # Convert to W:H format (normalize to height of 1)
                    ratio = f"{decimal:.2f}:1"
                    self.current_ratio = ratio
                    self._using_custom = True
                    self.ratioChanged.emit(ratio)
            except ValueError:
                pass
    
    def set_ratio(self, ratio: str):
        """Set the current aspect ratio."""
        self.current_ratio = ratio
        
        # Check if it's a preset ratio
        if ratio in self.buttons:
            for r, button in self.buttons.items():
                button.setChecked(r == ratio)
            self.custom_button.setChecked(False)
            self._show_custom_input(False)
            self._using_custom = False
        else:
            # It's a custom ratio
            for button in self.buttons.values():
                button.setChecked(False)
            self.custom_button.setChecked(True)
            self._show_custom_input(True)
            self._using_custom = True
            self.custom_input.setText(ratio)
    
    def get_ratio(self) -> str:
        """Get the current aspect ratio."""
        return self.current_ratio
    
    def is_using_custom(self) -> bool:
        """Check if using custom aspect ratio."""
        return self._using_custom


class ResolutionSelector(QWidget):
    """Smart resolution selector with presets and AR/resolution mode indicator."""
    
    resolutionChanged = Signal(str)
    modeChanged = Signal(str)  # "resolution" or "aspect_ratio"
    
    PRESETS = {
        "google": {
            "Auto (from AR)": "auto",
            "1K (1024×1024)": "1024x1024",
            "2K (2048×2048)": "2048x2048",
        },
        "openai": {
            "Auto (from AR)": "auto",
            "Square (1024×1024)": "1024x1024",
            "Portrait (1024×1792)": "1024x1792",
            "Landscape (1792×1024)": "1792x1024",
        },
        "stability": {
            "Auto (from AR)": "auto",
            "SD 1.5 (512×512)": "512x512",
            "SD 1.5 HD (768×768)": "768x768",
            "SDXL (1024×1024)": "1024x1024",
            "SDXL Wide (1152×896)": "1152x896",
            "SDXL Tall (896×1152)": "896x1152",
            "SDXL Cinema (1536×640)": "1536x640",
        }
    }
    
    def __init__(self, provider: str = "google", parent=None):
        super().__init__(parent)
        self.provider = provider
        self._using_aspect_ratio = True
        self._aspect_ratio = "1:1"
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Mode indicator
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(5)
        
        self.mode_label = QLabel("Mode:")
        mode_layout.addWidget(self.mode_label)
        
        self.mode_indicator = QLabel("Using Aspect Ratio")
        self.mode_indicator.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-weight: bold;
                padding: 2px 6px;
                border: 1px solid #4CAF50;
                border-radius: 3px;
                background: rgba(76, 175, 80, 0.1);
            }
        """)
        mode_layout.addWidget(self.mode_indicator)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        # Resolution combo
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self._on_resolution_changed)
        layout.addWidget(self.combo)
        
        # Info label
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.info_label)
        
        self.update_provider(self.provider)
    
    def update_provider(self, provider: str):
        """Update options based on provider."""
        self.provider = provider
        self.combo.clear()
        
        presets = self.PRESETS.get(provider, self.PRESETS["google"])
        for label, resolution in presets.items():
            self.combo.addItem(label, resolution)
        
        # Set default to Auto
        self.combo.setCurrentIndex(0)
        
        # Update info
        self._update_info_text()
    
    def _update_info_text(self):
        """Update the info label based on current state."""
        if self._using_aspect_ratio:
            self.info_label.setText(f"Resolution calculated from aspect ratio: {self._aspect_ratio}")
        else:
            if self.provider == "google":
                self.info_label.setText("Using manual resolution (overrides aspect ratio)")
            elif self.provider == "openai":
                self.info_label.setText("Using manual resolution (may affect generation style)")
            elif self.provider == "stability":
                self.info_label.setText("Using manual resolution (model-specific optimal)")
            else:
                self.info_label.setText("Using manual resolution")
    
    def _on_resolution_changed(self, text: str):
        """Handle resolution change."""
        resolution = self.combo.currentData()
        if resolution:
            if resolution == "auto":
                # Switch to aspect ratio mode
                self.set_mode_aspect_ratio()
            else:
                # Switch to resolution mode
                self.set_mode_resolution()
                self.resolutionChanged.emit(resolution)
    
    def set_mode_aspect_ratio(self):
        """Set mode to use aspect ratio."""
        self._using_aspect_ratio = True
        self.mode_indicator.setText("Using Aspect Ratio")
        self.mode_indicator.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-weight: bold;
                padding: 2px 6px;
                border: 1px solid #4CAF50;
                border-radius: 3px;
                background: rgba(76, 175, 80, 0.1);
            }
        """)
        self._update_info_text()
        self.modeChanged.emit("aspect_ratio")
        
        # Set combo to Auto if not already
        if self.combo.currentData() != "auto":
            self.combo.setCurrentIndex(0)
    
    def set_mode_resolution(self):
        """Set mode to use explicit resolution."""
        self._using_aspect_ratio = False
        self.mode_indicator.setText("Using Resolution")
        self.mode_indicator.setStyleSheet("""
            QLabel {
                color: #2196F3;
                font-weight: bold;
                padding: 2px 6px;
                border: 1px solid #2196F3;
                border-radius: 3px;
                background: rgba(33, 150, 243, 0.1);
            }
        """)
        self._update_info_text()
        self.modeChanged.emit("resolution")
    
    def update_aspect_ratio(self, ratio: str):
        """Update the current aspect ratio (for display)."""
        self._aspect_ratio = ratio
        if self._using_aspect_ratio:
            self._update_info_text()
            # Calculate suggested resolution based on aspect ratio
            self._update_suggested_resolution(ratio)
    
    def _update_suggested_resolution(self, ratio: str):
        """Update the combo text to show suggested resolution from AR."""
        if self._using_aspect_ratio and self.combo.currentData() == "auto":
            # Calculate resolution based on aspect ratio and provider
            suggested = self._calculate_resolution_from_ar(ratio)
            # Update the Auto item text to show the calculated resolution
            self.combo.setItemText(0, f"Auto ({suggested})")
    
    def _calculate_resolution_from_ar(self, ratio: str) -> str:
        """Calculate resolution from aspect ratio based on provider."""
        # Parse aspect ratio
        if ':' in ratio:
            parts = ratio.split(':')
            try:
                w = float(parts[0])
                h = float(parts[1])
                ar = w / h
            except (ValueError, IndexError):
                ar = 1.0
        else:
            ar = 1.0
        
        # Calculate based on provider
        if self.provider == "openai":
            if ar > 1.3:  # Landscape
                return "1792×1024"
            elif ar < 0.77:  # Portrait
                return "1024×1792"
            else:  # Square-ish
                return "1024×1024"
        elif self.provider == "google":
            # Google only supports square for now
            return "1024×1024"
        else:  # stability and others
            if ar > 1.3:  # Landscape
                return "1152×896"
            elif ar < 0.77:  # Portrait
                return "896×1152"
            else:  # Square-ish
                return "1024×1024"
    
    def get_resolution(self) -> str:
        """Get current resolution."""
        if self._using_aspect_ratio:
            # Calculate from aspect ratio
            return self._calculate_resolution_from_ar(self._aspect_ratio).replace('×', 'x')
        else:
            return self.combo.currentData() or "1024x1024"
    
    def set_resolution(self, resolution: str):
        """Set resolution."""
        if resolution == "auto":
            self.set_mode_aspect_ratio()
        else:
            for i in range(self.combo.count()):
                if self.combo.itemData(i) == resolution:
                    self.combo.setCurrentIndex(i)
                    self.set_mode_resolution()
                    break
    
    def is_using_aspect_ratio(self) -> bool:
        """Check if using aspect ratio mode."""
        return self._using_aspect_ratio


class QualitySelector(QWidget):
    """Quality and style selector for providers."""
    
    settingsChanged = Signal(dict)
    
    def __init__(self, provider: str = "google", parent=None):
        super().__init__(parent)
        self.provider = provider
        self.settings = {}
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Quality group
        self.quality_group = QGroupBox("Quality")
        quality_layout = QHBoxLayout(self.quality_group)
        
        self.quality_buttons = QButtonGroup()
        self.standard_radio = QRadioButton("Standard")
        self.hd_radio = QRadioButton("HD/High")
        
        self.quality_buttons.addButton(self.standard_radio, 0)
        self.quality_buttons.addButton(self.hd_radio, 1)
        quality_layout.addWidget(self.standard_radio)
        quality_layout.addWidget(self.hd_radio)
        
        self.standard_radio.setChecked(True)
        self.quality_buttons.buttonClicked.connect(self._on_quality_changed)
        
        layout.addWidget(self.quality_group)
        
        # Style group (OpenAI)
        self.style_group = QGroupBox("Style")
        style_layout = QHBoxLayout(self.style_group)
        
        self.style_buttons = QButtonGroup()
        self.vivid_radio = QRadioButton("Vivid")
        self.vivid_radio.setToolTip("Hyper-real and cinematic")
        self.natural_radio = QRadioButton("Natural")
        self.natural_radio.setToolTip("More realistic and subtle")
        
        self.style_buttons.addButton(self.vivid_radio, 0)
        self.style_buttons.addButton(self.natural_radio, 1)
        style_layout.addWidget(self.vivid_radio)
        style_layout.addWidget(self.natural_radio)
        
        self.vivid_radio.setChecked(True)
        self.style_buttons.buttonClicked.connect(self._on_style_changed)
        
        layout.addWidget(self.style_group)
        
        self.update_provider(self.provider)
    
    def update_provider(self, provider: str):
        """Update visibility based on provider."""
        self.provider = provider
        
        if provider == "openai":
            self.quality_group.setVisible(True)
            self.style_group.setVisible(True)
            self.quality_group.setTitle("Quality")
            self.standard_radio.setText("Standard ($0.04)")
            self.hd_radio.setText("HD ($0.08)")
        elif provider == "google":
            self.quality_group.setVisible(True)
            self.style_group.setVisible(False)
            self.quality_group.setTitle("Model Quality")
            self.standard_radio.setText("Fast")
            self.hd_radio.setText("Quality")
        else:
            self.quality_group.setVisible(False)
            self.style_group.setVisible(False)
    
    def _on_quality_changed(self):
        """Handle quality change."""
        quality = "hd" if self.hd_radio.isChecked() else "standard"
        self.settings["quality"] = quality
        self.settingsChanged.emit(self.settings)
    
    def _on_style_changed(self):
        """Handle style change."""
        style = "natural" if self.natural_radio.isChecked() else "vivid"
        self.settings["style"] = style
        self.settingsChanged.emit(self.settings)
    
    def get_settings(self) -> dict:
        """Get current settings."""
        settings = {}
        # Always save quality setting if the group exists
        if hasattr(self, 'quality_group'):
            settings["quality"] = "hd" if self.hd_radio.isChecked() else "standard"
        # Always save style setting if the group exists
        if hasattr(self, 'style_group'):
            settings["style"] = "natural" if self.natural_radio.isChecked() else "vivid"
        return settings
    
    def set_settings(self, settings: dict):
        """Restore settings."""
        if "quality" in settings:
            if settings["quality"] == "hd":
                self.hd_radio.setChecked(True)
            else:
                self.standard_radio.setChecked(True)
        
        if "style" in settings:
            if settings["style"] == "vivid":
                self.vivid_radio.setChecked(True)
            else:
                self.natural_radio.setChecked(True)


class BatchSelector(QWidget):
    """Batch generation selector with cost estimate."""
    
    batchChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_images = 1
        self.cost_per_image = 0.04
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Images:"))
        
        self.spin = QSpinBox()
        self.spin.setRange(1, 4)
        self.spin.setValue(1)
        self.spin.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.spin)
        
        self.cost_label = QLabel()
        self.cost_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.cost_label)
        
        layout.addStretch()
        
        self._update_cost()
    
    def _on_value_changed(self, value: int):
        """Handle value change."""
        self.num_images = value
        self._update_cost()
        self.batchChanged.emit(value)
    
    def _update_cost(self):
        """Update cost display."""
        total = self.num_images * self.cost_per_image
        if self.num_images > 1:
            self.cost_label.setText(f"≈ ${total:.2f} ({self.num_images} × ${self.cost_per_image:.2f})")
        else:
            self.cost_label.setText(f"≈ ${total:.2f}")
    
    def set_cost_per_image(self, cost: float):
        """Set cost per image."""
        self.cost_per_image = cost
        self._update_cost()
    
    def get_num_images(self) -> int:
        """Get number of images."""
        return self.num_images


class AdvancedSettingsPanel(QWidget):
    """Collapsible panel for advanced settings."""
    
    settingsChanged = Signal(dict)
    
    def __init__(self, provider: str = "google", parent=None):
        super().__init__(parent)
        self.provider = provider
        self.settings = {}
        self.expanded = False
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toggle button
        self.toggle_btn = QPushButton("▶ Advanced Settings")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self._toggle_expanded)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        layout.addWidget(self.toggle_btn)
        
        # Container for advanced settings
        self.container = QWidget()
        self.container.setVisible(False)
        container_layout = QVBoxLayout(self.container)
        
        # Provider-specific settings
        self.google_settings = self._create_google_settings()
        self.openai_settings = self._create_openai_settings()
        self.stability_settings = self._create_stability_settings()
        
        container_layout.addWidget(self.google_settings)
        container_layout.addWidget(self.openai_settings)
        container_layout.addWidget(self.stability_settings)
        
        layout.addWidget(self.container)
        
        self.update_provider(self.provider)
    
    def _create_google_settings(self) -> QWidget:
        """Create Google-specific advanced settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Prompt rewriting
        self.prompt_rewrite_check = QCheckBox("Enable prompt rewriting (AI enhancement)")
        self.prompt_rewrite_check.setChecked(True)
        self.prompt_rewrite_check.toggled.connect(
            lambda v: self._update_setting("enable_prompt_rewriting", v)
        )
        layout.addWidget(self.prompt_rewrite_check)
        
        # Safety filter
        safety_layout = QHBoxLayout()
        safety_layout.addWidget(QLabel("Safety filter:"))
        self.safety_combo = QComboBox()
        self.safety_combo.addItems(["Block most", "Block some", "Block few", "Block fewest"])
        self.safety_combo.setCurrentIndex(1)
        self.safety_combo.currentTextChanged.connect(
            lambda v: self._update_setting("safety_filter", v.lower().replace(" ", "_"))
        )
        safety_layout.addWidget(self.safety_combo)
        safety_layout.addStretch()
        layout.addLayout(safety_layout)
        
        # Person generation
        self.person_gen_check = QCheckBox("Allow person generation")
        self.person_gen_check.setChecked(True)
        self.person_gen_check.toggled.connect(
            lambda v: self._update_setting("person_generation", v)
        )
        layout.addWidget(self.person_gen_check)
        
        # Seed
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 2147483647)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.setToolTip("Use -1 for random, or set a specific seed for reproducible results")
        self.seed_spin.valueChanged.connect(
            lambda v: self._update_setting("seed", None if v == -1 else v)
        )
        seed_layout.addWidget(self.seed_spin)
        seed_layout.addStretch()
        layout.addLayout(seed_layout)
        
        return widget
    
    def _create_openai_settings(self) -> QWidget:
        """Create OpenAI-specific advanced settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Response format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Response format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["URL", "Base64 JSON"])
        self.format_combo.currentTextChanged.connect(
            lambda v: self._update_setting("response_format", v.lower().replace(" ", "_"))
        )
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        return widget
    
    def _create_stability_settings(self) -> QWidget:
        """Create Stability-specific advanced settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # CFG Scale
        cfg_layout = QHBoxLayout()
        cfg_layout.addWidget(QLabel("CFG Scale:"))
        self.cfg_slider = QSlider(Qt.Horizontal)
        self.cfg_slider.setRange(10, 150)  # 1.0 to 15.0
        self.cfg_slider.setValue(70)  # 7.0
        self.cfg_slider.setTickInterval(10)
        self.cfg_slider.setTickPosition(QSlider.TicksBelow)
        self.cfg_label = QLabel("7.0")
        self.cfg_slider.valueChanged.connect(self._on_cfg_changed)
        cfg_layout.addWidget(self.cfg_slider)
        cfg_layout.addWidget(self.cfg_label)
        layout.addLayout(cfg_layout)
        
        # Steps
        steps_layout = QHBoxLayout()
        steps_layout.addWidget(QLabel("Steps:"))
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(20, 150)
        self.steps_spin.setValue(50)
        self.steps_spin.valueChanged.connect(
            lambda v: self._update_setting("steps", v)
        )
        steps_layout.addWidget(self.steps_spin)
        steps_layout.addStretch()
        layout.addLayout(steps_layout)
        
        return widget
    
    def _on_cfg_changed(self, value: int):
        """Handle CFG scale change."""
        cfg = value / 10.0
        self.cfg_label.setText(f"{cfg:.1f}")
        self._update_setting("cfg_scale", cfg)
    
    def _toggle_expanded(self):
        """Toggle expanded state."""
        self.expanded = not self.expanded
        self.container.setVisible(self.expanded)
        self.toggle_btn.setText("▼ Advanced Settings" if self.expanded else "▶ Advanced Settings")
    
    def _update_setting(self, key: str, value: Any):
        """Update a setting."""
        self.settings[key] = value
        self.settingsChanged.emit(self.settings)
    
    def update_provider(self, provider: str):
        """Update visibility based on provider."""
        self.provider = provider
        self.google_settings.setVisible(provider == "google")
        self.openai_settings.setVisible(provider == "openai")
        self.stability_settings.setVisible(provider == "stability")
    
    def get_settings(self) -> dict:
        """Get current settings."""
        # Always include the current state of all controls
        current_settings = {}
        
        # Google settings
        if hasattr(self, 'prompt_rewrite_check'):
            current_settings['enable_prompt_rewriting'] = self.prompt_rewrite_check.isChecked()
        
        if hasattr(self, 'safety_combo'):
            current_settings['safety_filter'] = self.safety_combo.currentText()
        
        # OpenAI settings
        if hasattr(self, 'openai_hd_check'):
            current_settings['openai_quality'] = 'hd' if self.openai_hd_check.isChecked() else 'standard'
        
        if hasattr(self, 'openai_vivid_radio'):
            current_settings['openai_style'] = 'vivid' if self.openai_vivid_radio.isChecked() else 'natural'
        
        # Stability settings
        if hasattr(self, 'seed_spin'):
            current_settings['seed'] = self.seed_spin.value()
        
        if hasattr(self, 'cfg_spin'):
            current_settings['cfg_scale'] = self.cfg_spin.value()
        
        if hasattr(self, 'steps_spin'):
            current_settings['steps'] = self.steps_spin.value()
        
        # Merge with any existing settings that might have been set
        return {**self.settings, **current_settings}
    
    def set_settings(self, settings: dict):
        """Restore settings."""
        self.settings = settings.copy()
        
        # Update Google settings
        if "enable_prompt_rewriting" in settings:
            self.prompt_rewrite_check.setChecked(settings["enable_prompt_rewriting"])
        
        if "safety_filter" in settings:
            idx = self.safety_combo.findText(settings["safety_filter"])
            if idx >= 0:
                self.safety_combo.setCurrentIndex(idx)
        
        # Update OpenAI settings
        if "openai_quality" in settings:
            if settings["openai_quality"] == "hd":
                self.openai_hd_check.setChecked(True)
        
        if "openai_style" in settings:
            if settings["openai_style"] == "vivid":
                self.openai_vivid_radio.setChecked(True)
            else:
                self.openai_natural_radio.setChecked(True)
        
        # Update Stability settings
        if "seed" in settings:
            self.seed_spin.setValue(settings["seed"])
        
        if "cfg_scale" in settings:
            self.cfg_spin.setValue(settings["cfg_scale"])
        
        if "steps" in settings:
            self.steps_spin.setValue(settings["steps"])


class CostEstimator:
    """Calculate and display generation costs."""
    
    PRICING = {
        "google": {
            "standard": 0.03,
            "2k": 0.06,
            "fast": 0.02
        },
        "openai": {
            "standard": 0.04,
            "hd": 0.08
        },
        "stability": {
            "sdxl": 0.011,
            "sd3": 0.037,
            "sd15": 0.006
        }
    }
    
    @classmethod
    def calculate(cls, provider: str, settings: dict) -> float:
        """Calculate cost based on provider and settings."""
        if provider not in cls.PRICING:
            return 0.0
        
        pricing = cls.PRICING[provider]
        num_images = settings.get("num_images", 1)
        
        # Provider-specific logic
        if provider == "openai":
            quality = settings.get("quality", "standard")
            price_per_image = pricing.get(quality, pricing["standard"])
        elif provider == "google":
            resolution = settings.get("resolution", "1024x1024")
            if "2048" in resolution:
                price_per_image = pricing["2k"]
            else:
                price_per_image = pricing["standard"]
        else:
            # Default to standard pricing
            price_per_image = pricing.get("standard", 0.01)
        
        return price_per_image * num_images