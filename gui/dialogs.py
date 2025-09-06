"""Dialog windows for ImageAI GUI."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QTabWidget, QWidget, QComboBox, QFormLayout,
    QCheckBox, QPushButton, QLineEdit, QTextEdit
)

from core.constants import GEMINI_TEMPLATES_PATH
from templates import get_gemini_doc_templates


class ExamplesDialog(QDialog):
    """Dialog for selecting example prompts and templates."""
    
    EXAMPLES = [
        "A whimsical city made of candy canes and gumdrops at sunset, ultra-detailed, 8k",
        "A photorealistic glass terrarium containing a micro jungle with tiny glowing fauna",
        "Retro-futuristic poster of a rocket-powered bicycle racing across neon clouds",
        "An isometric diorama of a tiny island with waterfalls flowing into space",
        "Blueprint style render of a mechanical hummingbird with clockwork internals",
        "Studio portrait of a robot chef carefully plating molecular gastronomy",
        "A children's book illustration of a dragon learning to paint with oversized brushes",
        "Macro shot of dew drops forming constellations on a leaf under moonlight",
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Examples & Templates")
        self.resize(620, 440)
        
        self.append_to_prompt: bool = False
        self._last_values: dict[str, dict[str, str]] = {}
        
        v = QVBoxLayout(self)
        
        # Tabs: Examples and Templates
        self.tabs = QTabWidget()
        
        # Examples tab
        tab_examples = QWidget()
        v_ex = QVBoxLayout(tab_examples)
        self.listw = QListWidget()
        for ex in self.EXAMPLES:
            QListWidgetItem(ex, self.listw)
        v_ex.addWidget(QLabel("Choose an example to insert into the prompt:"))
        v_ex.addWidget(self.listw)
        self.tabs.addTab(tab_examples, "Examples")
        
        # Templates tab
        tab_templates = QWidget()
        v_t = QVBoxLayout(tab_templates)
        v_t.addWidget(QLabel("Select a template and fill in any attributes (all optional):"))
        
        # Credits
        try:
            credit = QLabel(
                'Templates inspired by the Gemini Image Generation docs: <br>'
                '<a href="https://ai.google.dev/gemini-api/docs/image-generation">'
                'ai.google.dev/gemini-api/docs/image-generation</a><br/>'
                'I also used this page to help develop the app.'
            )
            credit.setOpenExternalLinks(True)
            credit.setTextFormat(Qt.RichText)
            credit.setWordWrap(True)
            credit.setStyleSheet("color: gray; font-size: 9pt;")
            v_t.addWidget(credit)
        except Exception:
            pass
        
        # Load templates
        try:
            self.TEMPLATES = get_gemini_doc_templates()
        except Exception:
            # Fallback to built-in templates
            self.TEMPLATES = []
        
        self.template_combo = QComboBox()
        self.template_combo.addItems([t["name"] for t in self.TEMPLATES])
        v_t.addWidget(self.template_combo)
        
        # Dynamic form container
        self.template_form = QFormLayout()
        self.template_form_holder = QWidget()
        self.template_form_holder.setLayout(self.template_form)
        v_t.addWidget(self.template_form_holder)
        
        # Signals and initial form build
        self.template_combo.currentIndexChanged.connect(self._rebuild_template_form)
        self._rebuild_template_form()
        
        self.tabs.addTab(tab_templates, "Templates")
        v.addWidget(self.tabs)
        
        # Options
        self.chkAppend = QCheckBox("Append to current prompt instead of replacing")
        v.addWidget(self.chkAppend)
        
        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btnCancel = QPushButton("Cancel")
        self.btnOK = QPushButton("Use Selected")
        btns.addWidget(self.btnCancel)
        btns.addWidget(self.btnOK)
        v.addLayout(btns)
        
        self.btnCancel.clicked.connect(self.reject)
        self.btnOK.clicked.connect(self._on_ok)
        self.listw.itemDoubleClicked.connect(self._on_ok)
    
    def _rebuild_template_form(self):
        """Rebuild the template form for the selected template."""
        # Clear existing form
        while self.template_form.count():
            item = self.template_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        idx = self.template_combo.currentIndex()
        if idx < 0 or idx >= len(self.TEMPLATES):
            return
        
        template_data = self.TEMPLATES[idx]
        template_name = template_data["name"]
        defaults = template_data.get("defaults", {})
        
        # Extract placeholders from template
        template_str = template_data.get("template", "")
        import re
        placeholders = re.findall(r'\[([^\]]+)\]', template_str)
        
        # Create form fields for each placeholder
        self.template_fields = {}
        for placeholder in placeholders:
            edit = QLineEdit()
            
            # Set default value if available
            if placeholder in defaults:
                edit.setText(defaults[placeholder])
            
            # Restore last value if available
            if template_name in self._last_values:
                if placeholder in self._last_values[template_name]:
                    edit.setText(self._last_values[template_name][placeholder])
            
            # Show default value as tooltip
            if placeholder in defaults:
                edit.setToolTip(f"Default: {defaults[placeholder]}")
            
            self.template_form.addRow(f"{placeholder}:", edit)
            self.template_fields[placeholder] = edit
    
    def _on_ok(self):
        """Handle OK button click."""
        self.append_to_prompt = self.chkAppend.isChecked()
        self.accept()
    
    def get_selected_prompt(self) -> Optional[str]:
        """Get the selected prompt based on current tab."""
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0:  # Examples tab
            item = self.listw.currentItem()
            if item:
                return item.text()
        elif current_tab == 1:  # Templates tab
            idx = self.template_combo.currentIndex()
            if idx >= 0 and idx < len(self.TEMPLATES):
                template_data = self.TEMPLATES[idx]
                template_name = template_data["name"]
                template_str = template_data.get("template", "")
                defaults = template_data.get("defaults", {})
                
                # Save current values
                if template_name not in self._last_values:
                    self._last_values[template_name] = {}
                
                # Apply substitutions
                result = template_str
                for placeholder, field in self.template_fields.items():
                    value = field.text().strip()
                    self._last_values[template_name][placeholder] = value
                    
                    if not value and placeholder in defaults:
                        value = defaults[placeholder]
                    
                    if value:
                        result = result.replace(f"[{placeholder}]", value)
                
                return result
        
        return None