import cv2
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QListWidget, QLabel, QLineEdit, QSlider, QDoubleSpinBox, QMessageBox,
    QComboBox, QSplitter, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from src.processor import process_shot

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBS Shot Extractor")
        self.resize(1100, 750)

        self.videos = []
        self.shots = []
        self.current_video_path = None
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.original_height = 1080

        # --- NEW: Playback Speed State ---
        self.playback_speed = 1.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame_play)
        self.is_playing = False

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Main Splitter (Horizontal) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # ==========================================
        # LEFT PANEL: Imported Videos & Project Saving
        # ==========================================
        left_widget = QWidget()
        left_widget.setMinimumWidth(150)
        left_panel = QVBoxLayout(left_widget)

        project_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Project")
        self.btn_save.clicked.connect(self.save_project)
        self.btn_load = QPushButton("Load Project")
        self.btn_load.clicked.connect(self.load_project)
        project_layout.addWidget(self.btn_save)
        project_layout.addWidget(self.btn_load)
        left_panel.addLayout(project_layout)

        left_panel.addWidget(QLabel("")) # Spacer

        self.btn_import = QPushButton("Import Videos")
        self.btn_import.clicked.connect(self.import_videos)
        left_panel.addWidget(self.btn_import)

        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.load_video)
        left_panel.addWidget(QLabel("Imported Videos:"))
        left_panel.addWidget(self.video_list)

        self.btn_delete_video = QPushButton("Remove Selected Video")
        self.btn_delete_video.clicked.connect(self.delete_video)
        left_panel.addWidget(self.btn_delete_video)

        main_splitter.addWidget(left_widget)

        # ==========================================
        # CENTER PANEL: Preview & Trimming
        # ==========================================
        center_widget = QWidget()
        center_widget.setMinimumWidth(450)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        center_splitter = QSplitter(Qt.Orientation.Vertical)
        center_layout.addWidget(center_splitter)

        # TOP: Video Frame
        self.video_frame = QLabel("Select a video to preview")
        self.video_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_frame.setMinimumSize(400, 250)
        self.video_frame.setStyleSheet("background-color: black; color: white;")
        center_splitter.addWidget(self.video_frame)

        # BOTTOM: Editing Controls Container
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)

        # Nudge Target Selection
        nudge_options_layout = QHBoxLayout()
        self.nudge_group = QButtonGroup(self)

        self.radio_start = QRadioButton("Trim Start")
        self.radio_playhead = QRadioButton("Scrub Playhead")
        self.radio_playhead.setChecked(True)
        self.radio_end = QRadioButton("Trim End")

        self.nudge_group.addButton(self.radio_start)
        self.nudge_group.addButton(self.radio_playhead)
        self.nudge_group.addButton(self.radio_end)

        self.radio_start.toggled.connect(self.on_nudge_target_changed)
        self.radio_end.toggled.connect(self.on_nudge_target_changed)

        nudge_options_layout.addWidget(QLabel("Arrow Keys Target:"))
        nudge_options_layout.addWidget(self.radio_start)
        nudge_options_layout.addWidget(self.radio_playhead)
        nudge_options_layout.addWidget(self.radio_end)
        controls_layout.addLayout(nudge_options_layout)

        # Slider and Nudge Buttons
        slider_layout = QHBoxLayout()

        self.btn_play = QPushButton("Play")
        self.btn_play.setMaximumWidth(60)
        self.btn_play.setEnabled(False)
        self.btn_play.setToolTip("Play or Pause the video (Spacebar)")
        self.btn_play.clicked.connect(self.toggle_playback)
        slider_layout.addWidget(self.btn_play)

        # --- NEW: Playback Speed Dropdown ---
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.1x", "0.25x", "0.5x", "0.75x", "1x", "1.5x", "2x", "3x", "5x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.setToolTip("Playback Speed")
        self.speed_combo.currentTextChanged.connect(self.change_playback_speed)
        slider_layout.addWidget(self.speed_combo)

        self.btn_skip_back = QPushButton("<<")
        self.btn_skip_back.setMaximumWidth(30)
        self.btn_skip_back.setEnabled(False)
        self.btn_skip_back.setToolTip("Skip backward 15 seconds")
        self.btn_skip_back.clicked.connect(self.skip_backward)
        slider_layout.addWidget(self.btn_skip_back)

        self.btn_prev_frame = QPushButton("<")
        self.btn_prev_frame.setMaximumWidth(30)
        self.btn_prev_frame.setEnabled(False)
        self.btn_prev_frame.setToolTip("Step backward 1 frame (Left Arrow)")
        self.btn_prev_frame.clicked.connect(self.step_backward)
        slider_layout.addWidget(self.btn_prev_frame)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.scrub_video)
        self.slider.sliderPressed.connect(self.pause_playback)
        slider_layout.addWidget(self.slider)

        self.btn_next_frame = QPushButton(">")
        self.btn_next_frame.setMaximumWidth(30)
        self.btn_next_frame.setEnabled(False)
        self.btn_next_frame.setToolTip("Step forward 1 frame (Right Arrow)")
        self.btn_next_frame.clicked.connect(self.step_forward)
        slider_layout.addWidget(self.btn_next_frame)

        self.btn_skip_forward = QPushButton(">>")
        self.btn_skip_forward.setMaximumWidth(30)
        self.btn_skip_forward.setEnabled(False)
        self.btn_skip_forward.setToolTip("Skip forward 15 seconds")
        self.btn_skip_forward.clicked.connect(self.skip_forward)
        slider_layout.addWidget(self.btn_skip_forward)

        controls_layout.addLayout(slider_layout)

        # Shot controls (Times)
        shot_controls1 = QHBoxLayout()

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setDecimals(3)
        self.start_spin.setRange(0, 99999)
        self.start_spin.setSuffix(" s")
        self.start_spin.valueChanged.connect(self.on_start_changed)
        self.btn_set_start = QPushButton("Set Start to Playhead")
        self.btn_set_start.clicked.connect(lambda: self.start_spin.setValue(self.slider.value() / self.fps if self.fps else 0))

        self.end_spin = QDoubleSpinBox()
        self.end_spin.setDecimals(3)
        self.end_spin.setRange(0, 99999)
        self.end_spin.setSuffix(" s")
        self.end_spin.valueChanged.connect(self.on_end_changed)
        self.btn_set_end = QPushButton("Set End to Playhead")
        self.btn_set_end.clicked.connect(lambda: self.end_spin.setValue(self.slider.value() / self.fps if self.fps else 0))

        for w in [self.start_spin, self.btn_set_start, self.end_spin, self.btn_set_end]:
            shot_controls1.addWidget(w)
        controls_layout.addLayout(shot_controls1)

        # Shot controls (Name & Submit)
        shot_controls2 = QVBoxLayout()
        name_add_layout = QHBoxLayout()

        self.shot_name = QLineEdit()
        self.shot_name.setPlaceholderText("Unique Shot Name")
        self.shot_name.textChanged.connect(self.validate_shot)

        self.btn_add_shot = QPushButton("Add Shot")
        self.btn_add_shot.setEnabled(False)
        self.btn_add_shot.clicked.connect(self.add_shot)

        name_add_layout.addWidget(self.shot_name)
        name_add_layout.addWidget(self.btn_add_shot)
        shot_controls2.addLayout(name_add_layout)

        self.add_status_label = QLabel("Load a video to begin.")
        self.add_status_label.setStyleSheet("color: gray; font-style: italic; font-size: 11px;")
        self.add_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shot_controls2.addWidget(self.add_status_label)

        self.estimate_label = QLabel("Est. GIF Size: 0.0 MB")
        self.estimate_label.setStyleSheet("color: gray; font-style: italic; font-size: 11px;")
        self.estimate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shot_controls2.addWidget(self.estimate_label)

        controls_layout.addLayout(shot_controls2)
        center_splitter.addWidget(controls_widget)
        center_splitter.setSizes([600, 150])

        main_splitter.addWidget(center_widget)

        # ==========================================
        # RIGHT PANEL: Export Settings & List
        # ==========================================
        right_widget = QWidget()
        right_widget.setMinimumWidth(200)
        right_panel = QVBoxLayout(right_widget)

        mp4_res_layout = QHBoxLayout()
        mp4_res_layout.addWidget(QLabel("MP4 Resolution:"))
        self.mp4_res_combo = QComboBox()
        self.mp4_res_combo.addItems(["Original", "1080p", "720p", "480p", "360p"])
        mp4_res_layout.addWidget(self.mp4_res_combo)
        right_panel.addLayout(mp4_res_layout)

        gif_res_layout = QHBoxLayout()
        gif_res_layout.addWidget(QLabel("GIF Resolution:"))
        self.gif_res_combo = QComboBox()
        self.gif_res_combo.addItems(["Original", "720p", "480p", "360p"])
        self.gif_res_combo.currentTextChanged.connect(self.update_estimate)
        gif_res_layout.addWidget(self.gif_res_combo)
        right_panel.addLayout(gif_res_layout)

        self.size_label = QLabel("GIF Size Limit: 50 MB")
        right_panel.addWidget(self.size_label)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(5, 150)
        self.size_slider.setValue(50)
        self.size_slider.valueChanged.connect(lambda v: self.size_label.setText(f"Hard Size Limit: {v} MB"))
        right_panel.addWidget(self.size_slider)

        self.shot_list = QListWidget()
        right_panel.addWidget(QLabel("Shots to Export:"))
        right_panel.addWidget(self.shot_list)

        self.btn_delete_shot = QPushButton("Remove Selected Shot")
        self.btn_delete_shot.clicked.connect(self.delete_shot)
        right_panel.addWidget(self.btn_delete_shot)

        self.btn_export = QPushButton("Export All Shots")
        self.btn_export.setStyleSheet("background-color: #2e7d32; color: white; padding: 10px; font-weight: bold;")
        self.btn_export.clicked.connect(self.export_shots)
        right_panel.addWidget(self.btn_export)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([200, 650, 250])

    # --- Save and Load Logic ---
    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if not file_path: return

        project_data = {
            "videos": self.videos,
            "shots": self.shots
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
            QMessageBox.information(self, "Success", "Project saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{str(e)}")

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON Files (*.json)")
        if not file_path: return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            self.pause_playback()
            if self.cap:
                self.cap.release()
                self.cap = None
            self.current_video_path = None
            self.video_frame.setPixmap(QPixmap())
            self.video_frame.setText("Select a video to preview")

            self.slider.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_prev_frame.setEnabled(False)
            self.btn_next_frame.setEnabled(False)
            self.btn_skip_back.setEnabled(False)
            self.btn_skip_forward.setEnabled(False)

            self.slider.setValue(0)
            self.start_spin.setValue(0)
            self.end_spin.setValue(0)
            self.shot_name.clear()

            self.videos.clear()
            self.shots.clear()
            self.video_list.clear()
            self.shot_list.clear()

            self.videos = project_data.get("videos", [])
            for v in self.videos:
                self.video_list.addItem(v.split('/')[-1])

            self.shots = project_data.get("shots", [])
            for s in self.shots:
                self.shot_list.addItem(f"{s['name']} [{s['start']:.2f}s-{s['end']:.2f}s]")

            self.validate_shot()

            if self.videos:
                self.video_list.setCurrentRow(0)
                self.load_video(self.video_list.item(0))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{str(e)}")

    # --- Playback Logic ---
    def toggle_playback(self):
        if not self.cap: return

        if self.is_playing:
            self.pause_playback()
        else:
            if self.slider.value() >= self.total_frames - 1:
                self.slider.setValue(0)

            # --- UPDATED: Calculate interval based on speed multiplier ---
            base_interval = 1000 / self.fps if self.fps > 0 else 33
            adjusted_interval = int(base_interval / self.playback_speed)

            self.timer.start(adjusted_interval)
            self.btn_play.setText("Pause")
            self.is_playing = True

    def pause_playback(self):
        if self.is_playing:
            self.timer.stop()
            self.btn_play.setText("Play")
            self.is_playing = False

    def next_frame_play(self):
        if not self.cap: return
        current_frame = self.slider.value()

        if current_frame < self.total_frames - 1:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg).scaled(self.video_frame.size(), Qt.AspectRatioMode.KeepAspectRatio)
                self.video_frame.setPixmap(pixmap)

                self.slider.blockSignals(True)
                self.slider.setValue(current_frame + 1)
                self.slider.blockSignals(False)
            else:
                self.pause_playback()
        else:
            self.pause_playback()

    # --- NEW: Change Playback Speed ---
    def change_playback_speed(self, text):
        # Strip the 'x' off the end and convert to a float
        self.playback_speed = float(text.replace('x', ''))

        # If the video is currently playing, seamlessly update the timer speed
        if self.is_playing:
            base_interval = 1000 / self.fps if self.fps > 0 else 33
            adjusted_interval = int(base_interval / self.playback_speed)
            self.timer.start(adjusted_interval)

    # --- Deletion Logic ---
    def delete_video(self):
        current_row = self.video_list.currentRow()
        if current_row < 0: return

        if self.current_video_path == self.videos[current_row]:
            self.pause_playback()

            if self.cap:
                self.cap.release()
                self.cap = None
            self.current_video_path = None

            self.video_frame.setPixmap(QPixmap())
            self.video_frame.setText("Select a video to preview")

            self.slider.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_prev_frame.setEnabled(False)
            self.btn_next_frame.setEnabled(False)
            self.btn_skip_back.setEnabled(False)
            self.btn_skip_forward.setEnabled(False)

            self.slider.setValue(0)
            self.start_spin.setValue(0)
            self.end_spin.setValue(0)
            self.shot_name.clear()
            self.validate_shot()

        self.videos.pop(current_row)
        self.video_list.takeItem(current_row)

    def delete_shot(self):
        current_row = self.shot_list.currentRow()
        if current_row < 0: return

        self.shots.pop(current_row)
        self.shot_list.takeItem(current_row)
        self.validate_shot()

    # --- Validation Logic ---
    def validate_shot(self):
        if not self.current_video_path:
            self.add_status_label.setText("Load a video to begin.")
            self.btn_add_shot.setEnabled(False)
            return

        name = self.shot_name.text().strip()
        start = self.start_spin.value()
        end = self.end_spin.value()

        if not name:
            self.add_status_label.setText("Please enter a shot name.")
            self.btn_add_shot.setEnabled(False)
            return

        existing_names = [s['name'] for s in self.shots]
        if name in existing_names:
            self.add_status_label.setText("Shot name must be unique.")
            self.btn_add_shot.setEnabled(False)
            return

        if end <= start:
            self.add_status_label.setText("End time must be greater than start time.")
            self.btn_add_shot.setEnabled(False)
            return

        self.add_status_label.setText("Ready to add shot.")
        self.btn_add_shot.setEnabled(True)

    # --- Syncing Trims to Video Preview ---
    def on_nudge_target_changed(self):
        if not self.cap: return
        if self.radio_start.isChecked():
            self.slider.setValue(round(self.start_spin.value() * self.fps))
        elif self.radio_end.isChecked():
            self.slider.setValue(round(self.end_spin.value() * self.fps))

    def on_start_changed(self, val):
        self.update_estimate()
        self.validate_shot()
        if self.radio_start.isChecked() and self.cap:
            self.slider.setValue(round(val * self.fps))

    def on_end_changed(self, val):
        self.update_estimate()
        self.validate_shot()
        if self.radio_end.isChecked() and self.cap:
            self.slider.setValue(round(val * self.fps))

# --- Keyboard & Nudging Logic ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not self.shot_name.hasFocus():
            self.toggle_playback()

        # Left Arrow Logic
        elif event.key() == Qt.Key.Key_Left:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.skip_backward()  # Shift + Left = Skip 15s
            else:
                self.step_backward()  # Left only = Nudge 1 frame

        # Right Arrow Logic
        elif event.key() == Qt.Key.Key_Right:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.skip_forward()   # Shift + Right = Skip 15s
            else:
                self.step_forward()   # Right only = Nudge 1 frame

        else:
            super().keyPressEvent(event)

    def step_backward(self):
        if not self.cap: return
        self.pause_playback()

        if self.radio_start.isChecked():
            curr_frame = round(self.start_spin.value() * self.fps)
            self.start_spin.setValue(max(0, curr_frame - 1) / self.fps)
        elif self.radio_end.isChecked():
            curr_frame = round(self.end_spin.value() * self.fps)
            self.end_spin.setValue(max(0, curr_frame - 1) / self.fps)
        else:
            new_frame = max(0, self.slider.value() - 1)
            self.slider.setValue(new_frame)

    def step_forward(self):
        if not self.cap: return
        self.pause_playback()

        if self.radio_start.isChecked():
            curr_frame = round(self.start_spin.value() * self.fps)
            self.start_spin.setValue(min(self.total_frames, curr_frame + 1) / self.fps)
        elif self.radio_end.isChecked():
            curr_frame = round(self.end_spin.value() * self.fps)
            self.end_spin.setValue(min(self.total_frames, curr_frame + 1) / self.fps)
        else:
            new_frame = min(self.total_frames, self.slider.value() + 1)
            self.slider.setValue(new_frame)

    def skip_backward(self):
        if not self.cap: return
        self.pause_playback()
        skip_frames = round(15.0 * self.fps)

        if self.radio_start.isChecked():
            curr_frame = round(self.start_spin.value() * self.fps)
            self.start_spin.setValue(max(0, curr_frame - skip_frames) / self.fps)
        elif self.radio_end.isChecked():
            curr_frame = round(self.end_spin.value() * self.fps)
            self.end_spin.setValue(max(0, curr_frame - skip_frames) / self.fps)
        else:
            new_frame = max(0, self.slider.value() - skip_frames)
            self.slider.setValue(new_frame)

    def skip_forward(self):
        if not self.cap: return
        self.pause_playback()
        skip_frames = round(15.0 * self.fps)

        if self.radio_start.isChecked():
            curr_frame = round(self.start_spin.value() * self.fps)
            self.start_spin.setValue(min(self.total_frames, curr_frame + skip_frames) / self.fps)
        elif self.radio_end.isChecked():
            curr_frame = round(self.end_spin.value() * self.fps)
            self.end_spin.setValue(min(self.total_frames, curr_frame + skip_frames) / self.fps)
        else:
            new_frame = min(self.total_frames, self.slider.value() + skip_frames)
            self.slider.setValue(new_frame)

    # --- Core Mechanics ---
    def update_estimate(self):
        duration = self.end_spin.value() - self.start_spin.value()
        if duration <= 0:
            self.estimate_label.setText("Est. GIF Size: 0.0 MB")
            return

        res_str = self.gif_res_combo.currentText()
        height = self.original_height if res_str == "Original" else int(res_str.replace('p', ''))
        size_factor = (height / 720.0) ** 2
        est_mb = duration * size_factor * 1.0
        self.estimate_label.setText(f"Rough Est. Size: {est_mb * 0.6:.1f} MB - {est_mb * 1.5:.1f} MB (Will auto-compress to limit)")

    def import_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select OBS Videos", "", "Video Files (*.mkv *.mp4)")
        if not files: return

        was_empty = self.video_list.count() == 0

        for file in files:
            if file not in self.videos:
                self.videos.append(file)
                self.video_list.addItem(file.split('/')[-1])

        if was_empty and self.video_list.count() > 0:
            self.video_list.setCurrentRow(0)
            self.load_video(self.video_list.item(0))

    def load_video(self, item):
        idx = self.video_list.row(item)
        self.current_video_path = self.videos[idx]

        self.pause_playback()

        if self.cap: self.cap.release()

        self.cap = cv2.VideoCapture(self.current_video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frame_time = 1.0 / self.fps
        self.start_spin.setSingleStep(frame_time)
        self.end_spin.setSingleStep(frame_time)

        self.slider.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_prev_frame.setEnabled(True)
        self.btn_next_frame.setEnabled(True)
        self.btn_skip_back.setEnabled(True)
        self.btn_skip_forward.setEnabled(True)

        self.slider.setRange(0, self.total_frames)
        self.slider.setValue(0)
        self.start_spin.setValue(0)
        self.end_spin.setValue(0)
        self.speed_combo.setCurrentText("1x") # Reset speed when a new video loads
        self.shot_name.clear()

        self.radio_playhead.setChecked(True)
        self.validate_shot()
        self.scrub_video(0)

    def scrub_video(self, frame_number):
        if not self.cap: return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(self.video_frame.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.video_frame.setPixmap(pixmap)

    def add_shot(self):
        if not self.current_video_path: return
        name = self.shot_name.text().strip()
        start = self.start_spin.value()
        end = self.end_spin.value()

        self.shots.append({
            "video": self.current_video_path,
            "start": start,
            "end": end,
            "name": name
        })
        self.shot_list.addItem(f"{name} [{start:.2f}s-{end:.2f}s]")

        self.shot_name.clear()
        self.validate_shot()

    def export_shots(self):
        if not self.shots: return
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir: return

        self.pause_playback()

        self.btn_export.setEnabled(False)
        self.btn_export.setText("Processing... Check Terminal")
        QApplication.processEvents()

        target_size = self.size_slider.value()
        mp4_res = self.mp4_res_combo.currentText()
        gif_res = self.gif_res_combo.currentText()

        for shot in self.shots:
            process_shot(shot["video"], shot["start"], shot["end"], shot["name"], output_dir, target_size, mp4_res, gif_res)

        QMessageBox.information(self, "Success", "Export complete!")
        self.btn_export.setEnabled(True)
        self.btn_export.setText("Export All Shots")