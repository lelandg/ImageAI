"""
Batch Mode Widget for Async Image Generation.

Provides UI for queueing prompts and submitting batch jobs
to Google Gemini API with 50% discount.
"""

import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QGroupBox,
    QProgressBar, QMessageBox, QFileDialog, QSpinBox,
    QCheckBox, QSplitter, QFrame
)

from core.batch_manager import BatchRequest, BatchJob, BatchJobState, get_batch_manager

logger = logging.getLogger(__name__)


class BatchModeWidget(QWidget):
    """
    Widget for managing batch image generation.

    Allows users to queue multiple prompts and submit them as a batch job
    for 50% discount on async processing.
    """

    # Signals
    batch_started = Signal(str)  # job_id
    batch_completed = Signal(str, list)  # job_id, image_bytes_list
    batch_failed = Signal(str, str)  # job_id, error

    def __init__(self, parent=None):
        """Initialize the batch mode widget."""
        super().__init__(parent)
        self.queued_prompts: List[str] = []
        self.current_model = "gemini-2.5-flash-image"
        self.current_aspect_ratio = "1:1"
        self.current_quality = "2k"  # For NBP
        self.active_jobs: List[BatchJob] = []

        # Timer for polling job status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._poll_job_status)

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header with info
        header = QLabel(
            "<b>Batch Mode</b> - Queue prompts for 50% discount<br>"
            "<small>Jobs process asynchronously, typically completing within a few hours.</small>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Splitter: Queue on left, Jobs on right
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Prompt queue
        queue_frame = QFrame()
        queue_layout = QVBoxLayout(queue_frame)

        queue_layout.addWidget(QLabel("<b>Prompt Queue:</b>"))

        self.queue_list = QListWidget()
        self.queue_list.setToolTip("Queued prompts for batch processing")
        queue_layout.addWidget(self.queue_list)

        # Queue controls
        queue_controls = QHBoxLayout()

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        queue_controls.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_queue)
        queue_controls.addWidget(self.clear_btn)

        queue_layout.addLayout(queue_controls)

        # Import/Export
        file_controls = QHBoxLayout()

        self.import_btn = QPushButton("Import from File")
        self.import_btn.setToolTip("Import prompts from a text file (one per line)")
        self.import_btn.clicked.connect(self._import_prompts)
        file_controls.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export to File")
        self.export_btn.setToolTip("Export queued prompts to a text file")
        self.export_btn.clicked.connect(self._export_prompts)
        file_controls.addWidget(self.export_btn)

        queue_layout.addLayout(file_controls)

        splitter.addWidget(queue_frame)

        # Right side: Active jobs
        jobs_frame = QFrame()
        jobs_layout = QVBoxLayout(jobs_frame)

        jobs_layout.addWidget(QLabel("<b>Active Jobs:</b>"))

        self.jobs_list = QListWidget()
        self.jobs_list.setToolTip("Running and completed batch jobs")
        jobs_layout.addWidget(self.jobs_list)

        # Job controls
        job_controls = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self._refresh_all_jobs)
        job_controls.addWidget(self.refresh_btn)

        self.download_btn = QPushButton("Download Results")
        self.download_btn.clicked.connect(self._download_results)
        job_controls.addWidget(self.download_btn)

        jobs_layout.addLayout(job_controls)

        splitter.addWidget(jobs_frame)
        splitter.setSizes([500, 500])

        layout.addWidget(splitter)

        # Submit controls
        submit_group = QGroupBox("Submit Batch Job")
        submit_layout = QVBoxLayout(submit_group)

        # Options row
        options_layout = QHBoxLayout()

        options_layout.addWidget(QLabel("Batch Size:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)
        self.batch_size_spin.setValue(10)
        self.batch_size_spin.setToolTip("Maximum prompts per batch job")
        options_layout.addWidget(self.batch_size_spin)

        options_layout.addStretch()

        # Cost estimate
        self.cost_label = QLabel("Est. Cost: $0.00")
        self.cost_label.setToolTip("Estimated cost with 50% batch discount")
        options_layout.addWidget(self.cost_label)

        submit_layout.addLayout(options_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        submit_layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("Ready to submit batch jobs")
        self.status_label.setStyleSheet("color: #666;")
        submit_layout.addWidget(self.status_label)

        # Submit button
        button_layout = QHBoxLayout()

        self.submit_btn = QPushButton("Submit Batch Job")
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.submit_btn.clicked.connect(self._submit_batch)
        button_layout.addWidget(self.submit_btn)

        submit_layout.addLayout(button_layout)

        layout.addWidget(submit_group)

        self._update_ui()

    def add_prompt(self, prompt: str):
        """
        Add a prompt to the queue.

        Args:
            prompt: The prompt text to queue
        """
        if prompt and prompt.strip():
            self.queued_prompts.append(prompt.strip())
            self.queue_list.addItem(prompt.strip()[:100] + "..." if len(prompt) > 100 else prompt.strip())
            self._update_ui()
            logger.info(f"Added prompt to batch queue (total: {len(self.queued_prompts)})")

    def set_model(self, model: str):
        """Set the model to use for batch jobs."""
        self.current_model = model
        self._update_ui()

    def set_aspect_ratio(self, aspect_ratio: str):
        """Set the aspect ratio for batch jobs."""
        self.current_aspect_ratio = aspect_ratio

    def set_quality(self, quality: str):
        """Set the quality tier for NBP models."""
        self.current_quality = quality
        self._update_ui()

    def _update_ui(self):
        """Update UI state based on queue and jobs."""
        count = len(self.queued_prompts)
        self.submit_btn.setEnabled(count > 0)
        self.remove_btn.setEnabled(count > 0)
        self.clear_btn.setEnabled(count > 0)
        self.export_btn.setEnabled(count > 0)

        # Update cost estimate
        cost = self._estimate_cost()
        self.cost_label.setText(f"Est. Cost: ${cost:.2f} (50% off)")

    def _estimate_cost(self) -> float:
        """Estimate batch job cost with 50% discount."""
        count = len(self.queued_prompts)
        if count == 0:
            return 0.0

        # Base pricing (pre-discount)
        is_nbp = "gemini-3" in self.current_model
        if is_nbp:
            if self.current_quality == "4k":
                base_cost = 0.24
            else:
                base_cost = 0.134
        else:
            base_cost = 0.039  # Standard Nano Banana

        # 50% batch discount
        return count * base_cost * 0.5

    def _remove_selected(self):
        """Remove selected items from the queue."""
        selected = self.queue_list.selectedItems()
        for item in selected:
            row = self.queue_list.row(item)
            self.queue_list.takeItem(row)
            if row < len(self.queued_prompts):
                self.queued_prompts.pop(row)
        self._update_ui()

    def _clear_queue(self):
        """Clear all queued prompts."""
        if self.queued_prompts:
            reply = QMessageBox.question(
                self, "Clear Queue",
                f"Remove all {len(self.queued_prompts)} queued prompts?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.queued_prompts.clear()
                self.queue_list.clear()
                self._update_ui()

    def _import_prompts(self):
        """Import prompts from a text file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Prompts", "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.add_prompt(line)
                self.status_label.setText(f"Imported prompts from {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to import: {e}")

    def _export_prompts(self):
        """Export queued prompts to a text file."""
        if not self.queued_prompts:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Prompts", "batch_prompts.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for prompt in self.queued_prompts:
                        f.write(prompt + '\n')
                self.status_label.setText(f"Exported to {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export: {e}")

    def _submit_batch(self):
        """Submit the queued prompts as a batch job."""
        if not self.queued_prompts:
            return

        # Create batch requests
        requests = []
        for i, prompt in enumerate(self.queued_prompts):
            req = BatchRequest(
                key=f"img_{i:04d}",
                prompt=prompt,
                model=self.current_model,
                aspect_ratio=self.current_aspect_ratio,
                output_quality=self.current_quality
            )
            requests.append(req)

        try:
            # Get batch manager
            batch_manager = get_batch_manager()

            # Create job
            self.status_label.setText("Submitting batch job...")
            self.submit_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate

            display_name = f"ImageAI-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            job = batch_manager.create_batch_job(
                requests=requests,
                model=self.current_model,
                display_name=display_name
            )

            # Track job
            self.active_jobs.append(job)
            self._add_job_to_list(job)

            # Clear queue
            self.queued_prompts.clear()
            self.queue_list.clear()

            # Start polling
            if not self.status_timer.isActive():
                self.status_timer.start(30000)  # Poll every 30 seconds

            self.status_label.setText(f"Submitted job: {job.display_name}")
            self.batch_started.emit(job.job_id)

        except Exception as e:
            logger.error(f"Failed to submit batch job: {e}", exc_info=True)
            QMessageBox.critical(self, "Submission Failed", f"Failed to submit batch: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")

        finally:
            self.submit_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self._update_ui()

    def _add_job_to_list(self, job: BatchJob):
        """Add a job to the jobs list."""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, job.job_id)
        self._update_job_item(item, job)
        self.jobs_list.addItem(item)

    def _update_job_item(self, item: QListWidgetItem, job: BatchJob):
        """Update job item display."""
        status_icons = {
            BatchJobState.PENDING: "⏳",
            BatchJobState.RUNNING: "🔄",
            BatchJobState.SUCCEEDED: "✅",
            BatchJobState.FAILED: "❌",
            BatchJobState.CANCELLED: "⛔",
            BatchJobState.EXPIRED: "⌛",
            BatchJobState.UNKNOWN: "❓"
        }
        icon = status_icons.get(job.state, "❓")
        text = f"{icon} {job.display_name} ({job.request_count} images)"
        item.setText(text)

    def _poll_job_status(self):
        """Poll status of active jobs."""
        batch_manager = get_batch_manager()
        completed = []

        for job in self.active_jobs:
            if not job.is_complete:
                try:
                    updated_job = batch_manager.get_job_status(job.job_id)

                    # Update list item
                    for i in range(self.jobs_list.count()):
                        item = self.jobs_list.item(i)
                        if item.data(Qt.UserRole) == job.job_id:
                            self._update_job_item(item, updated_job)
                            break

                    if updated_job.is_complete:
                        completed.append(updated_job)

                except Exception as e:
                    logger.error(f"Failed to poll job {job.job_id}: {e}")

        # Handle completed jobs
        for job in completed:
            self.active_jobs.remove(job)

            if job.state == BatchJobState.SUCCEEDED:
                self.status_label.setText(f"Job completed: {job.display_name}")
                self.batch_completed.emit(job.job_id, [])  # Results downloaded separately
            else:
                self.status_label.setText(f"Job failed: {job.display_name}")
                self.batch_failed.emit(job.job_id, job.error or "Unknown error")

        # Stop timer if no active jobs
        if not any(not j.is_complete for j in self.active_jobs):
            self.status_timer.stop()

    def _refresh_all_jobs(self):
        """Manually refresh all job statuses."""
        self._poll_job_status()
        self.status_label.setText("Refreshed job statuses")

    def _download_results(self):
        """Download results from selected completed job."""
        selected = self.jobs_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a completed job to download.")
            return

        job_id = selected[0].data(Qt.UserRole)

        try:
            batch_manager = get_batch_manager()
            images, errors = batch_manager.get_job_results(job_id)

            if images:
                # Get save directory
                dir_path = QFileDialog.getExistingDirectory(
                    self, "Select Output Directory"
                )
                if dir_path:
                    output_dir = Path(dir_path)
                    for i, img_bytes in enumerate(images):
                        output_path = output_dir / f"batch_{job_id}_{i:04d}.png"
                        output_path.write_bytes(img_bytes)

                    self.status_label.setText(f"Downloaded {len(images)} images")
                    QMessageBox.information(
                        self, "Download Complete",
                        f"Downloaded {len(images)} images to {dir_path}"
                    )

            if errors:
                logger.warning(f"Batch job had errors: {errors}")

        except Exception as e:
            QMessageBox.critical(self, "Download Failed", f"Failed to download: {e}")
