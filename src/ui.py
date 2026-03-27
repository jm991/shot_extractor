import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QFileDialog, QListWidget, QLabel, QLineEdit, QSlider, QDoubleSpinBox, QMessageBox, 
    QComboBox, QSplitter, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt
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
        # LEFT PANEL: Imported Videos
        # ==========================================
        left_widget = QWidget()
        left_widget.setMinimumWidth(150)
        left_panel = QVBoxLayout(left_widget)
        
        self.btn_import = QPushButton("Import Videos")
        self.btn_import.clicked.connect(self.import_videos)
        left_panel.addWidget(self.btn_import)
        
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.load_video)
        left_panel.addWidget(QLabel("Imported Videos:"))
        left_panel.addWidget(self.video_list)
        
        # NEW: Delete Video Button
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
        self.btn_prev_frame = QPushButton("<")
        self.btn_prev_frame.setMaximumWidth(30)
        self.btn_prev_frame.setEnabled(False)
        self.btn_prev_frame.clicked.connect(self.step_backward)
        slider_layout.addWidget(self.btn_prev_frame)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.scrub_video)
        slider_layout.addWidget(self.slider)
        
        self.btn_next_frame = QPushButton(">")
        self.btn_next_frame.setMaximumWidth(30)
        self.btn_next_frame.setEnabled(False)
        self.btn_next_frame.clicked.connect(self.step_forward)
        slider_layout.addWidget(self.btn_next_frame)
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
        
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Export Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["Original", "720p", "480p", "360p"])
        self.res_combo.currentTextChanged.connect(self.update_estimate)
        res_layout.addWidget(self.res_combo)
        right_panel.addLayout(res_layout)
        
        self.size_label = QLabel("Hard Size Limit: 50 MB")
        right_panel.addWidget(self.size_label)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(5, 150)
        self.size_slider.setValue(50)
        self.size_slider.valueChanged.connect(lambda v: self.size_label.setText(f"Hard Size Limit: {v} MB"))
        right_panel.addWidget(self.size_slider)
        
        self.shot_list = QListWidget()
        right_panel.addWidget(QLabel("Shots to Export:"))
        right_panel.addWidget(self.shot_list)

        # NEW: Delete Shot Button
        self.btn_delete_shot = QPushButton("Remove Selected Shot")
        self.btn_delete_shot.clicked.connect(self.delete_shot)
        right_panel.addWidget(self.btn_delete_shot)

        self.btn_export = QPushButton("Export All Shots")
        self.btn_export.setStyleSheet("background-color: #2e7d32; color: white; padding: 10px; font-weight: bold;")
        self.btn_export.clicked.connect(self.export_shots)
        right_panel.addWidget(self.btn_export)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([200, 650, 250])

    # --- Deletion Logic ---
    def delete_video(self):
        current_row = self.video_list.currentRow()
        if current_row < 0: return # No item selected
        
        # If the video we are deleting is currently loaded in the preview player...
        if self.current_video_path == self.videos[current_row]:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.current_video_path = None
            
            # Clear the UI
            self.video_frame.setPixmap(QPixmap()) # Clears the image
            self.video_frame.setText("Select a video to preview")
            self.slider.setEnabled(False)
            self.btn_prev_frame.setEnabled(False)
            self.btn_next_frame.setEnabled(False)
            self.slider.setValue(0)
            self.start_spin.setValue(0)
            self.end_spin.setValue(0)
            self.shot_name.clear()
            self.validate_shot()

        # Remove from backend list and UI list
        self.videos.pop(current_row)
        self.video_list.takeItem(current_row)

    def delete_shot(self):
        current_row = self.shot_list.currentRow()
        if current_row < 0: return # No item selected
        
        # Remove from backend list and UI list
        self.shots.pop(current_row)
        self.shot_list.takeItem(current_row)
        
        # Re-validate in case deleting this shot freed up a shot name you wanted to use
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

    # --- Keyboard Nudging ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.step_backward()
        elif event.key() == Qt.Key.Key_Right:
            self.step_forward()
        else:
            super().keyPressEvent(event)

    def step_backward(self):
        if not self.cap: return
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
        if self.radio_start.isChecked():
            curr_frame = round(self.start_spin.value() * self.fps)
            self.start_spin.setValue(min(self.total_frames, curr_frame + 1) / self.fps)
        elif self.radio_end.isChecked():
            curr_frame = round(self.end_spin.value() * self.fps)
            self.end_spin.setValue(min(self.total_frames, curr_frame + 1) / self.fps)
        else:
            new_frame = min(self.total_frames, self.slider.value() + 1)
            self.slider.setValue(new_frame)

    # --- Core Mechanics ---
    def update_estimate(self):
        duration = self.end_spin.value() - self.start_spin.value()
        if duration <= 0:
            self.estimate_label.setText("Est. GIF Size: 0.0 MB")
            return
            
        res_str = self.res_combo.currentText()
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
        if self.cap: self.cap.release()
        
        self.cap = cv2.VideoCapture(self.current_video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        frame_time = 1.0 / self.fps
        self.start_spin.setSingleStep(frame_time)
        self.end_spin.setSingleStep(frame_time)
        
        self.slider.setEnabled(True)
        self.btn_prev_frame.setEnabled(True)
        self.btn_next_frame.setEnabled(True)
        self.slider.setRange(0, self.total_frames)
        self.slider.setValue(0)
        self.start_spin.setValue(0)
        self.end_spin.setValue(0)
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

        self.btn_export.setEnabled(False)
        self.btn_export.setText("Processing... Check Terminal")
        QApplication.processEvents() 
        
        target_size = self.size_slider.value()
        global_res = self.res_combo.currentText() 

        for shot in self.shots:
            process_shot(shot["video"], shot["start"], shot["end"], shot["name"], output_dir, target_size, global_res)
            
        QMessageBox.information(self, "Success", "Export complete!")
        self.btn_export.setEnabled(True)
        self.btn_export.setText("Export All Shots")