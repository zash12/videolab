#!/usr/bin/env python3
"""
Video Lab Pro Beta - Essential Features
Multi-tab desktop app for video effects, overlays, tracking, and export
Single-file implementation with core functionality
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
import numpy as np
import threading
import queue
import json
import os
import time
from pathlib import Path
from PIL import Image, ImageTk
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoLabPro:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Lab Pro Beta v1.0")
        self.root.geometry("1400x900")
        
        # Core state
        self.video_cap = None
        self.current_frame = None
        self.processed_frame = None
        self.frame_count = 0
        self.fps = 30
        self.current_frame_idx = 0
        self.is_playing = False
        self.preview_scale = 0.5
        
        # Pipeline and effects
        self.effects_pipeline = []
        self.overlay_image = None
        self.overlay_params = {'x': 10, 'y': 10, 'opacity': 1.0, 'scale': 1.0}
        self.crop_params = {'x': 0, 'y': 0, 'w': 0, 'h': 0, 'enabled': False}
        
        # Tracking
        self.trackers = []
        self.track_points = []
        self.lk_params = dict(winSize=(15,15), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        self.feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
        
        # Threading
        self.frame_queue = queue.Queue(maxsize=30)
        self.preview_thread = None
        self.stop_preview = False
        
        # Project data
        self.project_path = None
        self.markers = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the multi-tab UI"""
        # Main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tabs
        self.setup_import_tab()
        self.setup_effects_tab()
        self.setup_overlay_tab()
        self.setup_geometry_tab()
        self.setup_tracking_tab()
        self.setup_timeline_tab()
        self.setup_export_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind keyboard shortcuts
        self.root.bind('<space>', lambda e: self.toggle_playback())
        self.root.bind('<Left>', lambda e: self.step_frame(-1))
        self.root.bind('<Right>', lambda e: self.step_frame(1))
        self.root.bind('<Control-o>', lambda e: self.open_video())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        
    def setup_import_tab(self):
        """Import & Metadata tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Import & Metadata")
        
        # File operations
        file_frame = ttk.LabelFrame(tab, text="File Operations")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(file_frame, text="Open Video", command=self.open_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Open Image Sequence", command=self.open_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Project", command=self.save_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Load Project", command=self.load_project).pack(side=tk.LEFT, padx=5)
        
        # Preview area
        preview_frame = ttk.LabelFrame(tab, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.preview_label = ttk.Label(preview_frame, text="No video loaded")
        self.preview_label.pack(expand=True)
        
        # Controls
        controls_frame = ttk.Frame(preview_frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.play_button = ttk.Button(controls_frame, text="Play", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(controls_frame, text="<<", command=lambda: self.step_frame(-10)).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text="<", command=lambda: self.step_frame(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text=">", command=lambda: self.step_frame(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text=">>", command=lambda: self.step_frame(10)).pack(side=tk.LEFT, padx=2)
        
        # Frame info
        self.frame_info_var = tk.StringVar(value="Frame: 0/0 | FPS: 0 | Time: 00:00:00")
        ttk.Label(controls_frame, textvariable=self.frame_info_var).pack(side=tk.RIGHT, padx=5)
        
        # Metadata
        meta_frame = ttk.LabelFrame(tab, text="Video Metadata")
        meta_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.metadata_text = tk.Text(meta_frame, height=4, state=tk.DISABLED)
        self.metadata_text.pack(fill=tk.X, padx=5, pady=5)
        
    def setup_effects_tab(self):
        """Effects & Filters tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Effects & Filters")
        
        # Effects list
        list_frame = ttk.LabelFrame(tab, text="Active Effects Pipeline")
        list_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.effects_listbox = tk.Listbox(list_frame, height=6)
        self.effects_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        list_controls = ttk.Frame(list_frame)
        list_controls.pack(side=tk.RIGHT, padx=5, pady=5)
        
        ttk.Button(list_controls, text="Remove", command=self.remove_effect).pack(fill=tk.X, pady=2)
        ttk.Button(list_controls, text="Clear All", command=self.clear_effects).pack(fill=tk.X, pady=2)
        
        # Effect controls
        controls_frame = ttk.LabelFrame(tab, text="Effect Controls")
        controls_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Edge Detection
        edge_frame = ttk.LabelFrame(controls_frame, text="Edge Detection")
        edge_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.canny_low = tk.DoubleVar(value=50)
        self.canny_high = tk.DoubleVar(value=150)
        
        ttk.Label(edge_frame, text="Canny Low:").grid(row=0, column=0, sticky="w")
        ttk.Scale(edge_frame, from_=0, to=255, variable=self.canny_low, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=0, column=1, sticky="ew")
        ttk.Label(edge_frame, textvariable=self.canny_low).grid(row=0, column=2)
        
        ttk.Label(edge_frame, text="Canny High:").grid(row=1, column=0, sticky="w")
        ttk.Scale(edge_frame, from_=0, to=255, variable=self.canny_high, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=1, column=1, sticky="ew")
        ttk.Label(edge_frame, textvariable=self.canny_high).grid(row=1, column=2)
        
        ttk.Button(edge_frame, text="Add Canny Edge", command=lambda: self.add_effect("canny")).grid(row=2, column=0, columnspan=3, pady=5)
        
        # Blur Effects
        blur_frame = ttk.LabelFrame(controls_frame, text="Blur Effects")
        blur_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        self.blur_kernel = tk.IntVar(value=5)
        self.blur_sigma = tk.DoubleVar(value=1.0)
        
        ttk.Label(blur_frame, text="Kernel Size:").grid(row=0, column=0, sticky="w")
        ttk.Scale(blur_frame, from_=1, to=51, variable=self.blur_kernel, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=0, column=1, sticky="ew")
        ttk.Label(blur_frame, textvariable=self.blur_kernel).grid(row=0, column=2)
        
        ttk.Label(blur_frame, text="Sigma:").grid(row=1, column=0, sticky="w")
        ttk.Scale(blur_frame, from_=0.1, to=10.0, variable=self.blur_sigma, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=1, column=1, sticky="ew")
        ttk.Label(blur_frame, textvariable=self.blur_sigma).grid(row=1, column=2)
        
        ttk.Button(blur_frame, text="Add Gaussian Blur", command=lambda: self.add_effect("gaussian_blur")).grid(row=2, column=0, columnspan=3, pady=5)
        
        # Color Adjustments
        color_frame = ttk.LabelFrame(controls_frame, text="Color Adjustments")
        color_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        self.brightness = tk.DoubleVar(value=0)
        self.contrast = tk.DoubleVar(value=1.0)
        self.saturation = tk.DoubleVar(value=1.0)
        
        ttk.Label(color_frame, text="Brightness:").grid(row=0, column=0, sticky="w")
        ttk.Scale(color_frame, from_=-100, to=100, variable=self.brightness, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=0, column=1, sticky="ew")
        ttk.Label(color_frame, textvariable=self.brightness).grid(row=0, column=2)
        
        ttk.Label(color_frame, text="Contrast:").grid(row=0, column=3, sticky="w")
        ttk.Scale(color_frame, from_=0.0, to=3.0, variable=self.contrast, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=0, column=4, sticky="ew")
        ttk.Label(color_frame, textvariable=self.contrast).grid(row=0, column=5)
        
        ttk.Button(color_frame, text="Add Color Adjust", command=lambda: self.add_effect("color_adjust")).grid(row=1, column=0, columnspan=6, pady=5)
        
        # Configure grid weights
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=1)
        edge_frame.grid_columnconfigure(1, weight=1)
        blur_frame.grid_columnconfigure(1, weight=1)
        color_frame.grid_columnconfigure(1, weight=1)
        color_frame.grid_columnconfigure(4, weight=1)
        
    def setup_overlay_tab(self):
        """Overlays & Compositing tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Overlays & Compositing")
        
        # Image Overlay
        overlay_frame = ttk.LabelFrame(tab, text="Image Overlay")
        overlay_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(overlay_frame, text="Load Overlay Image", command=self.load_overlay).pack(side=tk.LEFT, padx=5)
        ttk.Button(overlay_frame, text="Clear Overlay", command=self.clear_overlay).pack(side=tk.LEFT, padx=5)
        
        # Overlay controls
        controls_frame = ttk.LabelFrame(tab, text="Overlay Controls")
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.overlay_x = tk.IntVar(value=10)
        self.overlay_y = tk.IntVar(value=10)
        self.overlay_opacity = tk.DoubleVar(value=1.0)
        self.overlay_scale = tk.DoubleVar(value=1.0)
        
        ttk.Label(controls_frame, text="X Position:").grid(row=0, column=0, sticky="w")
        ttk.Scale(controls_frame, from_=0, to=1920, variable=self.overlay_x, orient=tk.HORIZONTAL, command=self.update_overlay_params).grid(row=0, column=1, sticky="ew")
        ttk.Label(controls_frame, textvariable=self.overlay_x).grid(row=0, column=2)
        
        ttk.Label(controls_frame, text="Y Position:").grid(row=1, column=0, sticky="w")
        ttk.Scale(controls_frame, from_=0, to=1080, variable=self.overlay_y, orient=tk.HORIZONTAL, command=self.update_overlay_params).grid(row=1, column=1, sticky="ew")
        ttk.Label(controls_frame, textvariable=self.overlay_y).grid(row=1, column=2)
        
        ttk.Label(controls_frame, text="Opacity:").grid(row=2, column=0, sticky="w")
        ttk.Scale(controls_frame, from_=0.0, to=1.0, variable=self.overlay_opacity, orient=tk.HORIZONTAL, command=self.update_overlay_params).grid(row=2, column=1, sticky="ew")
        ttk.Label(controls_frame, textvariable=self.overlay_opacity).grid(row=2, column=2)
        
        ttk.Label(controls_frame, text="Scale:").grid(row=3, column=0, sticky="w")
        ttk.Scale(controls_frame, from_=0.1, to=5.0, variable=self.overlay_scale, orient=tk.HORIZONTAL, command=self.update_overlay_params).grid(row=3, column=1, sticky="ew")
        ttk.Label(controls_frame, textvariable=self.overlay_scale).grid(row=3, column=2)
        
        controls_frame.grid_columnconfigure(1, weight=1)
        
        # Text Overlay
        text_frame = ttk.LabelFrame(tab, text="Text Overlay")
        text_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.text_content = tk.StringVar(value="Sample Text")
        self.text_size = tk.IntVar(value=30)
        
        ttk.Label(text_frame, text="Text:").grid(row=0, column=0, sticky="w")
        ttk.Entry(text_frame, textvariable=self.text_content, width=30).grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(text_frame, text="Font Size:").grid(row=1, column=0, sticky="w")
        ttk.Scale(text_frame, from_=10, to=200, variable=self.text_size, orient=tk.HORIZONTAL, command=self.update_preview).grid(row=1, column=1, sticky="ew")
        
        ttk.Button(text_frame, text="Add Text Overlay", command=lambda: self.add_effect("text")).grid(row=2, column=0, columnspan=2, pady=5)
        
        text_frame.grid_columnconfigure(1, weight=1)
        
    def setup_geometry_tab(self):
        """Geometry tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Geometry")
        
        # Crop controls
        crop_frame = ttk.LabelFrame(tab, text="Crop & Resize")
        crop_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.crop_x = tk.IntVar(value=0)
        self.crop_y = tk.IntVar(value=0)
        self.crop_w = tk.IntVar(value=640)
        self.crop_h = tk.IntVar(value=480)
        self.crop_enabled = tk.BooleanVar()
        
        ttk.Checkbutton(crop_frame, text="Enable Crop", variable=self.crop_enabled, command=self.update_crop_params).grid(row=0, column=0, columnspan=2, sticky="w")
        
        ttk.Label(crop_frame, text="X:").grid(row=1, column=0, sticky="w")
        ttk.Scale(crop_frame, from_=0, to=1920, variable=self.crop_x, orient=tk.HORIZONTAL, command=self.update_crop_params).grid(row=1, column=1, sticky="ew")
        ttk.Label(crop_frame, textvariable=self.crop_x).grid(row=1, column=2)
        
        ttk.Label(crop_frame, text="Y:").grid(row=2, column=0, sticky="w")
        ttk.Scale(crop_frame, from_=0, to=1080, variable=self.crop_y, orient=tk.HORIZONTAL, command=self.update_crop_params).grid(row=2, column=1, sticky="ew")
        ttk.Label(crop_frame, textvariable=self.crop_y).grid(row=2, column=2)
        
        ttk.Label(crop_frame, text="Width:").grid(row=3, column=0, sticky="w")
        ttk.Scale(crop_frame, from_=32, to=1920, variable=self.crop_w, orient=tk.HORIZONTAL, command=self.update_crop_params).grid(row=3, column=1, sticky="ew")
        ttk.Label(crop_frame, textvariable=self.crop_w).grid(row=3, column=2)
        
        ttk.Label(crop_frame, text="Height:").grid(row=4, column=0, sticky="w")
        ttk.Scale(crop_frame, from_=32, to=1080, variable=self.crop_h, orient=tk.HORIZONTAL, command=self.update_crop_params).grid(row=4, column=1, sticky="ew")
        ttk.Label(crop_frame, textvariable=self.crop_h).grid(row=4, column=2)
        
        crop_frame.grid_columnconfigure(1, weight=1)
        
        # Aspect ratio presets
        aspect_frame = ttk.LabelFrame(tab, text="Aspect Ratio Presets")
        aspect_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(aspect_frame, text="16:9", command=lambda: self.set_aspect_ratio(16, 9)).pack(side=tk.LEFT, padx=5)
        ttk.Button(aspect_frame, text="9:16", command=lambda: self.set_aspect_ratio(9, 16)).pack(side=tk.LEFT, padx=5)
        ttk.Button(aspect_frame, text="1:1", command=lambda: self.set_aspect_ratio(1, 1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(aspect_frame, text="4:3", command=lambda: self.set_aspect_ratio(4, 3)).pack(side=tk.LEFT, padx=5)
        
    def setup_tracking_tab(self):
        """Tracking tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Tracking")
        
        # Tracking controls
        track_frame = ttk.LabelFrame(tab, text="Optical Flow Tracking")
        track_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(track_frame, text="Auto Detect Features", command=self.auto_detect_features).pack(side=tk.LEFT, padx=5)
        ttk.Button(track_frame, text="Clear Tracks", command=self.clear_tracks).pack(side=tk.LEFT, padx=5)
        ttk.Button(track_frame, text="Export Tracks (CSV)", command=self.export_tracks).pack(side=tk.LEFT, padx=5)
        
        # Tracking parameters
        params_frame = ttk.LabelFrame(tab, text="Tracking Parameters")
        params_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.max_corners = tk.IntVar(value=100)
        self.quality_level = tk.DoubleVar(value=0.3)
        self.min_distance = tk.IntVar(value=7)
        
        ttk.Label(params_frame, text="Max Corners:").grid(row=0, column=0, sticky="w")
        ttk.Scale(params_frame, from_=10, to=500, variable=self.max_corners, orient=tk.HORIZONTAL).grid(row=0, column=1, sticky="ew")
        ttk.Label(params_frame, textvariable=self.max_corners).grid(row=0, column=2)
        
        ttk.Label(params_frame, text="Quality Level:").grid(row=1, column=0, sticky="w")
        ttk.Scale(params_frame, from_=0.01, to=1.0, variable=self.quality_level, orient=tk.HORIZONTAL).grid(row=1, column=1, sticky="ew")
        ttk.Label(params_frame, textvariable=self.quality_level).grid(row=1, column=2)
        
        params_frame.grid_columnconfigure(1, weight=1)
        
        # Tracking info
        info_frame = ttk.LabelFrame(tab, text="Tracking Info")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.track_info_text = tk.Text(info_frame, height=10, state=tk.DISABLED)
        track_scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.track_info_text.yview)
        self.track_info_text.configure(yscrollcommand=track_scrollbar.set)
        
        self.track_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        track_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def setup_timeline_tab(self):
        """Timeline & Markers tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Timeline & Markers")
        
        # Timeline controls
        timeline_frame = ttk.LabelFrame(tab, text="Timeline Controls")
        timeline_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.timeline_var = tk.IntVar()
        self.timeline_scale = ttk.Scale(timeline_frame, from_=0, to=100, variable=self.timeline_var, 
                                       orient=tk.HORIZONTAL, command=self.seek_frame)
        self.timeline_scale.pack(fill=tk.X, padx=5, pady=5)
        
        # Marker controls
        marker_frame = ttk.LabelFrame(tab, text="Markers")
        marker_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(marker_frame, text="Add Marker", command=self.add_marker).pack(side=tk.LEFT, padx=5)
        ttk.Button(marker_frame, text="Clear Markers", command=self.clear_markers).pack(side=tk.LEFT, padx=5)
        ttk.Button(marker_frame, text="Snapshot Frame", command=self.snapshot_frame).pack(side=tk.LEFT, padx=5)
        
        # Markers list
        markers_list_frame = ttk.LabelFrame(tab, text="Marker List")
        markers_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.markers_listbox = tk.Listbox(markers_list_frame)
        markers_scrollbar = ttk.Scrollbar(markers_list_frame, orient=tk.VERTICAL, command=self.markers_listbox.yview)
        self.markers_listbox.configure(yscrollcommand=markers_scrollbar.set)
        
        self.markers_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        markers_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.markers_listbox.bind('<Double-Button-1>', self.jump_to_marker)
        
    def setup_export_tab(self):
        """Export tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Export")
        
        # Export settings
        settings_frame = ttk.LabelFrame(tab, text="Export Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.export_format = tk.StringVar(value="mp4")
        self.export_quality = tk.IntVar(value=23)
        self.export_fps = tk.DoubleVar(value=30)
        
        ttk.Label(settings_frame, text="Format:").grid(row=0, column=0, sticky="w")
        format_combo = ttk.Combobox(settings_frame, textvariable=self.export_format, values=["mp4", "avi", "mov"])
        format_combo.grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(settings_frame, text="Quality (CRF):").grid(row=1, column=0, sticky="w")
        ttk.Scale(settings_frame, from_=0, to=51, variable=self.export_quality, orient=tk.HORIZONTAL).grid(row=1, column=1, sticky="ew")
        ttk.Label(settings_frame, textvariable=self.export_quality).grid(row=1, column=2)
        
        ttk.Label(settings_frame, text="FPS:").grid(row=2, column=0, sticky="w")
        ttk.Scale(settings_frame, from_=1, to=60, variable=self.export_fps, orient=tk.HORIZONTAL).grid(row=2, column=1, sticky="ew")
        ttk.Label(settings_frame, textvariable=self.export_fps).grid(row=2, column=2)
        
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Export controls
        export_frame = ttk.LabelFrame(tab, text="Export Controls")
        export_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(export_frame, text="Export Video", command=self.export_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="Export Image Sequence", command=self.export_sequence).pack(side=tk.LEFT, padx=5)
        
        # Progress
        progress_frame = ttk.LabelFrame(tab, text="Export Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.export_status_var = tk.StringVar(value="Ready to export")
        ttk.Label(progress_frame, textvariable=self.export_status_var).pack(pady=5)
        
    # Core functionality methods
    
    def open_video(self):
        """Open video file"""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                if self.video_cap:
                    self.video_cap.release()
                
                self.video_cap = cv2.VideoCapture(file_path)
                self.frame_count = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
                
                # Update timeline
                self.timeline_scale.configure(to=self.frame_count-1)
                
                # Load first frame
                self.current_frame_idx = 0
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_cap.read()
                if ret:
                    self.current_frame = frame
                    self.update_preview_display()
                
                # Update metadata
                self.update_metadata()
                self.status_var.set(f"Loaded: {Path(file_path).name}")
                logger.info(f"Loaded video: {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load video: {str(e)}")
                logger.error(f"Failed to load video: {e}")
    
    def update_metadata(self):
        """Update metadata display"""
        if self.video_cap:
            width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = self.frame_count / self.fps if self.fps > 0 else 0
            
            metadata = f"Resolution: {width}x{height}\n"
            metadata += f"FPS: {self.fps:.2f}\n"
            metadata += f"Frames: {self.frame_count}\n"
            metadata += f"Duration: {duration:.2f}s"
            
            self.metadata_text.config(state=tk.NORMAL)
            self.metadata_text.delete(1.0, tk.END)
            self.metadata_text.insert(1.0, metadata)
            self.metadata_text.config(state=tk.DISABLED)
    
    def toggle_playback(self):
        """Toggle play/pause"""
        if not self.video_cap:
            return
        
        self.is_playing = not self.is_playing
        self.play_button.config(text="Pause" if self.is_playing else "Play")
        
        if self.is_playing and not self.preview_thread:
            self.start_preview_thread()
        elif not self.is_playing:
            self.stop_preview_thread()
    
    def start_preview_thread(self):
        """Start preview playback thread"""
        if self.preview_thread and self.preview_thread.is_alive():
            return
        
        self.stop_preview = False
        self.preview_thread = threading.Thread(target=self.preview_loop)
        self.preview_thread.daemon = True
        self.preview_thread.start()
    
    def stop_preview_thread(self):
        """Stop preview thread"""
        self.stop_preview = True
        if self.preview_thread:
            self.preview_thread.join(timeout=1)
    
    def preview_loop(self):
        """Main preview loop"""
        frame_time = 1.0 / self.fps if self.fps > 0 else 1.0/30
        
        while self.is_playing and not self.stop_preview:
            start_time = time.time()
            
            if self.current_frame_idx >= self.frame_count - 1:
                self.is_playing = False
                self.root.after(0, lambda: self.play_button.config(text="Play"))
                break
            
            self.step_frame(1)
            
            # Frame rate limiting
            elapsed = time.time() - start_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
    
    def step_frame(self, delta):
        """Step forward/backward by delta frames"""
        if not self.video_cap:
            return
        
        new_idx = max(0, min(self.frame_count - 1, self.current_frame_idx + delta))
        if new_idx != self.current_frame_idx:
            self.current_frame_idx = new_idx
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
            ret, frame = self.video_cap.read()
            if ret:
                self.current_frame = frame
                self.update_preview_display()
                self.timeline_var.set(self.current_frame_idx)
    
    def seek_frame(self, value):
        """Seek to specific frame"""
        if not self.video_cap:
            return
        
        frame_idx = int(float(value))
        if frame_idx != self.current_frame_idx:
            self.current_frame_idx = frame_idx
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.video_cap.read()
            if ret:
                self.current_frame = frame
                self.update_preview_display()
    
    def apply_effects_pipeline(self, frame):
        """Apply all effects in pipeline"""
        if frame is None:
            return None
        
        processed = frame.copy()
        
        for effect in self.effects_pipeline:
            if effect['type'] == 'canny':
                gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, int(self.canny_low.get()), int(self.canny_high.get()))
                processed = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            
            elif effect['type'] == 'gaussian_blur':
                ksize = int(self.blur_kernel.get())
                if ksize % 2 == 0:
                    ksize += 1
                processed = cv2.GaussianBlur(processed, (ksize, ksize), self.blur_sigma.get())
            
            elif effect['type'] == 'color_adjust':
                processed = cv2.convertScaleAbs(processed, alpha=self.contrast.get(), beta=self.brightness.get())
            
            elif effect['type'] == 'text':
                cv2.putText(processed, self.text_content.get(), (50, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, self.text_size.get()/50.0, (255, 255, 255), 2)
        
        # Apply overlay if present
        if self.overlay_image is not None:
            processed = self.apply_overlay(processed)
        
        # Apply crop if enabled
        if self.crop_enabled.get():
            x, y, w, h = self.crop_x.get(), self.crop_y.get(), self.crop_w.get(), self.crop_h.get()
            processed = processed[y:y+h, x:x+w]
        
        return processed
    
    def apply_overlay(self, frame):
        """Apply overlay image"""
        if self.overlay_image is None:
            return frame
        
        x, y = self.overlay_x.get(), self.overlay_y.get()
        scale = self.overlay_scale.get()
        opacity = self.overlay_opacity.get()
        
        # Resize overlay
        overlay = cv2.resize(self.overlay_image, None, fx=scale, fy=scale)
        h, w = overlay.shape[:2]
        
        # Check bounds
        if x + w > frame.shape[1] or y + h > frame.shape[0] or x < 0 or y < 0:
            return frame
        
        # Apply overlay with alpha blending
        roi = frame[y:y+h, x:x+w]
        result = cv2.addWeighted(roi, 1-opacity, overlay, opacity, 0)
        frame[y:y+h, x:x+w] = result
        
        return frame
    
    def update_preview_display(self):
        """Update preview display"""
        if self.current_frame is None:
            return
        
        # Apply effects
        self.processed_frame = self.apply_effects_pipeline(self.current_frame)
        
        # Scale for preview
        preview_frame = cv2.resize(self.processed_frame, None, fx=self.preview_scale, fy=self.preview_scale)
        
        # Convert to PIL and display
        preview_rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        preview_pil = Image.fromarray(preview_rgb)
        preview_tk = ImageTk.PhotoImage(preview_pil)
        
        self.preview_label.config(image=preview_tk)
        self.preview_label.image = preview_tk
        
        # Update frame info
        time_seconds = self.current_frame_idx / self.fps if self.fps > 0 else 0
        time_str = f"{int(time_seconds//3600):02d}:{int((time_seconds%3600)//60):02d}:{int(time_seconds%60):02d}"
        self.frame_info_var.set(f"Frame: {self.current_frame_idx}/{self.frame_count} | FPS: {self.fps:.1f} | Time: {time_str}")
    
    def update_preview(self, *args):
        """Update preview when parameters change"""
        if self.current_frame is not None:
            self.update_preview_display()
    
    # Effects management
    def add_effect(self, effect_type):
        """Add effect to pipeline"""
        effect = {'type': effect_type, 'enabled': True}
        self.effects_pipeline.append(effect)
        self.update_effects_list()
        self.update_preview()
    
    def remove_effect(self):
        """Remove selected effect"""
        selection = self.effects_listbox.curselection()
        if selection:
            idx = selection[0]
            del self.effects_pipeline[idx]
            self.update_effects_list()
            self.update_preview()
    
    def clear_effects(self):
        """Clear all effects"""
        self.effects_pipeline.clear()
        self.update_effects_list()
        self.update_preview()
    
    def update_effects_list(self):
        """Update effects listbox"""
        self.effects_listbox.delete(0, tk.END)
        for effect in self.effects_pipeline:
            self.effects_listbox.insert(tk.END, f"{effect['type']} ({'ON' if effect['enabled'] else 'OFF'})")
    
    # Overlay management
    def load_overlay(self):
        """Load overlay image"""
        file_path = filedialog.askopenfilename(
            title="Select Overlay Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.overlay_image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if self.overlay_image.shape[2] == 4:  # RGBA
                    self.overlay_image = cv2.cvtColor(self.overlay_image, cv2.COLOR_BGRA2BGR)
                self.status_var.set(f"Loaded overlay: {Path(file_path).name}")
                self.update_preview()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load overlay: {str(e)}")
    
    def clear_overlay(self):
        """Clear overlay"""
        self.overlay_image = None
        self.update_preview()
    
    def update_overlay_params(self, *args):
        """Update overlay parameters"""
        self.overlay_params['x'] = self.overlay_x.get()
        self.overlay_params['y'] = self.overlay_y.get()
        self.overlay_params['opacity'] = self.overlay_opacity.get()
        self.overlay_params['scale'] = self.overlay_scale.get()
        self.update_preview()
    
    # Geometry functions
    def update_crop_params(self, *args):
        """Update crop parameters"""
        self.crop_params['x'] = self.crop_x.get()
        self.crop_params['y'] = self.crop_y.get()
        self.crop_params['w'] = self.crop_w.get()
        self.crop_params['h'] = self.crop_h.get()
        self.crop_params['enabled'] = self.crop_enabled.get()
        self.update_preview()
    
    def set_aspect_ratio(self, w_ratio, h_ratio):
        """Set crop to specific aspect ratio"""
        if not self.current_frame:
            return
        
        frame_h, frame_w = self.current_frame.shape[:2]
        
        # Calculate crop dimensions maintaining aspect ratio
        if frame_w / frame_h > w_ratio / h_ratio:
            # Frame is wider
            new_h = frame_h
            new_w = int(new_h * w_ratio / h_ratio)
            x_offset = (frame_w - new_w) // 2
            y_offset = 0
        else:
            # Frame is taller
            new_w = frame_w
            new_h = int(new_w * h_ratio / w_ratio)
            x_offset = 0
            y_offset = (frame_h - new_h) // 2
        
        self.crop_x.set(x_offset)
        self.crop_y.set(y_offset)
        self.crop_w.set(new_w)
        self.crop_h.set(new_h)
        self.crop_enabled.set(True)
        self.update_preview()
    
    # Tracking functions
    def auto_detect_features(self):
        """Auto detect features for tracking"""
        if self.current_frame is None:
            return
        
        gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
        corners = cv2.goodFeaturesToTrack(gray, maxCorners=self.max_corners.get(), 
                                          qualityLevel=self.quality_level.get(),
                                          minDistance=self.min_distance.get(), blockSize=7)
        
        if corners is not None:
            self.track_points = corners.reshape(-1, 1, 2).astype(np.float32)
            self.update_track_info()
            self.status_var.set(f"Detected {len(self.track_points)} features")
    
    def clear_tracks(self):
        """Clear all tracking points"""
        self.track_points = []
        self.update_track_info()
    
    def update_track_info(self):
        """Update tracking info display"""
        self.track_info_text.config(state=tk.NORMAL)
        self.track_info_text.delete(1.0, tk.END)
        
        if self.track_points:
            info = f"Tracking {len(self.track_points)} points:\n\n"
            for i, point in enumerate(self.track_points[:10]):  # Show first 10
                x, y = point[0]
                info += f"Point {i+1}: ({x:.1f}, {y:.1f})\n"
            if len(self.track_points) > 10:
                info += f"... and {len(self.track_points) - 10} more points"
        else:
            info = "No tracking points detected"
        
        self.track_info_text.insert(1.0, info)
        self.track_info_text.config(state=tk.DISABLED)
    
    def export_tracks(self):
        """Export tracks to CSV"""
        if not self.track_points:
            messagebox.showwarning("Warning", "No tracking points to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Tracks",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['frame', 'point_id', 'x', 'y'])
                    for i, point in enumerate(self.track_points):
                        x, y = point[0]
                        writer.writerow([self.current_frame_idx, i, x, y])
                
                self.status_var.set(f"Exported tracks to {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export tracks: {str(e)}")
    
    # Timeline functions
    def add_marker(self):
        """Add marker at current frame"""
        if not self.video_cap:
            return
        
        name = simpledialog.askstring("Marker Name", "Enter marker name:")
        if name:
            marker = {'frame': self.current_frame_idx, 'name': name}
            self.markers.append(marker)
            self.update_markers_list()
    
    def clear_markers(self):
        """Clear all markers"""
        self.markers.clear()
        self.update_markers_list()
    
    def update_markers_list(self):
        """Update markers listbox"""
        self.markers_listbox.delete(0, tk.END)
        for marker in sorted(self.markers, key=lambda x: x['frame']):
            time_seconds = marker['frame'] / self.fps if self.fps > 0 else 0
            time_str = f"{int(time_seconds//60):02d}:{int(time_seconds%60):02d}"
            self.markers_listbox.insert(tk.END, f"Frame {marker['frame']} ({time_str}) - {marker['name']}")
    
    def jump_to_marker(self, event):
        """Jump to selected marker"""
        selection = self.markers_listbox.curselection()
        if selection:
            marker = sorted(self.markers, key=lambda x: x['frame'])[selection[0]]
            self.current_frame_idx = marker['frame']
            self.timeline_var.set(self.current_frame_idx)
            self.seek_frame(self.current_frame_idx)
    
    def snapshot_frame(self):
        """Save snapshot of current processed frame"""
        if self.processed_frame is None:
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Snapshot",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, self.processed_frame)
                self.status_var.set(f"Saved snapshot: {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save snapshot: {str(e)}")
    
    # Export functions
    def export_video(self):
        """Export processed video"""
        if not self.video_cap:
            messagebox.showwarning("Warning", "No video loaded")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Video",
            defaultextension=f".{self.export_format.get()}",
            filetypes=[("Video files", f"*.{self.export_format.get()}"), ("All files", "*.*")]
        )
        
        if file_path:
            threading.Thread(target=self._export_video_worker, args=(file_path,), daemon=True).start()
    
    def _export_video_worker(self, output_path):
        """Export video worker thread"""
        try:
            # Get video properties
            frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if self.crop_enabled.get():
                frame_width = self.crop_w.get()
                frame_height = self.crop_h.get()
            
            # Setup video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, self.export_fps.get(), (frame_width, frame_height))
            
            self.root.after(0, lambda: self.export_status_var.set("Exporting..."))
            
            # Process all frames
            for frame_idx in range(self.frame_count):
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = self.video_cap.read()
                
                if ret:
                    processed = self.apply_effects_pipeline(frame)
                    out.write(processed)
                
                # Update progress
                progress = (frame_idx / self.frame_count) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
            
            out.release()
            self.root.after(0, lambda: self.export_status_var.set(f"Export complete: {Path(output_path).name}"))
            self.root.after(0, lambda: self.progress_var.set(0))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
            self.root.after(0, lambda: self.export_status_var.set("Export failed"))
    
    def export_sequence(self):
        """Export as image sequence"""
        if not self.video_cap:
            messagebox.showwarning("Warning", "No video loaded")
            return
        
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        if folder_path:
            threading.Thread(target=self._export_sequence_worker, args=(folder_path,), daemon=True).start()
    
    def _export_sequence_worker(self, output_folder):
        """Export sequence worker thread"""
        try:
            self.root.after(0, lambda: self.export_status_var.set("Exporting sequence..."))
            
            for frame_idx in range(self.frame_count):
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = self.video_cap.read()
                
                if ret:
                    processed = self.apply_effects_pipeline(frame)
                    filename = f"frame_{frame_idx:06d}.png"
                    filepath = os.path.join(output_folder, filename)
                    cv2.imwrite(filepath, processed)
                
                # Update progress
                progress = (frame_idx / self.frame_count) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
            
            self.root.after(0, lambda: self.export_status_var.set("Sequence export complete"))
            self.root.after(0, lambda: self.progress_var.set(0))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
            self.root.after(0, lambda: self.export_status_var.set("Export failed"))
    
    # Project management
    def save_project(self):
        """Save project to JSON"""
        file_path = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".vproj",
            filetypes=[("Video Project files", "*.vproj"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                project_data = {
                    'effects_pipeline': self.effects_pipeline,
                    'overlay_params': self.overlay_params,
                    'crop_params': self.crop_params,
                    'markers': self.markers,
                    'parameters': {
                        'canny_low': self.canny_low.get(),
                        'canny_high': self.canny_high.get(),
                        'blur_kernel': self.blur_kernel.get(),
                        'blur_sigma': self.blur_sigma.get(),
                        'brightness': self.brightness.get(),
                        'contrast': self.contrast.get(),
                        'text_content': self.text_content.get(),
                        'text_size': self.text_size.get()
                    }
                }
                
                with open(file_path, 'w') as f:
                    json.dump(project_data, f, indent=2)
                
                self.project_path = file_path
                self.status_var.set(f"Project saved: {Path(file_path).name}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save project: {str(e)}")
    
    def load_project(self):
        """Load project from JSON"""
        file_path = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("Video Project files", "*.vproj"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    project_data = json.load(f)
                
                # Restore data
                self.effects_pipeline = project_data.get('effects_pipeline', [])
                self.overlay_params = project_data.get('overlay_params', self.overlay_params)
                self.crop_params = project_data.get('crop_params', self.crop_params)
                self.markers = project_data.get('markers', [])
                
                # Restore parameters
                params = project_data.get('parameters', {})
                self.canny_low.set(params.get('canny_low', 50))
                self.canny_high.set(params.get('canny_high', 150))
                self.blur_kernel.set(params.get('blur_kernel', 5))
                self.blur_sigma.set(params.get('blur_sigma', 1.0))
                self.brightness.set(params.get('brightness', 0))
                self.contrast.set(params.get('contrast', 1.0))
                self.text_content.set(params.get('text_content', 'Sample Text'))
                self.text_size.set(params.get('text_size', 30))
                
                # Update UI
                self.update_effects_list()
                self.update_markers_list()
                self.update_preview()
                
                self.project_path = file_path
                self.status_var.set(f"Project loaded: {Path(file_path).name}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load project: {str(e)}")
    
    def open_sequence(self):
        """Open image sequence (placeholder)"""
        messagebox.showinfo("Info", "Image sequence loading not implemented in beta")
    
    def run(self):
        """Start the application"""
        self.root.mainloop()
        
        # Cleanup
        if self.video_cap:
            self.video_cap.release()
        cv2.destroyAllWindows()


def main():
    """Main entry point"""
    try:
        app = VideoLabPro()
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")


if __name__ == "__main__":
    main()
