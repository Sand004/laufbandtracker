"""
Migration script to transfer data from SQLite to Supabase
"""
import sqlite3
import logging
from supabase_config import SupabaseManager
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_to_supabase():
    """Migrate all workouts from SQLite to Supabase"""
    
    # Initialize Supabase manager
    supabase_manager = SupabaseManager()
    
    # Connect to SQLite database
    try:
        conn = sqlite3.connect('treadmill_workouts.db')
        cursor = conn.cursor()
        
        # Get all workouts from SQLite
        cursor.execute("""
            SELECT id, start_time, end_time, distance, steps, duration, synced 
            FROM workouts 
            ORDER BY start_time
        """)
        
        workouts = []
        for row in cursor.fetchall():
            workout = {
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'distance': row[3],
                'steps': row[4],
                'duration': row[5],
                'synced': row[6] if row[6] is not None else False
            }
            workouts.append(workout)
        
        logging.info(f"Found {len(workouts)} workouts in SQLite database")
        
        # Migrate workouts
        migrated_count = supabase_manager.migrate_from_sqlite(workouts)
        
        logging.info(f"Successfully migrated {migrated_count} workouts to Supabase")
        
        # Mark synced workouts in SQLite
        if migrated_count > 0:
            cursor.execute("""
                UPDATE workouts 
                SET synced = 1 
                WHERE synced = 0 OR synced IS NULL
            """)
            conn.commit()
            logging.info("Marked workouts as synced in SQLite database")
        
        conn.close()
        
        return migrated_count
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
        return 0
    except Exception as e:
        logging.error(f"Migration error: {e}")
        return 0

def test_supabase_connection():
    """Test the Supabase connection"""
    try:
        supabase_manager = SupabaseManager()
        
        # Test getting workouts
        workouts = supabase_manager.get_workouts()
        logging.info(f"Supabase connection successful. Found {len(workouts)} workouts.")
        
        # Test getting pull-ups
        pullups_today = supabase_manager.get_pullups_today()
        logging.info(f"Today's pull-ups: {pullups_today}")
        
        return True
        
    except Exception as e:
        logging.error(f"Supabase connection error: {e}")
        return False

if __name__ == "__main__":
    print("=== Treadmill Tracker Migration Tool ===")
    print("\nThis script will migrate your workout data from SQLite to Supabase.")
    print("\nIMPORTANT: Make sure you have:")
    print("1. Run the SQL schema in Supabase dashboard")
    print("2. Installed required packages: pip install supabase")
    
    choice = input("\nDo you want to proceed? (y/n): ")
    
    if choice.lower() == 'y':
        print("\nTesting Supabase connection...")
        if test_supabase_connection():
            print("\nStarting migration...")
            count = migrate_to_supabase()
            print(f"\nMigration complete! {count} workouts migrated.")
        else:
            print("\nError: Could not connect to Supabase. Please check your credentials.")
    else:
        print("\nMigration cancelled.")
