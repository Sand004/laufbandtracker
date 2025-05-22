import json
import sqlite3
from datetime import datetime

json_file = r"F:\Sell everything\Laufband\treadmill_workouts.json"
db_file = "treadmill_workouts.db"

# Connect to the SQLite database
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Create the workouts table if it doesn't exist
cursor.execute('''
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

# Load workouts from the JSON file
with open(json_file, 'r') as f:
    workouts = json.load(f)

# Insert workouts into the database
for workout in workouts:
    cursor.execute('''
        INSERT INTO workouts (start_time, end_time, distance, steps, duration, synced)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        workout['start_time'],
        workout.get('end_time'),
        workout['distance'],
        workout['steps'],
        workout['duration'],
        workout['synced']
    ))

# Commit the changes and close the connection
conn.commit()
conn.close() 