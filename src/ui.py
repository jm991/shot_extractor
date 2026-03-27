import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QFileDialog, QListWidget, QLabel, QLineEdit, QSlider, QSpinBox, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from src.processor import process_shot

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBS Shot Extractor")
        self.resize(950, 750)

        self.videos = []
        self.shots = []
        self.current_video_path = None
        self.cap = None
        self.fps = 30
        self.total_frames = 0
        self.original_height = 1080 

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel ---
        left_panel = QVBoxLayout()
        self.btn_import = QPushButton("Import MKV Videos")
        self.btn_import.clicked.connect(self.import_videos)
        left_panel.addWidget(self.btn_import)
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.load_video)
        left_panel.addWidget(QLabel("Imported Videos:"))
        left_panel.addWidget(self.video_list)
        main_layout.addLayout(left_panel, 1)

        # --- Center Panel ---
        center_panel = QVBoxLayout()
        self.video_frame = QLabel("Select a video to preview")
        self.video_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_frame.setMinimumSize(640, 360)
        self.video_frame.setStyleSheet("background-color: black; color: white;")
        center_panel.addWidget(self.video_frame)

        # Slider and Nudge Buttons Layout
        slider_layout = QHBoxLayout()
        
        self.btn_prev_frame = QPushButton("<")
        self.btn_prev_frame.setMaximumWidth(30)
        self.btn_prev_frame.setEnabled(False)
        self.btn_prev_frame.clicked.connect(self.step_backward)
        slider_layout.addWidget(self.btn_prev_frame)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self.scrub_video)
        slider_layout.addWidget(self.slider)
        
        self.btn_next_frame = QPushButton(">")
        self.btn_next_frame.setMaximumWidth(30)
        self.btn_next_frame.setEnabled(False)
        self.btn_next_frame.clicked.connect(self.step_forward)
        slider_layout.addWidget(self.btn_next_frame)

        center_panel.addLayout(slider_layout)

        # Shot controls
        shot_controls = QHBoxLayout()
        
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 99999)
        self.start_spin.setSuffix(" sec")
        self.start_spin.valueChanged.connect(self.update_estimate)
        self.btn_set_start = QPushButton("Set Start")
        self.btn_set_start.clicked.connect(lambda: self.start_spin.setValue(self.slider.value() // int(self.fps)))
        
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 99999)
        self.end_spin.setSuffix(" sec")
        self.end_spin.valueChanged.connect(self.update_estimate)
        self.btn_set_end = QPushButton("Set End")
        self.btn_set_end.clicked.connect(lambda: self.end_spin.setValue(self.slider.value() // int(self.fps)))

        self.shot_name = QLineEdit()
        self.shot_name.setPlaceholderText("Shot Name")
        
        self.btn_add_shot = QPushButton("Add Shot")
        self.btn_add_shot.clicked.connect(self.add_shot)

        # Add to layout
        for w in [self.btn_set_start, self.start_spin, self.btn_set_end, self.end_spin]:
            shot_controls.addWidget(w)
            
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(self.shot_name)
        settings_layout.addWidget(self.btn_add_shot)
        
        self.estimate_label = QLabel("Est. GIF Size: 0.0 MB")
        self.estimate_label.setStyleSheet("color: gray; font-style: italic;")
        
        center_panel.addLayout(shot_controls)
        center_panel.addLayout(settings_layout)
        center_panel.addWidget(self.estimate_label)
        main_layout.addLayout(center_panel, 3)

        # --- Right Panel ---
        right_panel = QVBoxLayout()
        
        # Global Resolution Dropdown
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Export Resolution:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["Original", "720p", "480p", "360p"])
        self.res_combo.currentTextChanged.connect(self.update_estimate)
        res_layout.addWidget(self.res_combo)
        right_panel.addLayout(res_layout)
        
        # Global Size Limit Slider
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

        self.btn_export = QPushButton("Export All Shots")
        self.btn_export.setStyleSheet("background-color: #2e7d32; color: white; padding: 10px; font-weight: bold;")
        self.btn_export.clicked.connect(self.export_shots)
        right_panel.addWidget(self.btn_export)

        main_layout.addLayout(right_panel, 1)

    def step_backward(self):
        if not self.cap: return
        new_frame = max(0, self.slider.value() - 1)
        self.slider.setValue(new_frame)
        self.scrub_video(new_frame)

    def step_forward(self):
        if not self.cap: return
        new_frame = min(self.total_frames, self.slider.value() + 1)
        self.slider.setValue(new_frame)
        self.scrub_video(new_frame)

    def update_estimate(self):
        duration = self.end_spin.value() - self.start_spin.value()
        if duration <= 0:
            self.estimate_label.setText("Est. GIF Size: 0.0 MB")
            return
            
        res_str = self.res_combo.currentText()
        height = self.original_height if res_str == "Original" else int(res_str.replace('p', ''))
        
        size_factor = (height / 720.0) ** 2 
        est_mb = duration * size_factor * 1.0 
        
        lower_bound = est_mb * 0.6
        upper_bound = est_mb * 1.5
        
        self.estimate_label.setText(f"Rough Est. Size: {lower_bound:.1f} MB - {upper_bound:.1f} MB (Will auto-compress to fit limit)")

    def import_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select OBS Videos", "", "Video Files (*.mkv *.mp4)")
        for file in files:
            if file not in self.videos:
                self.videos.append(file)
                self.video_list.addItem(file.split('/')[-1])

    def load_video(self, item):
        idx = self.video_list.row(item)
        self.current_video_path = self.videos[idx]
        if self.cap: self.cap.release()
        self.cap = cv2.VideoCapture(self.current_video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.slider.setEnabled(True)
        self.btn_prev_frame.setEnabled(True)
        self.btn_next_frame.setEnabled(True)
        self.slider.setRange(0, self.total_frames)
        self.slider.setValue(0)
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
        start, end = self.start_spin.value(), self.end_spin.value()
        
        if not name or end <= start:
            QMessageBox.warning(self, "Error", "Invalid name or timestamps.")
            return

        self.shots.append({
            "video": self.current_video_path, 
            "start": start, 
            "end": end, 
            "name": name
        })
        self.shot_list.addItem(f"{name} [{start}s-{end}s]")
        self.shot_name.clear()

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