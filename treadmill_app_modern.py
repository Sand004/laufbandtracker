import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
import asyncio
import time
from bleak import BleakClient, BleakScanner
from datetime import datetime, timedelta
import threading
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from dateutil.relativedelta import relativedelta
import calendar
from supabase_config import SupabaseManager
import os

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# BLE Configuration
WALKPAD_ADDRESS = "69:82:20:D3:DE:C7"
TREADMILL_DATA_UUID = "00002acd-0000-1000-8000-00805f9b34fb"
CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"

# Define modern color scheme with dark mode support
COLORS = {
    'primary': '#6366F1',  # Indigo
    'secondary': '#10B981',  # Emerald
    'accent': '#F59E0B',  # Amber
    'background': '#F9FAFB',  # Gray-50
    'surface': '#FFFFFF',  # White
    'text': '#111827',  # Gray-900
    'text-secondary': '#6B7280',  # Gray-500
    'border': '#E5E7EB',  # Gray-200
    'warning': '#F59E0B',  # Amber
    'error': '#EF4444',  # Red
    'success': '#10B981',  # Emerald
    'chart_colors': ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
}

# Dark mode colors (for future implementation)
DARK_COLORS = {
    'primary': '#818CF8',  # Indigo-400
    'secondary': '#34D399',  # Emerald-400
    'accent': '#FCD34D',  # Amber-300
    'background': '#111827',  # Gray-900
    'surface': '#1F2937',  # Gray-800
    'text': '#F9FAFB',  # Gray-50
    'text-secondary': '#9CA3AF',  # Gray-400
    'border': '#374151',  # Gray-700
    'warning': '#FCD34D',  # Amber-300
    'error': '#F87171',  # Red-400
    'success': '#34D399',  # Emerald-400
    'chart_colors': ['#818CF8', '#34D399', '#FCD34D', '#F87171', '#A78BFA', '#F472B6']
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
        self.root.title("Fitness Tracker Pro")
        # Make UI larger and more modern
        self.root.geometry("1000x1100")
        self.root.configure(bg=COLORS['background'])
        
        # Set custom style
        self.setup_styles()
        
        # Initialize Supabase manager
        self.supabase_manager = SupabaseManager()

        # Variables
        self.client = None
        self.connected = False
        self.current_speed = 0.0
        self.total_distance = 0.0
        self.steps = 0
        self.start_time = None
        self.running_time = "00:00:00"
        self.current_workout = None
        self.workouts = []
        self.is_running = False
        self.last_step_update = datetime.now()
        self.speed_above_zero_time = None
        self.pullups_today = 0
        
        # Date filters
        self.selected_timeframe = tk.StringVar(value="All Time")
        self.filter_start_date = None
        self.filter_end_date = datetime.now()

        self.setup_ui()
        self.load_workouts()
        self.load_pullups()

        # Start async event loop in a separate thread
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.run_event_loop, daemon=True).start()

        # Schedule logging initialization after the main loop starts
        self.root.after(100, self.initialize_logging)
        
        # Schedule periodic data refresh
        self.root.after(30000, self.refresh_data)  # Refresh every 30 seconds

    def setup_styles(self):
        """Set up custom ttk styles for a modern look"""
        style = ttk.Style()
        
        # Configure the theme
        try:
            style.theme_use('clam')
        except:
            pass
        
        # Configure styles with modern design
        style.configure('Card.TFrame',
                       background=COLORS['surface'],
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Primary.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none')
        style.map('Primary.TButton',
                 background=[('active', '#4F46E5'), ('!active', COLORS['primary'])])
        
        style.configure('Secondary.TButton', 
                       font=('Segoe UI', 10),
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none')
        style.map('Secondary.TButton',
                 background=[('active', '#059669'), ('!active', COLORS['secondary'])])
        
        style.configure('Accent.TButton', 
                       font=('Segoe UI', 10),
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none')
        style.map('Accent.TButton',
                 background=[('active', '#DC2626'), ('!active', COLORS['accent'])])
        
        # Labels
        style.configure('Heading1.TLabel', 
                       font=('Segoe UI', 24, 'bold'),
                       background=COLORS['background'],
                       foreground=COLORS['text'])
        
        style.configure('Heading2.TLabel', 
                       font=('Segoe UI', 18, 'bold'),
                       background=COLORS['surface'],
                       foreground=COLORS['text'])
        
        style.configure('Heading3.TLabel', 
                       font=('Segoe UI', 14, 'bold'),
                       background=COLORS['surface'],
                       foreground=COLORS['text'])
        
        style.configure('Body.TLabel', 
                       font=('Segoe UI', 11),
                       background=COLORS['surface'],
                       foreground=COLORS['text-secondary'])
        
        style.configure('Value.TLabel', 
                       font=('Segoe UI', 16, 'bold'),
                       background=COLORS['surface'],
                       foreground=COLORS['primary'])
        
        style.configure('TFrame', background=COLORS['background'])
        style.configure('Card.TLabelframe', 
                       background=COLORS['surface'],
                       foreground=COLORS['text'],
                       borderwidth=1,
                       relief='flat')
        
        style.configure('TLabelframe.Label', 
                       font=('Segoe UI', 12, 'bold'),
                       background=COLORS['surface'],
                       foreground=COLORS['text'])

    def initialize_logging(self):
        """Initialize the logging handler after the UI is set up."""
        log_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(log_handler)

    def create_card(self, parent, **kwargs):
        """Create a card-style frame"""
        card = ttk.Frame(parent, style='Card.TFrame', **kwargs)
        card.configure(relief='flat', borderwidth=1)
        return card

    def setup_ui(self):
        # Main container with modern padding
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header section
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # App title with icon placeholder
        title_label = ttk.Label(header_frame, text="🏃‍♂️ Fitness Tracker Pro", 
                               style='Heading1.TLabel')
        title_label.pack(side=tk.LEFT)
        
        # Connection status on the right
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_indicator = ttk.Label(status_frame, text="●", 
                                         font=('Segoe UI', 16),
                                         foreground=COLORS['error'])
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_label = ttk.Label(status_frame, text="Disconnected", 
                                     style='Body.TLabel')
        self.status_label.pack(side=tk.LEFT)

        # Main content area with 3-column layout
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_columnconfigure(2, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Left column - Current workout
        self.setup_workout_column(content_frame)
        
        # Middle column - Statistics dashboard
        self.setup_stats_column(content_frame)
        
        # Right column - Pull-ups and controls
        self.setup_pullups_column(content_frame)

    def setup_workout_column(self, parent):
        """Setup the workout tracking column"""
        left_col = ttk.Frame(parent)
        left_col.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(0, 10))
        
        # Workout status card
        workout_card = self.create_card(left_col, padding=20)
        workout_card.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(workout_card, text="Treadmill Workout", style='Heading2.TLabel').pack(pady=(0, 15))
        
        # Current stats grid
        stats_grid = ttk.Frame(workout_card)
        stats_grid.pack(fill=tk.X)
        
        # Speed
        speed_frame = ttk.Frame(stats_grid)
        speed_frame.pack(fill=tk.X, pady=5)
        ttk.Label(speed_frame, text="Speed", style='Body.TLabel').pack(side=tk.LEFT)
        self.speed_label = ttk.Label(speed_frame, text="0.0 km/h", style='Value.TLabel')
        self.speed_label.pack(side=tk.RIGHT)
        
        # Distance
        distance_frame = ttk.Frame(stats_grid)
        distance_frame.pack(fill=tk.X, pady=5)
        ttk.Label(distance_frame, text="Distance", style='Body.TLabel').pack(side=tk.LEFT)
        self.distance_label = ttk.Label(distance_frame, text="0.00 km", style='Value.TLabel')
        self.distance_label.pack(side=tk.RIGHT)
        
        # Steps
        steps_frame = ttk.Frame(stats_grid)
        steps_frame.pack(fill=tk.X, pady=5)
        ttk.Label(steps_frame, text="Steps", style='Body.TLabel').pack(side=tk.LEFT)
        self.steps_label = ttk.Label(steps_frame, text="0", style='Value.TLabel')
        self.steps_label.pack(side=tk.RIGHT)
        
        # Time
        time_frame = ttk.Frame(stats_grid)
        time_frame.pack(fill=tk.X, pady=5)
        ttk.Label(time_frame, text="Time", style='Body.TLabel').pack(side=tk.LEFT)
        self.time_label = ttk.Label(time_frame, text="00:00:00", style='Value.TLabel')
        self.time_label.pack(side=tk.RIGHT)
        
        # Control buttons
        button_frame = ttk.Frame(workout_card)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.conn_btn = ttk.Button(button_frame, text="Connect Device", 
                                  command=self.toggle_connection,
                                  style='Primary.TButton')
        self.conn_btn.pack(fill=tk.X, pady=5)
        
        control_btns = ttk.Frame(button_frame)
        control_btns.pack(fill=tk.X, pady=5)
        
        self.start_btn = ttk.Button(control_btns, text="Start", 
                                   command=self.start_workout_session,
                                   style='Secondary.TButton')
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_btns, text="Stop", 
                                  command=self.stop_workout_session,
                                  style='Accent.TButton')
        self.stop_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        self.stop_btn.config(state='disabled')
        
        # Speed control card
        speed_card = self.create_card(left_col, padding=20)
        speed_card.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(speed_card, text="Speed Control", style='Heading3.TLabel').pack(pady=(0, 10))
        
        # Quick speed buttons
        speed_grid = ttk.Frame(speed_card)
        speed_grid.pack(fill=tk.X)
        
        speeds = [1, 2, 3, 4]
        for i, speed in enumerate(speeds):
            btn = ttk.Button(speed_grid, text=f"{speed} km/h",
                            command=lambda s=speed: self.set_speed(s),
                            style='Secondary.TButton')
            btn.grid(row=0, column=i, padx=2, pady=2, sticky=(tk.W, tk.E))
            speed_grid.columnconfigure(i, weight=1)
        
        # Fine control
        fine_frame = ttk.Frame(speed_card)
        fine_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(fine_frame, text="Fine Adjust", style='Body.TLabel').pack()
        
        fine_btns = ttk.Frame(fine_frame)
        fine_btns.pack(fill=tk.X, pady=5)
        
        fine_speeds = [-0.5, -0.2, 0.2, 0.5]
        for i, delta in enumerate(fine_speeds):
            btn = ttk.Button(fine_btns, text=f"{delta:+.1f}",
                            command=lambda d=delta: self.adjust_speed(d))
            btn.grid(row=0, column=i, padx=2, pady=2, sticky=(tk.W, tk.E))
            fine_btns.columnconfigure(i, weight=1)
        
        # Manual log button
        manual_card = self.create_card(left_col, padding=15)
        manual_card.pack(fill=tk.X)
        
        self.manual_log_btn = ttk.Button(manual_card, text="📝 Log Manual Workout", 
                                        command=self.manual_log_workout,
                                        style='Primary.TButton')
        self.manual_log_btn.pack(fill=tk.X)

    def setup_stats_column(self, parent):
        """Setup the statistics dashboard column"""
        middle_col = ttk.Frame(parent)
        middle_col.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(0, 10))
        
        # Quick stats cards
        stats_row = ttk.Frame(middle_col)
        stats_row.pack(fill=tk.X, pady=(0, 10))
        
        # Today's stats
        today_card = self.create_card(stats_row, padding=15)
        today_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(today_card, text="Today", style='Heading3.TLabel').pack()
        self.today_distance = ttk.Label(today_card, text="0.0 km", style='Value.TLabel')
        self.today_distance.pack()
        ttk.Label(today_card, text="Distance", style='Body.TLabel').pack()
        
        # This week stats
        week_card = self.create_card(stats_row, padding=15)
        week_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        ttk.Label(week_card, text="This Week", style='Heading3.TLabel').pack()
        self.week_distance = ttk.Label(week_card, text="0.0 km", style='Value.TLabel')
        self.week_distance.pack()
        ttk.Label(week_card, text="Distance", style='Body.TLabel').pack()
        
        # Charts notebook
        charts_card = self.create_card(middle_col, padding=15)
        charts_card.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(charts_card, text="Performance Analytics", style='Heading2.TLabel').pack(pady=(0, 10))
        
        # Timeframe selector
        timeframe_frame = ttk.Frame(charts_card)
        timeframe_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(timeframe_frame, text="Timeframe:", style='Body.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        timeframe_options = ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "This Year"]
        timeframe_dropdown = ttk.Combobox(timeframe_frame, textvariable=self.selected_timeframe, 
                                         values=timeframe_options, width=15, state='readonly')
        timeframe_dropdown.pack(side=tk.LEFT)
        timeframe_dropdown.bind("<<ComboboxSelected>>", self.update_timeframe)
        
        # Charts notebook
        self.stats_notebook = ttk.Notebook(charts_card)
        self.stats_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create frames for each tab
        self.day_frame = ttk.Frame(self.stats_notebook)
        self.week_frame = ttk.Frame(self.stats_notebook)
        self.month_frame = ttk.Frame(self.stats_notebook)
        self.pullups_chart_frame = ttk.Frame(self.stats_notebook)
        
        # Add tabs
        self.stats_notebook.add(self.day_frame, text="📊 Daily")
        self.stats_notebook.add(self.week_frame, text="📈 Weekly")
        self.stats_notebook.add(self.month_frame, text="📉 Monthly")
        self.stats_notebook.add(self.pullups_chart_frame, text="💪 Pull-ups")
        
        # Setup charts
        self.setup_charts()
        
        # Bind tab change
        self.stats_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def setup_pullups_column(self, parent):
        """Setup the pull-ups tracking column"""
        right_col = ttk.Frame(parent)
        right_col.grid(row=0, column=2, sticky=(tk.N, tk.W, tk.E, tk.S))
        
        # Pull-ups card
        pullups_card = self.create_card(right_col, padding=20)
        pullups_card.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(pullups_card, text="Pull-ups Today", style='Heading2.TLabel').pack(pady=(0, 15))
        
        # Big counter display
        counter_frame = ttk.Frame(pullups_card)
        counter_frame.pack(fill=tk.X, pady=10)
        
        self.pullups_counter = ttk.Label(counter_frame, text="0", 
                                        font=('Segoe UI', 48, 'bold'),
                                        foreground=COLORS['accent'])
        self.pullups_counter.pack()
        
        ttk.Label(counter_frame, text="reps completed", style='Body.TLabel').pack()
        
        # Pull-up stats
        pullup_stats = ttk.Frame(pullups_card)
        pullup_stats.pack(fill=tk.X, pady=(20, 0))
        
        # Weekly average
        avg_frame = ttk.Frame(pullup_stats)
        avg_frame.pack(fill=tk.X, pady=5)
        ttk.Label(avg_frame, text="Weekly Average", style='Body.TLabel').pack(side=tk.LEFT)
        self.pullups_avg = ttk.Label(avg_frame, text="0", style='Value.TLabel')
        self.pullups_avg.pack(side=tk.RIGHT)
        
        # Personal best
        pb_frame = ttk.Frame(pullup_stats)
        pb_frame.pack(fill=tk.X, pady=5)
        ttk.Label(pb_frame, text="Personal Best", style='Body.TLabel').pack(side=tk.LEFT)
        self.pullups_pb = ttk.Label(pb_frame, text="0", style='Value.TLabel')
        self.pullups_pb.pack(side=tk.RIGHT)
        
        # Refresh button
        refresh_btn = ttk.Button(pullups_card, text="🔄 Refresh", 
                                command=self.refresh_pullups,
                                style='Secondary.TButton')
        refresh_btn.pack(fill=tk.X, pady=(20, 0))
        
        # Summary stats card
        summary_card = self.create_card(right_col, padding=20)
        summary_card.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(summary_card, text="All-Time Stats", style='Heading3.TLabel').pack(pady=(0, 10))
        
        # Total workouts
        total_frame = ttk.Frame(summary_card)
        total_frame.pack(fill=tk.X, pady=5)
        ttk.Label(total_frame, text="Total Workouts", style='Body.TLabel').pack(side=tk.LEFT)
        self.total_workouts_label = ttk.Label(total_frame, text="0", style='Value.TLabel')
        self.total_workouts_label.pack(side=tk.RIGHT)
        
        # Total distance
        dist_frame = ttk.Frame(summary_card)
        dist_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dist_frame, text="Total Distance", style='Body.TLabel').pack(side=tk.LEFT)
        self.total_distance_label = ttk.Label(dist_frame, text="0 km", style='Value.TLabel')
        self.total_distance_label.pack(side=tk.RIGHT)
        
        # Total steps
        steps_frame = ttk.Frame(summary_card)
        steps_frame.pack(fill=tk.X, pady=5)
        ttk.Label(steps_frame, text="Total Steps", style='Body.TLabel').pack(side=tk.LEFT)
        self.total_steps_label = ttk.Label(steps_frame, text="0", style='Value.TLabel')
        self.total_steps_label.pack(side=tk.RIGHT)
        
        # Logs viewer
        logs_card = self.create_card(right_col, padding=15)
        logs_card.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(logs_card, text="System Logs", style='Heading3.TLabel').pack(pady=(0, 10))
        
        # Log text widget
        self.log_text = scrolledtext.ScrolledText(
            logs_card, 
            wrap='word', 
            height=10,
            font=('Consolas', 9),
            background='#F3F4F6',
            foreground=COLORS['text']
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_charts(self):
        """Setup all chart figures"""
        # Daily chart
        self.day_fig = plt.Figure(figsize=(6, 4), dpi=100, facecolor=COLORS['surface'])
        self.day_ax = self.day_fig.add_subplot(111)
        self.day_ax.set_facecolor(COLORS['surface'])
        self.day_canvas = FigureCanvasTkAgg(self.day_fig, master=self.day_frame)
        self.day_canvas.draw()
        self.day_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Weekly chart
        self.week_fig = plt.Figure(figsize=(6, 4), dpi=100, facecolor=COLORS['surface'])
        self.week_ax = self.week_fig.add_subplot(111)
        self.week_ax.set_facecolor(COLORS['surface'])
        self.week_canvas = FigureCanvasTkAgg(self.week_fig, master=self.week_frame)
        self.week_canvas.draw()
        self.week_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Monthly chart
        self.month_fig = plt.Figure(figsize=(6, 4), dpi=100, facecolor=COLORS['surface'])
        self.month_ax = self.month_fig.add_subplot(111)
        self.month_ax.set_facecolor(COLORS['surface'])
        self.month_canvas = FigureCanvasTkAgg(self.month_fig, master=self.month_frame)
        self.month_canvas.draw()
        self.month_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pull-ups chart
        self.pullups_fig = plt.Figure(figsize=(6, 4), dpi=100, facecolor=COLORS['surface'])
        self.pullups_ax = self.pullups_fig.add_subplot(111)
        self.pullups_ax.set_facecolor(COLORS['surface'])
        self.pullups_canvas = FigureCanvasTkAgg(self.pullups_fig, master=self.pullups_chart_frame)
        self.pullups_canvas.draw()
        self.pullups_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_workouts(self):
        """Load workouts from Supabase"""
        try:
            self.workouts = self.supabase_manager.get_workouts(
                start_date=self.filter_start_date,
                end_date=self.filter_end_date
            )
            self.update_statistics()
            self.update_all_charts()
            logging.info(f"Loaded {len(self.workouts)} workouts from Supabase")
        except Exception as e:
            logging.error(f"Error loading workouts: {e}")
            self.workouts = []

    def load_pullups(self):
        """Load pull-ups data"""
        try:
            # Load today's count
            self.pullups_today = self.supabase_manager.get_pullups_today()
            self.pullups_counter.config(text=str(self.pullups_today))
            
            # Load history for stats
            history = self.supabase_manager.get_pullups_history(30)
            if history:
                # Calculate weekly average
                week_history = [h for h in history if 
                               datetime.fromisoformat(h['date']).date() >= 
                               (datetime.now().date() - timedelta(days=7))]
                if week_history:
                    avg = sum(h['reps'] for h in week_history) / len(week_history)
                    self.pullups_avg.config(text=f"{avg:.1f}")
                
                # Find personal best
                pb = max(h['reps'] for h in history)
                self.pullups_pb.config(text=str(pb))
            
            logging.info(f"Loaded pull-ups data: {self.pullups_today} today")
        except Exception as e:
            logging.error(f"Error loading pull-ups: {e}")

    def refresh_pullups(self):
        """Refresh pull-ups data"""
        self.load_pullups()
        self.update_pullups_chart()
        logging.info("Pull-ups data refreshed")

    def refresh_data(self):
        """Periodic data refresh"""
        self.load_workouts()
        self.load_pullups()
        # Schedule next refresh
        self.root.after(30000, self.refresh_data)

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
        
        # Reload data with new filter
        self.load_workouts()

    def on_tab_changed(self, event=None):
        """Update charts when changing tabs"""
        current_tab = self.stats_notebook.select()
        tab_name = self.stats_notebook.tab(current_tab, "text")
        
        if "Daily" in tab_name:
            self.update_day_chart()
        elif "Weekly" in tab_name:
            self.update_week_chart()
        elif "Monthly" in tab_name:
            self.update_month_chart()
        elif "Pull-ups" in tab_name:
            self.update_pullups_chart()

    def update_all_charts(self):
        """Update all charts at once"""
        self.update_day_chart()
        self.update_week_chart() 
        self.update_month_chart()
        self.update_pullups_chart()

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
            daily_data[day] = {'steps': 0, 'distance': 0}
        
        # Populate data from workouts
        for workout in self.workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if start_date <= workout_date <= end_date:
                daily_data[workout_date]['steps'] += workout['steps']
                daily_data[workout_date]['distance'] += workout['distance']
        
        # Prepare data for plotting
        dates = list(daily_data.keys())
        steps = [d['steps'] for d in daily_data.values()]
        
        # Create bar chart
        bars = self.day_ax.bar(
            dates, 
            steps, 
            color=COLORS['primary'],
            alpha=0.8,
            width=0.6
        )
        
        # Add value labels
        for bar, value in zip(bars, steps):
            if value > 0:
                self.day_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 50,
                    self.format_number(value),
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
        
        # Styling
        self.day_ax.set_ylabel('Steps', fontsize=10)
        self.day_ax.set_title('Daily Steps - Last 7 Days', fontsize=12, pad=10)
        self.day_ax.xaxis.set_major_formatter(mdates.DateFormatter('%a\n%d'))
        self.day_ax.grid(axis='y', linestyle='--', alpha=0.3)
        self.day_ax.spines['top'].set_visible(False)
        self.day_ax.spines['right'].set_visible(False)
        
        self.day_fig.tight_layout()
        self.day_canvas.draw()

    def update_week_chart(self):
        """Update the weekly chart"""
        self.week_ax.clear()
        
        # Get data for last 4 weeks
        end_date = datetime.now().date()
        start_date = end_date - timedelta(weeks=4)
        
        # Create weekly buckets
        weekly_data = {}
        for i in range(4):
            week_start = end_date - timedelta(weeks=4-i-1)
            week_end = week_start + timedelta(days=6)
            week_label = f"Week {i+1}"
            weekly_data[week_label] = {
                'steps': 0,
                'distance': 0,
                'start': week_start,
                'end': week_end
            }
        
        # Populate data
        for workout in self.workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if workout_date >= start_date:
                for week_label, week_data in weekly_data.items():
                    if week_data['start'] <= workout_date <= week_data['end']:
                        weekly_data[week_label]['steps'] += workout['steps']
                        weekly_data[week_label]['distance'] += workout['distance']
        
        # Plot
        labels = list(weekly_data.keys())
        distances = [d['distance'] for d in weekly_data.values()]
        
        bars = self.week_ax.bar(
            labels,
            distances,
            color=COLORS['secondary'],
            alpha=0.8
        )
        
        # Add value labels
        for bar, value in zip(bars, distances):
            if value > 0:
                self.week_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.1,
                    f"{value:.1f} km",
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
        
        # Styling
        self.week_ax.set_ylabel('Distance (km)', fontsize=10)
        self.week_ax.set_title('Weekly Distance - Last 4 Weeks', fontsize=12, pad=10)
        self.week_ax.grid(axis='y', linestyle='--', alpha=0.3)
        self.week_ax.spines['top'].set_visible(False)
        self.week_ax.spines['right'].set_visible(False)
        
        self.week_fig.tight_layout()
        self.week_canvas.draw()

    def update_month_chart(self):
        """Update the monthly chart"""
        self.month_ax.clear()
        
        # Get data for last 6 months
        today = datetime.now()
        end_date = today.date()
        start_date = (today - relativedelta(months=5)).replace(day=1).date()
        
        # Create monthly buckets
        monthly_data = {}
        current_date = start_date
        while current_date <= end_date:
            month_label = current_date.strftime('%b')
            monthly_data[month_label] = {
                'steps': 0,
                'distance': 0,
                'workouts': 0
            }
            current_date = (datetime(current_date.year, current_date.month, 1) + 
                           relativedelta(months=1)).date()
        
        # Populate data
        for workout in self.workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            if workout_date >= start_date:
                month_label = workout_date.strftime('%b')
                if month_label in monthly_data:
                    monthly_data[month_label]['steps'] += workout['steps']
                    monthly_data[month_label]['distance'] += workout['distance']
                    monthly_data[month_label]['workouts'] += 1
        
        # Plot
        labels = list(monthly_data.keys())
        workouts = [d['workouts'] for d in monthly_data.values()]
        
        bars = self.month_ax.bar(
            labels,
            workouts,
            color=COLORS['accent'],
            alpha=0.8
        )
        
        # Add value labels
        for bar, value in zip(bars, workouts):
            if value > 0:
                self.month_ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    str(value),
                    ha='center',
                    va='bottom',
                    fontsize=9
                )
        
        # Styling
        self.month_ax.set_ylabel('Workouts', fontsize=10)
        self.month_ax.set_title('Monthly Workouts - Last 6 Months', fontsize=12, pad=10)
        self.month_ax.grid(axis='y', linestyle='--', alpha=0.3)
        self.month_ax.spines['top'].set_visible(False)
        self.month_ax.spines['right'].set_visible(False)
        
        self.month_fig.tight_layout()
        self.month_canvas.draw()

    def update_pullups_chart(self):
        """Update the pull-ups chart"""
        self.pullups_ax.clear()
        
        try:
            # Get 30 days of pull-up data
            history = self.supabase_manager.get_pullups_history(30)
            
            if history:
                # Sort by date
                history.sort(key=lambda x: x['date'])
                
                # Extract data
                dates = [datetime.fromisoformat(h['date']).date() for h in history]
                reps = [h['reps'] for h in history]
                
                # Create line plot with markers
                self.pullups_ax.plot(dates, reps, 
                                    color=COLORS['accent'],
                                    marker='o',
                                    markersize=6,
                                    linewidth=2,
                                    alpha=0.8)
                
                # Fill area under the line
                self.pullups_ax.fill_between(dates, reps, 
                                           color=COLORS['accent'],
                                           alpha=0.2)
                
                # Add value labels for last 7 days
                for date, rep in zip(dates[-7:], reps[-7:]):
                    self.pullups_ax.text(date, rep + 1, str(rep),
                                       ha='center', va='bottom',
                                       fontsize=8)
                
                # Styling
                self.pullups_ax.set_ylabel('Reps', fontsize=10)
                self.pullups_ax.set_title('Pull-ups - Last 30 Days', fontsize=12, pad=10)
                self.pullups_ax.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
                self.pullups_ax.grid(axis='y', linestyle='--', alpha=0.3)
                self.pullups_ax.spines['top'].set_visible(False)
                self.pullups_ax.spines['right'].set_visible(False)
                
            else:
                self.pullups_ax.text(0.5, 0.5, 'No pull-up data available',
                                   ha='center', va='center',
                                   transform=self.pullups_ax.transAxes,
                                   fontsize=12, color=COLORS['text-secondary'])
                
        except Exception as e:
            logging.error(f"Error updating pull-ups chart: {e}")
            self.pullups_ax.text(0.5, 0.5, 'Error loading data',
                               ha='center', va='center',
                               transform=self.pullups_ax.transAxes,
                               fontsize=12, color=COLORS['error'])
        
        self.pullups_fig.tight_layout()
        self.pullups_canvas.draw()

    def update_statistics(self):
        """Update all statistics displays"""
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        
        # Calculate statistics
        today_stats = {'distance': 0, 'steps': 0, 'workouts': 0}
        week_stats = {'distance': 0, 'steps': 0, 'workouts': 0}
        total_stats = {'distance': 0, 'steps': 0, 'workouts': len(self.workouts)}
        
        for workout in self.workouts:
            workout_date = datetime.fromisoformat(workout['start_time']).date()
            distance = workout['distance']
            steps = workout['steps']
            
            # Today
            if workout_date == today:
                today_stats['distance'] += distance
                today_stats['steps'] += steps
                today_stats['workouts'] += 1
            
            # This week
            if workout_date >= week_start:
                week_stats['distance'] += distance
                week_stats['steps'] += steps
                week_stats['workouts'] += 1
            
            # Total
            total_stats['distance'] += distance
            total_stats['steps'] += steps
        
        # Update displays
        self.today_distance.config(text=f"{today_stats['distance']:.1f} km")
        self.week_distance.config(text=f"{week_stats['distance']:.1f} km")
        
        self.total_workouts_label.config(text=str(total_stats['workouts']))
        self.total_distance_label.config(text=f"{total_stats['distance']:.1f} km")
        self.total_steps_label.config(text=self.format_number(total_stats['steps']))

    def format_number(self, num):
        """Format large numbers with K/M suffix"""
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        else:
            return str(int(num))

    def manual_log_workout(self):
        """Open manual workout logging dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Log Manual Workout")
        dialog.geometry("400x350")
        dialog.configure(bg=COLORS['background'])
        
        # Center the dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Log Workout", style='Heading2.TLabel').pack(pady=(0, 20))
        
        # Input fields
        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Distance
        ttk.Label(fields_frame, text="Distance (km):", style='Body.TLabel').grid(
            row=0, column=0, sticky=tk.W, pady=10)
        distance_entry = ttk.Entry(fields_frame, width=20)
        distance_entry.grid(row=0, column=1, padx=(10, 0), pady=10)
        
        # Steps
        ttk.Label(fields_frame, text="Steps:", style='Body.TLabel').grid(
            row=1, column=0, sticky=tk.W, pady=10)
        steps_entry = ttk.Entry(fields_frame, width=20)
        steps_entry.grid(row=1, column=1, padx=(10, 0), pady=10)
        
        # Time
        ttk.Label(fields_frame, text="Time (minutes):", style='Body.TLabel').grid(
            row=2, column=0, sticky=tk.W, pady=10)
        time_entry = ttk.Entry(fields_frame, width=20)
        time_entry.grid(row=2, column=1, padx=(10, 0), pady=10)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def save_workout():
            try:
                distance = float(distance_entry.get())
                steps = int(steps_entry.get())
                duration = int(time_entry.get()) * 60
                
                if distance <= 0 or steps <= 0 or duration <= 0:
                    raise ValueError("Values must be positive")
                
                # Create workout record
                workout = {
                    'start_time': datetime.now().isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'distance': distance,
                    'steps': steps,
                    'duration': duration
                }
                
                # Save to Supabase
                if self.supabase_manager.add_workout(workout):
                    logging.info(f"Manual workout saved: {distance}km, {steps} steps")
                    dialog.destroy()
                    self.load_workouts()  # Refresh data
                else:
                    raise Exception("Failed to save workout")
                    
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Invalid Input", 
                                   "Please enter valid positive numbers")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Error", f"Failed to save: {str(e)}")
        
        ttk.Button(button_frame, text="Cancel", 
                  command=dialog.destroy).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Save", 
                  command=save_workout,
                  style='Primary.TButton').pack(side=tk.LEFT)
        
        # Focus on first field
        distance_entry.focus()

    def handle_treadmill_data(self, _, data: bytearray):
        """Handle incoming treadmill data"""
        try:
            if len(data) >= 4:
                # Decode speed
                speed_raw = int.from_bytes(data[2:4], byteorder='little')
                new_speed = speed_raw / 100.0
                self.current_speed = new_speed

                # Auto start/stop logic
                if self.current_speed > 0.0:
                    if not self.is_running:
                        if self.speed_above_zero_time is None:
                            self.speed_above_zero_time = datetime.now()
                        elif (datetime.now() - self.speed_above_zero_time).seconds >= 2:
                            self.is_running = True
                            self.start_time = datetime.now()
                            self.start_workout()
                            logging.info("Workout auto-started")
                    else:
                        self.speed_above_zero_time = None

                elif self.current_speed == 0.0:
                    if self.is_running:
                        if self.speed_above_zero_time is None:
                            self.speed_above_zero_time = datetime.now()
                        elif (datetime.now() - self.speed_above_zero_time).seconds >= 2:
                            self.is_running = False
                            self.stop_workout()
                            logging.info("Workout auto-stopped")
                            self.reset_counters()
                    else:
                        self.speed_above_zero_time = None

        except Exception as e:
            logging.error(f"Error parsing treadmill data: {e}")

    def start_workout(self):
        """Create a workout record"""
        self.current_workout = {
            'start_time': datetime.now().isoformat(),
            'distance': 0,
            'steps': 0,
            'duration': 0
        }

    def stop_workout(self):
        """Finalize and save the current workout"""
        if self.current_workout and self.steps >= 50:  # Min 50 steps to save
            end_time = datetime.now()
            self.current_workout.update({
                'end_time': end_time.isoformat(),
                'distance': self.total_distance,
                'steps': self.steps,
                'duration': (end_time - datetime.fromisoformat(
                    self.current_workout['start_time'])).seconds
            })
            
            # Save to Supabase
            if self.supabase_manager.add_workout(self.current_workout):
                logging.info("Workout saved to Supabase")
                self.current_workout = None
                # Refresh statistics
                self.root.after(1000, self.load_workouts)

    def start_workout_session(self):
        """Manual start button handler"""
        self.is_running = True
        self.start_time = datetime.now()
        self.reset_counters()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        if self.connected and self.client:
            asyncio.run_coroutine_threadsafe(self._send_start_command(), self.loop)

    async def _send_start_command(self):
        """Send start command to treadmill"""
        try:
            await self.client.write_gatt_char(CONTROL_POINT_UUID, 
                                            bytearray([0x07]), response=True)
        except Exception as e:
            logging.error(f"Start command error: {e}")

    def stop_workout_session(self):
        """Manual stop button handler"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._set_speed(0), self.loop)
        self.is_running = False
        self.stop_workout()
        self.reset_counters()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

    def reset_counters(self):
        """Reset workout counters"""
        self.total_distance = 0.0
        self.steps = 0
        self.start_time = None
        self.running_time = "00:00:00"
        self.current_speed = 0.0
        self.update_ui()

    def toggle_connection(self):
        """Toggle BLE connection"""
        if not self.connected:
            asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)

    def update_ui(self):
        """Update UI with current values"""
        # Speed
        self.speed_label.config(text=f"{self.current_speed:.1f} km/h")

        # Calculate time/distance/steps if running
        if self.is_running and self.start_time is not None:
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.running_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Distance
            elapsed_hours = elapsed.total_seconds() / 3600.0
            self.total_distance = self.current_speed * elapsed_hours

            # Steps calculation
            current_time = datetime.now()
            if self.current_speed > 0 and (current_time - self.last_step_update).seconds >= 1:
                spm = self.estimate_spm_from_speed(self.current_speed)
                steps_this_second = spm / 60.0
                self.steps += steps_this_second
                self.last_step_update = current_time

        # Update labels
        self.distance_label.config(text=f"{self.total_distance:.2f} km")
        self.steps_label.config(text=f"{int(self.steps)}")
        self.time_label.config(text=self.running_time)

        # Schedule next update
        self.root.after(1000, self.update_ui)

    def estimate_spm_from_speed(self, speed_kmh: float) -> float:
        """Estimate steps per minute from speed"""
        if speed_kmh <= 0:
            return 0.0
        # Linear approximation
        if speed_kmh <= 2.0:
            return (speed_kmh / 2.0) * 78.0
        elif speed_kmh <= 2.6:
            return 78.0 + ((speed_kmh - 2.0) / 0.6) * (92.0 - 78.0)
        else:
            return 92.0 + ((speed_kmh - 2.6) / 0.4) * (100.0 - 92.0)

    def set_speed(self, speed_kmh):
        """Set treadmill speed"""
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._set_speed(speed_kmh), self.loop)

    def adjust_speed(self, delta_speed):
        """Adjust speed by delta"""
        new_speed = max(0, self.current_speed + delta_speed)
        if self.connected:
            asyncio.run_coroutine_threadsafe(self._set_speed(new_speed), self.loop)

    async def _set_speed(self, speed_kmh: float):
        """Send speed command to treadmill"""
        if not self.client or not self.connected:
            return
        try:
            speed_units = int(speed_kmh * 100)
            if speed_kmh == 0:
                command = bytearray([0x08])  # Stop
            else:
                command = bytearray([0x02, speed_units & 0xFF, (speed_units >> 8) & 0xFF])

            await self.client.write_gatt_char(CONTROL_POINT_UUID, command, response=True)
            self.current_speed = speed_kmh

        except Exception as e:
            logging.error(f"Speed control error: {e}")

    async def connect(self):
        """Connect to treadmill"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                self.status_label.config(text="Searching...")
                self.status_indicator.config(foreground=COLORS['warning'])
                
                device = await BleakScanner.find_device_by_address(
                    WALKPAD_ADDRESS, timeout=20.0)
                if not device:
                    self.status_label.config(text="Device not found")
                    return

                self.status_label.config(text="Connecting...")
                self.client = BleakClient(device, use_cached_services=True)
                await self.client.connect(timeout=30.0)
                await asyncio.sleep(2)

                # Subscribe to notifications
                await self.client.start_notify(TREADMILL_DATA_UUID, 
                                             self.handle_treadmill_data)

                # Request control
                await self.client.write_gatt_char(CONTROL_POINT_UUID, 
                                                bytearray([0x00]), response=True)

                self.connected = True
                self.conn_btn.config(text="Disconnect")
                self.status_label.config(text="Connected")
                self.status_indicator.config(foreground=COLORS['success'])
                self.keep_alive_task = asyncio.create_task(self.keep_alive())
                return

            except Exception as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {e}")
                self.status_label.config(text=f"Error: {str(e)}")
                self.connected = False

                if self.client:
                    try:
                        await self.client.disconnect()
                    except:
                        pass
                    finally:
                        self.client = None

                if attempt < max_retries - 1:
                    self.status_label.config(text=f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)

        self.status_label.config(text="Connection failed")
        self.status_indicator.config(foreground=COLORS['error'])

    async def disconnect(self):
        """Disconnect from treadmill"""
        if self.client:
            try:
                await self._set_speed(0)
            except:
                pass
            try:
                await self.client.disconnect()
                logging.info("Disconnected from treadmill")
            except Exception as e:
                logging.error(f"Disconnect error: {e}")
            finally:
                self.client = None
                self.connected = False
                self.conn_btn.config(text="Connect Device")
                self.status_label.config(text="Disconnected")
                self.status_indicator.config(foreground=COLORS['error'])
                if hasattr(self, 'keep_alive_task') and self.keep_alive_task:
                    self.keep_alive_task.cancel()
                    self.keep_alive_task = None

    async def keep_alive(self):
        """Keep connection alive"""
        while self.client and self.client.is_connected:
            try:
                if not self.is_running:
                    logging.debug("Keep-alive ping")
            except Exception as e:
                logging.error(f"Keep-alive error: {e}")
            await asyncio.sleep(10)

    def run_event_loop(self):
        """Run async event loop"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self):
        """Start the application"""
        self.update_ui()
        self.root.mainloop()


if __name__ == "__main__":
    app = TreadmillApp()
    app.run()
