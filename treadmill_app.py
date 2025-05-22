import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
import asyncio
import time
from bleak import BleakClient, BleakScanner
from datetime import datetime, timedelta
import threading
import logging
import json
import os
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from dateutil.relativedelta import relativedelta
import calendar

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# BLE Configuration
WALKPAD_ADDRESS = "69:82:20:D3:DE:C7"
TREADMILL_DATA_UUID = "00002acd-0000-1000-8000-00805f9b34fb"
CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"

# Define modern color scheme
COLORS = {
    'primary': '#4F6BED',  # Blue
    'secondary': '#48C1A3',  # Teal
    'background': '#F5F7FA',  # Light Gray
    'text': '#2D3748',  # Dark Gray
    'warning': '#F6AD55',  # Orange
    'error': '#E53E3E',  # Red
    'success': '#48BB78',  # Green
    'chart_colors': ['#4F6BED', '#48C1A3', '#F6AD55', '#E53E3E', '#805AD5', '#ED64A6']
}

class TextHandler(logging.Handler):
    """Custom logging handler that writes logs to a Tkinter Text widget."""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        # Configure the Text widget to be read-only
        self.text_widget.configure(state='disabled')
        # Add a tag for different log levels
        self.text_widget.tag_config('DEBUG', foreground='gray')
        self.text_widget.tag_config('INFO', foreground=COLORS['text'])
        self.text_widget.tag_config('WARNING', foreground=COLORS['warning'])
        self.text_widget.tag_config('ERROR', foreground=COLORS['error'])
        self.text_widget.tag_config('CRITICAL', foreground=COLORS['error'], underline=1)

    def emit(self, record):
        msg = self.format(record)
        # Enable the Text widget to insert log
        self.text_widget.configure(state='normal')
        # Insert the log message at the end
        self.text_widget.insert(tk.END, msg + '\n', record.levelname)
        # Auto-scroll to the end
        self.text_widget.yview(tk.END)
        # Disable the Text widget to make it read-only
        self.text_widget.configure(state='disabled')

class TreadmillApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Treadmill Control")
        # Make UI a bit larger/prettier:
        self.root.geometry("800x980")  # Increased size for more content
        self.root.configure(bg=COLORS['background'])
        
        # Set custom style
        self.setup_styles()

        # Variables
        self.client = None
        self.connected = False
        self.current_speed = 0.0
        self.total_distance = 0.0
        self.steps = 0
        self.start_time = None
        self.running_time = "00:00:00"
        self.current_workout = None
        self.workouts_file = r"F:\Sell everything\Laufband\treadmill_workouts.json"  # Original path
        self.db_file = "treadmill_workouts.db"
        self.setup_database()
        self.load_workouts()  # Load existing workouts from the database
        self.is_running = False
        self.last_step_update = datetime.now()
        self.speed_above_zero_time = None
        
        # Date filters
        self.selected_timeframe = tk.StringVar(value="All Time")
        self.filter_start_date = None
        self.filter_end_date = datetime.now()

        self.setup_ui()

        # Start async event loop in a separate thread
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.run_event_loop, daemon=True).start()

        # Schedule logging initialization after the main loop starts
        self.root.after(100, self.initialize_logging)

    def setup_styles(self):
        """Set up custom ttk styles for a modern look"""
        style = ttk.Style()
        
        # Configure the theme - if 'clam' is available, use it for more control
        try:
            style.theme_use('clam')
        except:
            pass  # Use default theme if clam is not available
        
        # Button style
        style.configure('TButton', 
                       font=('Segoe UI', 10),
                       background=COLORS['primary'],
                       foreground=COLORS['background'],
                       padding=5)
        
        # Accent button style
        style.configure('Accent.TButton', 
                       background=COLORS['secondary'],
                       foreground=COLORS['background'])
        
        # Label style
        style.configure('TLabel', 
                       font=('Segoe UI', 10),
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        # Header label style
        style.configure('Header.TLabel', 
                       font=('Segoe UI', 12, 'bold'),
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        # Value label style
        style.configure('Value.TLabel', 
                       font=('Segoe UI', 11, 'bold'),
                       background=COLORS['background'],
                       foreground=COLORS['primary'])
        
        # Frame style
        style.configure('TFrame', background=COLORS['background'])
        
        # LabelFrame style
        style.configure('TLabelframe', 
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        style.configure('TLabelframe.Label', 
                       font=('Segoe UI', 11, 'bold'),
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        # Notebook style
        style.configure('TNotebook', 
                       background=COLORS['background'],
                       tabposition='n')
        
        style.configure('TNotebook.Tab', 
                       font=('Segoe UI', 10),
                       padding=[10, 4],
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        style.map('TNotebook.Tab', 
                 background=[('selected', COLORS['primary'])],
                 foreground=[('selected', 'white')])

    def initialize_logging(self):
        """Initialize the logging handler after the UI is set up."""
        log_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(log_handler)

    def setup_ui(self):
        # Main container frame with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # App title
        title_label = ttk.Label(main_frame, text="Treadmill Control Dashboard", 
                               font=('Segoe UI', 16, 'bold'), 
                               foreground=COLORS['primary'])
        title_label.pack(pady=(0, 15))

        # Frame for the top row of buttons
        control_buttons_frame = ttk.Frame(main_frame, padding="10")
        control_buttons_frame.pack(fill=tk.X, pady=5)

        # Add a more modern appearance to buttons
        self.start_btn = ttk.Button(control_buttons_frame, text="Start Workout", 
                                   command=self.start_workout_session, width=15)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.stop_btn = ttk.Button(control_buttons_frame, text="Stop Workout", 
                                  command=self.stop_workout_session, width=15)
        self.stop_btn.grid(row=0, column=1, padx=5)
        self.stop_btn.config(state='disabled')  # Disabled at start

        # Add a button for manual workout logging
        self.manual_log_btn = ttk.Button(control_buttons_frame, text="Log Workout", 
                                        command=self.manual_log_workout, width=15,
                                        style='Accent.TButton')
        self.manual_log_btn.grid(row=0, column=2, padx=5)

        # Connection frame
        conn_frame = ttk.Frame(main_frame, padding="10")
        conn_frame.pack(fill=tk.X, pady=5)

        self.conn_btn = ttk.Button(conn_frame, text="Connect to Device", 
                                  command=self.toggle_connection, width=20)
        self.conn_btn.grid(row=0, column=0, padx=5)

        status_frame = ttk.Frame(conn_frame, padding=5)
        status_frame.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(status_frame, text="Status:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, text="Disconnected", 
                                     foreground='#E53E3E', font=('Segoe UI', 10, 'bold'))
        self.status_label.grid(row=0, column=1, padx=5, sticky=tk.W)

        # Create a 2-column layout
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left column - Current workout data and controls
        left_col = ttk.Frame(content_frame, padding=10)
        left_col.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(0, 10))
        
        # Stats Frame with a more modern design
        stats_frame = ttk.LabelFrame(left_col, text="Current Workout", padding="15")
        stats_frame.pack(fill=tk.X, pady=10)

        # Speed display
        ttk.Label(stats_frame, text="Speed:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W, pady=5)
        self.speed_label = ttk.Label(stats_frame, text="0.0 km/h", style='Value.TLabel')
        self.speed_label.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Distance display
        ttk.Label(stats_frame, text="Distance:", style='Header.TLabel').grid(row=1, column=0, sticky=tk.W, pady=5)
        self.distance_label = ttk.Label(stats_frame, text="0.00 km", style='Value.TLabel')
        self.distance_label.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Steps display
        ttk.Label(stats_frame, text="Steps:", style='Header.TLabel').grid(row=2, column=0, sticky=tk.W, pady=5)
        self.steps_label = ttk.Label(stats_frame, text="0", style='Value.TLabel')
        self.steps_label.grid(row=2, column=1, sticky=tk.W, pady=5)

        # Time display
        ttk.Label(stats_frame, text="Time:", style='Header.TLabel').grid(row=3, column=0, sticky=tk.W, pady=5)
        self.time_label = ttk.Label(stats_frame, text="00:00:00", style='Value.TLabel')
        self.time_label.grid(row=3, column=1, sticky=tk.W, pady=5)

        # Speed Control Frame
        control_frame = ttk.LabelFrame(left_col, text="Speed Control", padding="15")
        control_frame.pack(fill=tk.X, pady=10)

        # Speed buttons in a grid layout
        speeds_frame = ttk.Frame(control_frame)
        speeds_frame.pack(fill=tk.X, pady=5)
        
        speeds = [1, 2, 3, 4]  # Added one more speed
        for i, speed in enumerate(speeds):
            btn = ttk.Button(speeds_frame, text=f"{speed} km/h",
                            command=lambda s=speed: self.set_speed(s),
                            width=8)
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Fine Speed Control
        fine_control_frame = ttk.LabelFrame(left_col, text="Fine Speed Control", padding="15")
        fine_control_frame.pack(fill=tk.X, pady=10)

        fine_speeds_frame = ttk.Frame(fine_control_frame)
        fine_speeds_frame.pack(fill=tk.X, pady=5)
        
        fine_speeds = [-0.5, -0.2, 0.2, 0.5]  # More fine-grained control
        for i, speed in enumerate(fine_speeds):
            btn = ttk.Button(fine_speeds_frame, text=f"{speed:+.1f} km/h",
                            command=lambda s=speed: self.adjust_speed(s),
                            width=8)
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Right column - Statistics
        right_col = ttk.Frame(content_frame, padding=10)
        right_col.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S))
        
        # Timeframe selection
        timeframe_frame = ttk.Frame(right_col)
        timeframe_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(timeframe_frame, text="Timeframe:", style='Header.TLabel').grid(row=0, column=0, padx=(0, 10))
        timeframe_options = ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "This Year"]
        timeframe_dropdown = ttk.Combobox(timeframe_frame, textvariable=self.selected_timeframe, 
                                         values=timeframe_options, width=15)
        timeframe_dropdown.grid(row=0, column=1)
        timeframe_dropdown.bind("<<ComboboxSelected>>", self.update_timeframe)

        # Workout Statistics Notebook with charts
        stats_notebook_frame = ttk.LabelFrame(right_col, text="Workout Statistics", padding="10")
        stats_notebook_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.stats_notebook = ttk.Notebook(stats_notebook_frame)
        self.stats_notebook.pack(fill=tk.BOTH, expand=True)

        # Create frames for each tab
        self.day_frame = ttk.Frame(self.stats_notebook, padding="10")
        self.week_frame = ttk.Frame(self.stats_notebook, padding="10")
        self.month_frame = ttk.Frame(self.stats_notebook, padding="10")
        self.total_frame = ttk.Frame(self.stats_notebook, padding="10")
        self.logs_frame = ttk.Frame(self.stats_notebook, padding="10")

        # Add tabs to notebook
        self.stats_notebook.add(self.day_frame, text="Daily")
        self.stats_notebook.add(self.week_frame, text="Weekly")
        self.stats_notebook.add(self.month_frame, text="Monthly")
        self.stats_notebook.add(self.total_frame, text="Total")
        self.stats_notebook.add(self.logs_frame, text="Logs")

        # Setup each tab
        self.setup_day_tab()
        self.setup_week_tab()
        self.setup_month_tab()
        self.setup_total_tab()
        self.setup_logs_tab()
        
        # Bind tab change to update the charts
        self.stats_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def setup_day_tab(self):
        """Set up the Day tab with summary stats and last 7 days chart"""
        # Create a frame for summary stats
        summary_frame = ttk.Frame(self.day_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a grid for summary stats
        ttk.Label(summary_frame, text="Total Distance:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W, pady=2)
        self.day_distance_label = ttk.Label(summary_frame, text="0.00 km", style='Value.TLabel')
        self.day_distance_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Time:", style='Header.TLabel').grid(row=1, column=0, sticky=tk.W, pady=2)
        self.day_time_label = ttk.Label(summary_frame, text="00:00:00", style='Value.TLabel')
        self.day_time_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Steps:", style='Header.TLabel').grid(row=2, column=0, sticky=tk.W, pady=2)
        self.day_steps_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.day_steps_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Workouts:", style='Header.TLabel').grid(row=3, column=0, sticky=tk.W, pady=2)
        self.day_workouts_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.day_workouts_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Create frame for the chart
        chart_frame = ttk.LabelFrame(self.day_frame, text="Last 7 Days Steps", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a figure for the chart
        self.day_fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.day_ax = self.day_fig.add_subplot(111)
        
        # Create the canvas and add it to the frame
        self.day_canvas = FigureCanvasTkAgg(self.day_fig, master=chart_frame)
        self.day_canvas.draw()
        self.day_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial chart setup
        self.update_day_chart()

    def setup_week_tab(self):
        """Set up the Week tab with summary stats and last 4 weeks chart"""
        # Create a frame for summary stats
        summary_frame = ttk.Frame(self.week_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a grid for summary stats
        ttk.Label(summary_frame, text="Total Distance:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W, pady=2)
        self.week_distance_label = ttk.Label(summary_frame, text="0.00 km", style='Value.TLabel')
        self.week_distance_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Time:", style='Header.TLabel').grid(row=1, column=0, sticky=tk.W, pady=2)
        self.week_time_label = ttk.Label(summary_frame, text="00:00:00", style='Value.TLabel')
        self.week_time_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Steps:", style='Header.TLabel').grid(row=2, column=0, sticky=tk.W, pady=2)
        self.week_steps_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.week_steps_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Workouts:", style='Header.TLabel').grid(row=3, column=0, sticky=tk.W, pady=2)
        self.week_workouts_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.week_workouts_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Create frame for the chart
        chart_frame = ttk.LabelFrame(self.week_frame, text="Last 4 Weeks", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a figure for the chart
        self.week_fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.week_ax = self.week_fig.add_subplot(111)
        
        # Create the canvas and add it to the frame
        self.week_canvas = FigureCanvasTkAgg(self.week_fig, master=chart_frame)
        self.week_canvas.draw()
        self.week_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial chart setup
        self.update_week_chart()

    def setup_month_tab(self):
        """Set up the Month tab with summary stats and last 6 months chart"""
        # Create a frame for summary stats
        summary_frame = ttk.Frame(self.month_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create a grid for summary stats
        ttk.Label(summary_frame, text="Total Distance:", style='Header.TLabel').grid(row=0, column=0, sticky=tk.W, pady=2)
        self.month_distance_label = ttk.Label(summary_frame, text="0.00 km", style='Value.TLabel')
        self.month_distance_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Time:", style='Header.TLabel').grid(row=1, column=0, sticky=tk.W, pady=2)
        self.month_time_label = ttk.Label(summary_frame, text="00:00:00", style='Value.TLabel')
        self.month_time_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Total Steps:", style='Header.TLabel').grid(row=2, column=0, sticky=tk.W, pady=2)
        self.month_steps_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.month_steps_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(summary_frame, text="Workouts:", style='Header.TLabel').grid(row=3, column=0, sticky=tk.W, pady=2)
        self.month_workouts_label = ttk.Label(summary_frame, text="0", style='Value.TLabel')
        self.month_workouts_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Create frame for the chart
        chart_frame = ttk.LabelFrame(self.month_frame, text="Last 6 Months", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a figure for the chart
        self.month_fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.month_ax = self.month_fig.add_subplot(111)
        
        # Create the canvas and add it to the frame
        self.month_canvas = FigureCanvasTkAgg(self.month_fig, master=chart_frame)
        self.month_canvas.draw()
        self.month_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial chart setup
        self.update_month_chart()

    def setup_total_tab(self):
        """Set up the Total tab with overall stats"""
        # Create a frame for summary stats with a more visual layout
        summary_frame = ttk.Frame(self.total_frame)
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create a grid with more spacing and larger fonts
        stats = [
            ("Total Distance", "0.00 km", "total_distance_label"),
            ("Total Time", "00:00:00", "total_time_label"),
            ("Total Steps", "0", "total_steps_label"),
            ("Total Workouts", "0", "total_workouts_label"),
            ("Average Distance per Day", "0.00 km", "avg_distance_label"),
            ("Average Steps per Day", "0", "avg_steps_label"),
            ("Days with Workouts", "0%", "days_with_workouts_label"),
            ("First Workout", "Never", "first_workout_label"),
            ("Last Workout", "Never", "last_workout_label")
        ]
        
        # Create the stat boxes in a grid
        for i, (label, default, attr_name) in enumerate(stats):
            row, col = divmod(i, 2)
            
            # Create a frame for each stat for better styling
            stat_frame = ttk.Frame(summary_frame, padding=10)
            stat_frame.grid(row=row, column=col, padx=10, pady=10, sticky=(tk.W, tk.E))
            
            ttk.Label(stat_frame, text=label, style='Header.TLabel').pack(anchor=tk.W)
            value_label = ttk.Label(stat_frame, text=default, 
                                  style='Value.TLabel', font=('Segoe UI', 14, 'bold'))
            value_label.pack(anchor=tk.W, pady=(5, 0))
            
            # Store the label reference
            setattr(self, attr_name, value_label)

    def setup_logs_tab(self):
        """Set up the Logs tab with a ScrolledText widget."""
        # Create a ScrolledText widget with improved styling
        self.log_text = scrolledtext.ScrolledText(
            self.logs_frame, 
            wrap='word', 
            height=20,
            font=('Consolas', 9),
            background='#f8f9fa',
            foreground=COLORS['text']
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def update_timeframe(self, event=None):
        """Update the date filter based on selected timeframe"""
        today = datetime.now()
        timeframe = self.selected_timeframe.get()
        
        if timeframe == "All Time":
            self.filter_start_date = None
        elif timeframe == "Last 7 Days":
            self.filter_start_date = today - timedelta(days=7)
        elif timeframe == "Last 30 Days":
            self.filter_start_date = today - timedelta(days=30)
        elif timeframe == "Last 90 Days":
            self.filter_start_date = today - timedelta(days=90)
        elif timeframe == "This Year":
            self.filter_start_date = datetime(today.year, 1, 1)
            
        self.filter_end_date = today
        
        # Update statistics and charts
        self.update_statistics()
        self.update_all_charts()

    def on_tab_changed(self, event=None):
        """Update charts when changing tabs"""
        current_tab = self.stats_notebook.select()
        tab_name = self.stats_notebook.tab(current_tab, "text")
        
        if tab_name == "Daily":
            self.update_day_chart()
        elif tab_name == "Weekly":
            self.update_week_chart()
        elif tab_name == "Monthly":
            self.update_month_chart()

    def update_all_charts(self):
        """Update all charts at once"""
        self.update_day_chart()
        self.update_week_chart()
        self.update_month_chart()

    def update_day_chart(self):
        """Update the daily chart with last 7 days data"""
        self.day_ax.clear()
        
        # Get the last 7 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        
        # Create a dictionary to store data for each day
        daily_data = {}
        for i in range(7):
            day = start_date + timedelta(days=i)
            daily_data[day] = 0
        
        # Filter workouts by the timeframe
        filtered_workouts = self.get_filtered_workouts()
        
        # Populate data
        for workout in filtered_workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if start_date <= workout_date <= end_date:
                daily_data[workout_date] += workout['steps']
        
        # Prepare data for plotting
        dates = list(daily_data.keys())
        steps = list(daily_data.values())
        
        # Create a better-looking bar chart
        bars = self.day_ax.bar(
            dates, 
            steps, 
            color=COLORS['primary'],
            alpha=0.8,
            width=0.6
        )
        
        # Add data labels on top of bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                # Format steps with better human-readable format
                steps_str = self.format_steps(height)
                self.day_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 5,
                    steps_str,
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
                
        # Customize the chart
        self.day_ax.set_ylabel('Steps')
        self.day_ax.set_title('Daily Steps for the Last 7 Days')
        
        # Format x-axis to show day names
        self.day_ax.xaxis.set_major_formatter(mdates.DateFormatter('%a\n%d-%m'))
        
        # Add grid for better readability
        self.day_ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Adjust layout and redraw
        self.day_fig.tight_layout()
        self.day_canvas.draw()

    def handle_treadmill_data(self, _, data: bytearray):
        """
        Decode treadmill data to get the speed, then start or stop the workout:
        - If speed > 0 for 2 seconds, start the workout.
        - If speed == 0 for 2 seconds, stop the workout and save it to the database.
        """
        try:
            if len(data) >= 4:
                # Bytes [2..3] are speed in 0.01 km/h
                speed_raw = int.from_bytes(data[2:4], byteorder='little')
                new_speed = speed_raw / 100.0
                self.current_speed = new_speed

                # Start workout automatically if speed > 0 for 2 seconds and we are not yet "running"
                if self.current_speed > 0.0:
                    if not self.is_running:
                        if self.speed_above_zero_time is None:
                            self.speed_above_zero_time = datetime.now()
                        elif (datetime.now() - self.speed_above_zero_time).seconds >= 2:
                            self.is_running = True
                            self.start_time = datetime.now()
                            self.start_workout()
                            logging.debug("Workout started")
                    else:
                        self.speed_above_zero_time = None

                # End workout automatically if speed == 0 for 2 seconds and we are currently "running"
                elif self.current_speed == 0.0:
                    if self.is_running:
                        if self.speed_above_zero_time is None:
                            self.speed_above_zero_time = datetime.now()
                        elif (datetime.now() - self.speed_above_zero_time).seconds >= 2:
                            self.is_running = False
                            self.stop_workout()
                            logging.debug("Workout stopped")
                            self.reset_counters()
                    else:
                        self.speed_above_zero_time = None

        except Exception as e:
            logging.error(f"Error parsing data: {e}")

    def setup_database(self):
        """Set up the SQLite database and create the workouts table if it doesn't exist."""
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)  # Allow connections from different threads
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT,
                end_time TEXT,
                distance REAL,
                steps INTEGER,
                duration INTEGER,
                synced BOOLEAN
            )
        ''')
        self.conn.commit()

    def get_db_connection(self):
        """Get a new database connection for the current thread."""
        return sqlite3.connect(self.db_file, check_same_thread=False)

    def load_workouts(self):
        """Load workouts from the database."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        self.workouts = []
        cursor.execute("SELECT * FROM workouts")
        rows = cursor.fetchall()
        for row in rows:
            workout = {
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'distance': row[3],
                'steps': row[4],
                'duration': row[5],
                'synced': row[6]
            }
            self.workouts.append(workout)
        conn.close()

    def update_week_chart(self):
        """Update the week chart with last 4 weeks data"""
        self.week_ax.clear()
        
        # Get the date range for the last 4 weeks
        end_date = datetime.now().date()
        start_date = end_date - timedelta(weeks=4)
        
        # Create weekly buckets
        weekly_data = {}
        for i in range(4):
            week_start = end_date - timedelta(weeks=4-i)
            week_end = week_start + timedelta(days=6)
            week_label = f"{week_start.strftime('%d %b')}-{week_end.strftime('%d %b')}"
            weekly_data[week_label] = {
                'steps': 0,
                'distance': 0,
                'start_date': week_start,
                'end_date': week_end
            }
            
        # Filter workouts by the timeframe
        filtered_workouts = self.get_filtered_workouts()
        
        # Populate data
        for workout in filtered_workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if workout_date >= start_date:
                # Find which week this workout belongs to
                for week_label, week_data in weekly_data.items():
                    if week_data['start_date'] <= workout_date <= week_data['end_date']:
                        weekly_data[week_label]['steps'] += workout['steps']
                        weekly_data[week_label]['distance'] += workout['distance']
        
        # Prepare data for plotting
        week_labels = list(weekly_data.keys())
        steps = [data['steps'] for data in weekly_data.values()]
        
        # Create the bar chart
        bars = self.week_ax.bar(
            week_labels, 
            steps, 
            color=COLORS['secondary'],
            alpha=0.8,
            width=0.6
        )
        
        # Add data labels on top of bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                # Format steps with better human-readable format
                steps_str = self.format_steps(height)
                self.week_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 5,
                    steps_str,
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
        
        # Customize the chart
        self.week_ax.set_ylabel('Steps')
        self.week_ax.set_title('Weekly Steps for the Last 4 Weeks')
        
        # Rotate x-axis labels for better fit
        plt.setp(self.week_ax.get_xticklabels(), rotation=45, ha='right')
        
        # Add grid for better readability
        self.week_ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Adjust layout and redraw
        self.week_fig.tight_layout()
        self.week_canvas.draw()

    def update_month_chart(self):
        """Update the month chart with last 6 months data"""
        self.month_ax.clear()
        
        # Get the date range for the last 6 months
        today = datetime.now()
        end_date = today.date()
        start_date = (today - relativedelta(months=5)).replace(day=1).date()
        
        # Create monthly buckets
        monthly_data = {}
        current_date = start_date
        while current_date <= end_date:
            month_label = current_date.strftime('%b %Y')
            monthly_data[month_label] = {
                'steps': 0,
                'distance': 0,
                'month': current_date.month,
                'year': current_date.year
            }
            # Move to next month
            current_date = (datetime(current_date.year, current_date.month, 1) + relativedelta(months=1)).date()
        
        # Filter workouts by the timeframe
        filtered_workouts = self.get_filtered_workouts()
        
        # Populate data
        for workout in filtered_workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if workout_date >= start_date:
                month_label = workout_date.strftime('%b %Y')
                if month_label in monthly_data:
                    monthly_data[month_label]['steps'] += workout['steps']
                    monthly_data[month_label]['distance'] += workout['distance']
        
        # Prepare data for plotting
        month_labels = list(monthly_data.keys())
        steps = [data['steps'] for data in monthly_data.values()]
        
        # Create the bar chart
        bars = self.month_ax.bar(
            month_labels, 
            steps, 
            color=COLORS['primary'],
            alpha=0.8,
            width=0.6
        )
        
        # Add data labels on top of bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                # Format steps with better human-readable format
                steps_str = self.format_steps(height)
                self.month_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 5,
                    steps_str,
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
        
        # Customize the chart
        self.month_ax.set_ylabel('Steps')
        self.month_ax.set_title('Monthly Steps for the Last 6 Months')
        
        # Add grid for better readability
        self.month_ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Adjust layout and redraw
        self.month_fig.tight_layout()
        self.month_canvas.draw()

    def get_filtered_workouts(self):
        """Filter workouts based on the selected timeframe"""
        if not self.filter_start_date:
            return self.workouts
            
        filtered = []
        for workout in self.workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if self.filter_start_date <= workout_date <= self.filter_end_date:
                filtered.append(workout)
                
        return filtered

    def update_statistics(self):
        """Update all statistics based on the filtered workouts"""
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # Get filtered workouts
        filtered_workouts = self.get_filtered_workouts()

        # Filter workouts for different periods
        today_workouts = [
            w for w in filtered_workouts
            if datetime.fromisoformat(w['start_time']).date() == today
        ]
        week_workouts = [
            w for w in filtered_workouts
            if datetime.fromisoformat(w['start_time']).date() >= week_start
        ]
        month_workouts = [
            w for w in filtered_workouts
            if datetime.fromisoformat(w['start_time']).date() >= month_start
        ]

        # Update statistics for each period
        self.update_period_stats(today_workouts, "day")
        self.update_period_stats(week_workouts, "week")
        self.update_period_stats(month_workouts, "month")
        self.update_period_stats(filtered_workouts, "total")  # Update total statistics
        
        # Update total statistics details
        self.update_total_stats_details(filtered_workouts)

    def update_period_stats(self, workouts, period):
        """Update statistics for a specific time period"""
        total_distance = sum(w['distance'] for w in workouts)
        total_steps = sum(w['steps'] for w in workouts)
        total_duration = sum(w['duration'] for w in workouts)

        # Format time
        days, remainder = divmod(total_duration, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        time_str = ""
        if days > 0:
            time_str += f"{days}d "
        if hours > 0:
            time_str += f"{hours}h "
        if minutes > 0:
            time_str += f"{minutes}min"
        if not time_str:
            time_str = "0min"

        # Format steps with better human-readable format
        steps_str = self.format_steps(total_steps)

        # Update UI labels
        getattr(self, f"{period}_distance_label").config(text=f"{total_distance:.2f} km")
        getattr(self, f"{period}_time_label").config(text=time_str)
        getattr(self, f"{period}_steps_label").config(text=steps_str)
        getattr(self, f"{period}_workouts_label").config(text=str(len(workouts)))

    def update_total_stats_details(self, filtered_workouts):
        """Update the additional details in the total stats tab"""
        if not filtered_workouts:
            # If no workouts, set default values
            self.avg_distance_label.config(text="0.00 km")
            self.avg_steps_label.config(text="0")
            self.days_with_workouts_label.config(text="0%")
            self.first_workout_label.config(text="Never")
            self.last_workout_label.config(text="Never")
            return
            
        # Calculate totals
        total_workouts = len(filtered_workouts)
        total_distance = sum(w['distance'] for w in filtered_workouts)
        total_steps = sum(w['steps'] for w in filtered_workouts)

        # Find first and last workout dates
        sorted_workouts = sorted(filtered_workouts, key=lambda w: w['start_time'])
        first_workout = datetime.fromisoformat(sorted_workouts[0]['start_time'])
        last_workout = datetime.fromisoformat(sorted_workouts[-1]['start_time'])

        # Calculate the number of days since the first workout
        total_days = (last_workout.date() - first_workout.date()).days + 1

        # Calculate averages per day
        avg_distance_per_day = total_distance / total_days if total_days > 0 else 0
        avg_steps_per_day = total_steps / total_days if total_days > 0 else 0

        # Calculate percentage of days with workouts
        unique_workout_days = {datetime.fromisoformat(w['start_time']).date() for w in filtered_workouts}
        days_with_workouts_percentage = (len(unique_workout_days) / total_days) * 100 if total_days > 0 else 0

        # Update labels
        self.avg_distance_label.config(text=f"{avg_distance_per_day:.2f} km")
        steps_str = self.format_steps(avg_steps_per_day)
        self.avg_steps_label.config(text=steps_str)
        self.days_with_workouts_label.config(text=f"{days_with_workouts_percentage:.1f}%")
        
        self.first_workout_label.config(text=first_workout.strftime('%d %b %Y'))
        self.last_workout_label.config(text=last_workout.strftime('%d %b %Y'))

    def manual_log_workout(self):
        """Prompt user to manually log a workout."""
        # Create a new window for input with improved styling
        input_window = tk.Toplevel(self.root)
        input_window.title("Manual Workout Log")
        input_window.configure(bg=COLORS['background'])
        input_window.geometry("350x280")
        
        # Add a frame with padding
        main_frame = ttk.Frame(input_window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Log a Workout", 
                            font=('Segoe UI', 14, 'bold'), 
                            foreground=COLORS['primary'])
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # Distance input with styling
        ttk.Label(main_frame, text="Distance (km):", style='Header.TLabel').grid(
            row=1, column=0, padx=5, pady=10, sticky=tk.W)
        distance_entry = ttk.Entry(main_frame, width=15)
        distance_entry.grid(row=1, column=1, padx=5, pady=10)

        # Steps input with styling
        ttk.Label(main_frame, text="Steps:", style='Header.TLabel').grid(
            row=2, column=0, padx=5, pady=10, sticky=tk.W)
        steps_entry = ttk.Entry(main_frame, width=15)
        steps_entry.grid(row=2, column=1, padx=5, pady=10)

        # Time input with styling
        ttk.Label(main_frame, text="Time (minutes):", style='Header.TLabel').grid(
            row=3, column=0, padx=5, pady=10, sticky=tk.W)
        time_entry = ttk.Entry(main_frame, width=15)
        time_entry.grid(row=3, column=1, padx=5, pady=10)

        # Button frame for better layout
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", 
                            command=input_window.destroy, width=10)
        cancel_btn.grid(row=0, column=0, padx=5)
        
        # Submit button with accent style
        submit_btn = ttk.Button(button_frame, text="Save Workout", 
                            command=lambda: self.save_manual_workout(
                                distance_entry.get(), steps_entry.get(), time_entry.get(), input_window),
                            style='Accent.TButton', width=15)
        submit_btn.grid(row=0, column=1, padx=5)

    def save_manual_workout(self, distance, steps, time_minutes, window):
        """Save the manually entered workout to the database."""
        try:
            # Validate inputs
            if not distance or not steps or not time_minutes:
                raise ValueError("All fields are required")
                
            distance = float(distance)
            steps = int(steps)
            duration = int(time_minutes) * 60  # Convert minutes to seconds
            
            # Additional validation
            if distance <= 0 or steps <= 0 or duration <= 0:
                raise ValueError("Values must be greater than zero")

            # Create a workout record
            workout = {
                'start_time': datetime.now().isoformat(),
                'end_time': datetime.now().isoformat(),
                'distance': distance,
                'steps': steps,
                'duration': duration,
                'synced': False
            }

            # Save to the database
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workouts (start_time, end_time, distance, steps, duration, synced)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                workout['start_time'],
                workout['end_time'],
                workout['distance'],
                workout['steps'],
                workout['duration'],
                workout['synced']
            ))
            conn.commit()
            conn.close()

            # Reload workouts and update statistics
            self.load_workouts()
            self.update_statistics()
            
            # Update all charts
            self.update_all_charts()

            # Show success message
            logging.info(f"Manual workout logged: {distance} km, {steps} steps, {time_minutes} minutes")
            
            # Close the input window
            window.destroy()

        except ValueError as e:
            error_message = str(e) if str(e) else "Please enter valid numbers for distance, steps, and time."
            logging.error(f"Invalid input for manual workout log: {error_message}")
            
            # Use messagebox for error
            from tkinter import messagebox
            messagebox.showerror("Input Error", error_message)

    def run_event_loop(self):
        """Run the asyncio event loop in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self):
        """Start the application."""
        self.update_ui()  # Begin the periodic UI update
        self.update_statistics()  # Initial update of statistics
        self.update_all_charts()  # Initial creation of charts
        self.root.mainloop()

    # You also need these workout-related functions

    def start_workout(self):
        """Create a workout record."""
        self.current_workout = {
            'start_time': datetime.now().isoformat(),
            'distance': 0,
            'steps': 0,
            'duration': 0,
            'synced': False  # Default
        }

    def stop_workout(self):
        """Finalize and save the current workout."""
        if self.current_workout:
            end_time = datetime.now()
            self.current_workout.update({
                'end_time': end_time.isoformat(),
                'distance': self.total_distance,
                'steps': self.steps,
                'duration': (end_time - datetime.fromisoformat(self.current_workout['start_time'])).seconds
            })
            self.save_workouts()
            self.current_workout = None
            self.update_statistics()

    def save_workouts(self):
        """Save the current workout to the database."""
        if self.current_workout and self.current_workout['steps'] >= 50:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workouts (start_time, end_time, distance, steps, duration, synced)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.current_workout['start_time'],
                self.current_workout.get('end_time'),
                self.current_workout['distance'],
                self.current_workout['steps'],
                self.current_workout['duration'],
                self.current_workout['synced']
            ))
            conn.commit()
            conn.close()

            # Reload workouts from the database
            self.load_workouts()

            # Schedule the statistics update 1 second after saving the workout
            self.root.after(1000, self.update_statistics)

    def start_workout_session(self):
        """Triggered by the Start button to unpause the treadmill."""
        self.is_running = True
        self.start_time = datetime.now()
        self.reset_counters()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        # Actually tell the treadmill to resume (0x07) if connected
        if self.connected and self.client:
            asyncio.run_coroutine_threadsafe(self._send_start_command(), self.loop)

    async def _send_start_command(self):
        """Sends the 'start/resume' command (0x07) to the treadmill."""
        try:
            await self.client.write_gatt_char(CONTROL_POINT_UUID, bytearray([0x07]), response=True)
        except Exception as e:
            self.status_label.config(text=f"Start error: {str(e)}")

    def stop_workout_session(self):
        """Triggered by the Stop button to pause the treadmill.
        Also finalizes and saves the current workout.
        """
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._set_speed(0), self.loop)
        # Finalize the current workout immediately.
        self.is_running = False
        self.stop_workout()
        self.reset_counters()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

    def reset_counters(self):
        """Reset all workout counters."""
        self.total_distance = 0.0
        self.steps = 0
        self.start_time = None
        self.running_time = "00:00:00"
        self.current_speed = 0.0
        self.update_ui()

    def toggle_connection(self):
        """Handle Connect/Disconnect button."""
        if not self.connected:
            asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)

    def update_ui(self):
        """
        Update UI labels with current values once per second.
        - Always show the current speed.
        - Only accumulate distance/time/steps if `is_running` is True.
        - Steps are incremented based on one-second average speed, rounding to 0 decimals.
        """
        # Always show the current speed
        self.speed_label.config(text=f"{self.current_speed:.1f} km/h")

        # If a workout is in progress (is_running), track time/distance:
        if self.is_running and self.start_time is not None:
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.running_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Distance from speed * time
            elapsed_hours = elapsed.total_seconds() / 3600.0
            self.total_distance = self.current_speed * elapsed_hours

            # Steps (using average speed for this 1-second interval; keep as float)
            current_time = datetime.now()
            if self.current_speed > 0 and (current_time - self.last_step_update).seconds >= 1:
                spm = self.estimate_spm_from_speed(self.current_speed)  # steps per minute
                steps_this_second = spm / 60.0  # steps per second, keep as float
                self.steps += steps_this_second
                self.last_step_update = current_time  # Update the last step update time

        # Update labels
        self.distance_label.config(text=f"{self.total_distance:.3f} km")
        self.steps_label.config(text=f"{int(self.steps)}")  # Round only for display
        self.time_label.config(text=self.running_time)

        # Schedule next update in 1 second
        self.root.after(1000, self.update_ui)

    def estimate_spm_from_speed(self, speed_kmh: float) -> float:
        """Estimate steps per minute from speed (rough approximation)."""
        if speed_kmh <= 0:
            return 0.0
        # Adjusted linear approximation: 2 km/h -> ~78 spm, 2.6 km/h -> ~92 spm, 3 km/h -> ~100 spm
        if speed_kmh <= 2.0:
            return (speed_kmh / 2.0) * 78.0
        elif speed_kmh <= 2.6:
            # Linear interpolation between 2.0 km/h (78 spm) and 2.6 km/h (92 spm)
            return 78.0 + ((speed_kmh - 2.0) / 0.6) * (92.0 - 78.0)
        else:
            # Linear interpolation between 2.6 km/h (92 spm) and 3.0 km/h (100 spm)
            return 92.0 + ((speed_kmh - 2.6) / 0.4) * (100.0 - 92.0)

    def set_speed(self, speed_kmh):
        """Handle direct speed button clicks."""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._set_speed(speed_kmh), self.loop)

    def adjust_speed(self, delta_speed):
        """Adjust speed by a small increment."""
        new_speed = self.current_speed + delta_speed
        if new_speed >= 0:
            asyncio.run_coroutine_threadsafe(self._set_speed(new_speed), self.loop)

    async def _set_speed(self, speed_kmh: float):
        """Send a speed command to the treadmill without starting/stopping workouts here."""
        if not self.client or not self.connected:
            return
        try:
            # Convert km/h -> 0.01 km/h units
            speed_units = int(speed_kmh * 100)

            # For stopping, send a stop command instead of speed=0
            if speed_kmh == 0:
                command = bytearray([0x08])  # Stop command
            else:
                command = bytearray([0x02, speed_units & 0xFF, (speed_units >> 8) & 0xFF])

            await self.client.write_gatt_char(CONTROL_POINT_UUID, command, response=True)

            # Just update the current speed in code. DO NOT auto-start/stop the workout here.
            self.current_speed = speed_kmh

        except Exception as e:
            self.status_label.config(text=f"Speed error: {str(e)}")

    async def connect(self):
        """Connect to treadmill via BLE with retries."""
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                self.status_label.config(text="Searching...")
                device = await BleakScanner.find_device_by_address(WALKPAD_ADDRESS, timeout=20.0)
                if not device:
                    self.status_label.config(text="Device not found")
                    return

                self.status_label.config(text="Connecting...")
                # Disable cached services and increase the connection timeout
                self.client = BleakClient(device, use_cached_services=True)
                await self.client.connect(timeout=30.0)

                # Optional: Wait briefly to ensure the device is ready
                await asyncio.sleep(2)

                # Subscribe to treadmill data
                await self.client.start_notify(TREADMILL_DATA_UUID, self.handle_treadmill_data)

                # Request control
                await self.client.write_gatt_char(CONTROL_POINT_UUID, bytearray([0x00]), response=True)

                self.connected = True
                self.conn_btn.config(text="Disconnect")
                self.status_label.config(text="Connected")
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                return  # Exit the loop if connected successfully

            except Exception as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
                self.status_label.config(text=f"Error: {str(e)}")
                self.connected = False

                # Ensure the client is properly disconnected before retrying
                if self.client:
                    try:
                        await self.client.disconnect()
                    except Exception as disconnect_error:
                        logging.error(f"Error during disconnect: {str(disconnect_error)}")
                    finally:
                        self.client = None

                if attempt < max_retries - 1:
                    self.status_label.config(text=f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

        self.status_label.config(text="Failed to connect after multiple attempts")

    async def disconnect(self):
        """Disconnect from treadmill."""
        if self.client:
            try:
                # Set speed to 0 first (stop)
                await self._set_speed(0)
            except Exception as e:
                logging.error(f"Error setting speed to 0: {str(e)}")
            try:
                await self.client.disconnect()
                logging.debug("Disconnected from the treadmill.")
            except Exception as e:
                logging.error(f"Error during disconnect: {str(e)}")
            finally:
                self.client = None
                self.connected = False
                self.conn_btn.config(text="Connect")
                self.status_label.config(text="Disconnected")
                # Cancel the keep-alive task if running
                if hasattr(self, 'keep_alive_task') and self.keep_alive_task:
                    self.keep_alive_task.cancel()
                    self.keep_alive_task = None

    async def keep_alive(self):
        """Periodically perform a dummy read to maintain the connection without starting a workout."""
        while self.client and self.client.is_connected:
            try:
                if not self.is_running:
                    # Perform a dummy read from the treadmill data characteristic.
                    logging.debug("Keep-alive: dummy read performed.")
                else:
                    logging.debug("Keep-alive: workout active, skipping dummy read.")
            except Exception as e:
                logging.error(f"Keep-alive error: {e}")
            await asyncio.sleep(10)  # Adjust the interval as needed.

    def format_steps(self, steps):
        """Format steps with better human-readable format"""
        if steps >= 1000000:
            return f"{steps/1000000:.1f}M"
        elif steps >= 1000:
            return f"{steps/1000:.1f}k"
        else:
            return str(steps)



if __name__ == "__main__":
    app = TreadmillApp()
    app.run()
