"""Advanced settings widgets for ImageAI."""

from typing import Dict, Any, Optional, Tuple
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QSlider, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QGroupBox, QButtonGroup,
    QRadioButton, QToolButton, QFrame, QScrollArea,
    QSizePolicy
)


class AspectRatioSelector(QWidget):
    """Visual aspect ratio selector with preview rectangles."""
    
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
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QGridLayout(self)
        layout.setSpacing(5)  # Tighter spacing
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        col = 0
        row = 0
        for ratio, info in self.ASPECT_RATIOS.items():
            button = self._create_ratio_button(ratio, info)
            self.buttons[ratio] = button
            layout.addWidget(button, row, col)
            
            col += 1
            if col > 2:  # 3 columns
                col = 0
                row += 1
        
        # Select default
        self.set_ratio("1:1")
    
    def _create_ratio_button(self, ratio: str, info: dict) -> QToolButton:
        """Create a visual button for aspect ratio selection."""
        button = QToolButton()
        button.setCheckable(True)
        button.setToolTip(f"{info['label']}\n{info['use']}")
        button.setMinimumSize(65, 65)  # Smaller buttons
        button.setMaximumSize(75, 75)  # Constrain max size
        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # Create visual preview
        width, height = map(int, ratio.split(':'))
        max_size = 40  # Smaller preview
        if width > height:
            w = max_size
            h = int(max_size * height / width)
        else:
            h = max_size
            w = int(max_size * width / height)
        
        # Create pixmap with aspect ratio preview
        pixmap = QPixmap(65, 50)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        
        # Draw rectangle
        rect_color = QColor("#4CAF50")
        painter.fillRect((65-w)//2, (50-h)//2 - 5, w, h, rect_color)
        
        # Draw label with dark text on white background for visibility
        painter.setPen(Qt.black)  # Dark text
        font = QFont()
        font.setPixelSize(11)  # Slightly larger font
        font.setBold(True)  # Bold for better visibility
        painter.setFont(font)
        
        # Draw white background for text
        text_rect = painter.fontMetrics().boundingRect(ratio)
        text_x = (65 - text_rect.width()) // 2
        text_y = 50 - 12
        painter.fillRect(text_x - 2, text_y - 2, text_rect.width() + 4, 14, QColor(255, 255, 255, 200))
        
        # Draw the ratio text
        painter.drawText(pixmap.rect(), Qt.AlignBottom | Qt.AlignHCenter, ratio)
        painter.end()
        
        button.setIcon(pixmap)
        button.setIconSize(QSize(65, 50))
        button.clicked.connect(lambda: self._on_ratio_clicked(ratio))
        
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
    
    def _on_ratio_clicked(self, ratio: str):
        """Handle ratio button click."""
        self.set_ratio(ratio)
        self.ratioChanged.emit(ratio)
    
    def set_ratio(self, ratio: str):
        """Set the current aspect ratio."""
        self.current_ratio = ratio
        for r, button in self.buttons.items():
            button.setChecked(r == ratio)
    
    def get_ratio(self) -> str:
        """Get the current aspect ratio."""
        return self.current_ratio


class ResolutionSelector(QWidget):
    """Smart resolution selector with presets."""
    
    resolutionChanged = Signal(str)
    
    PRESETS = {
        "google": {
            "1K (1024×1024)": "1024x1024",
            "2K (2048×2048)": "2048x2048",
        },
        "openai": {
            "Square (1024×1024)": "1024x1024",
            "Portrait (1024×1792)": "1024x1792",
            "Landscape (1792×1024)": "1792x1024",
        },
        "stability": {
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
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        # Update info
        if provider == "google":
            self.info_label.setText("2K only available for Standard/Ultra models")
        elif provider == "openai":
            self.info_label.setText("Different sizes may affect generation style")
        elif provider == "stability":
            self.info_label.setText("Use model-specific optimal resolutions")
        else:
            self.info_label.clear()
    
    def _on_resolution_changed(self, text: str):
        """Handle resolution change."""
        resolution = self.combo.currentData()
        if resolution:
            self.resolutionChanged.emit(resolution)
    
    def get_resolution(self) -> str:
        """Get current resolution."""
        return self.combo.currentData() or "1024x1024"
    
    def set_resolution(self, resolution: str):
        """Set resolution."""
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == resolution:
                self.combo.setCurrentIndex(i)
                break


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
        if self.quality_group.isVisible():
            settings["quality"] = "hd" if self.hd_radio.isChecked() else "standard"
        if self.style_group.isVisible():
            settings["style"] = "natural" if self.natural_radio.isChecked() else "vivid"
        return settings


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
        return self.settings.copy()


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