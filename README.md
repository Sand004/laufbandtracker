# Fitness Tracker Pro (Treadmill & Pull-up Tracker)

A modern fitness tracking application that monitors treadmill workouts via Bluetooth and tracks pull-up exercises through an ESP32 sensor, with all data stored in the cloud using Supabase.

## Features

### 🏃‍♂️ Treadmill Tracking
- **Automatic Bluetooth Connection**: Connects to WalkingPad treadmills via BLE
- **Real-time Monitoring**: Tracks speed, distance, steps, and time
- **Auto Start/Stop**: Automatically detects when workout begins and ends
- **Manual Logging**: Add workouts manually when not connected

### 💪 Pull-up Tracking
- **ESP32 Integration**: Receives data from ultrasonic sensor via Supabase
- **Daily Counter**: Shows today's pull-up count with live updates
- **Statistics**: Weekly average and personal best tracking
- **Progress Charts**: Visual representation of pull-up history

### 📊 Analytics Dashboard
- **Multiple Views**: Daily, weekly, and monthly statistics
- **Interactive Charts**: Beautiful visualizations of your progress
- **Timeframe Filtering**: View data for different time periods
- **Cloud Storage**: All data synced to Supabase for access anywhere

## Installation

### Prerequisites
- Python 3.8 or higher
- Bluetooth adapter (for treadmill connection)
- Supabase account (free tier works fine)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sand004/laufbandtracker.git
   cd laufbandtracker
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Supabase**
   - Create a new project at [supabase.com](https://supabase.com)
   - Run the SQL schema from `supabase_schema.sql` in the SQL editor
   - Copy your project URL and anon key

4. **Configure credentials**
   - Open `supabase_config.py`
   - Update `SUPABASE_URL` and `SUPABASE_KEY` with your credentials

5. **Migrate existing data (optional)**
   ```bash
   python migrate_to_supabase.py
   ```

6. **Run the application**
   ```bash
   python treadmill_app_modern.py
   ```

## ESP32 Pull-up Sensor Setup

The pull-up sensor uses an HC-SR04 ultrasonic sensor with ESP32. The provided code automatically sends data to Supabase.

### Hardware Requirements
- ESP32 development board
- HC-SR04 ultrasonic sensor
- Pull-up bar installation

### Wiring
- TRIG_PIN: GPIO 5
- ECHO_PIN: GPIO 18

### Configuration
1. Update WiFi credentials in the ESP32 code
2. The Supabase credentials are already configured
3. Upload the code to your ESP32

## Usage

### Treadmill Workouts
1. Click "Connect Device" to connect to your treadmill
2. Start walking - the app auto-detects workout start
3. Stop walking - workout is automatically saved after 2 seconds
4. Or use manual controls with Start/Stop buttons

### Manual Workout Logging
1. Click "Log Manual Workout"
2. Enter distance, steps, and time
3. Click Save to store in Supabase

### Viewing Statistics
- Use the timeframe dropdown to filter data
- Switch between chart tabs to see different views
- Pull-up data updates automatically every 30 seconds

## Architecture

### Cloud Database (Supabase)
- **workouts** table: Stores all treadmill workout data
- **daily_pullups** table: Tracks pull-ups per day
- **increment_reps_today()** function: Used by ESP32 to add pull-ups

### Local Application
- **treadmill_app_modern.py**: Main application with modern UI
- **supabase_config.py**: Database connection and operations
- **migrate_to_supabase.py**: Migration tool for existing data

## Building Executable

To create a standalone executable:

```bash
pyinstaller --onefile --windowed --name "Fitness Tracker Pro" treadmill_app_modern.py
```

The executable will be in the `dist` folder.

## Troubleshooting

### Bluetooth Connection Issues
- Ensure Bluetooth is enabled on your computer
- Check that the treadmill address matches your device
- Try the `connect.py` script for testing connection

### Supabase Connection Errors
- Verify your credentials are correct
- Check internet connection
- Ensure the database schema is properly created

### Pull-up Sensor Not Working
- Verify ESP32 is connected to WiFi
- Check ultrasonic sensor wiring
- Monitor serial output for debugging

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License - see LICENSE file for details
