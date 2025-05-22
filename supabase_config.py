"""
Supabase configuration and client setup
"""
from supabase import create_client, Client
import os
from typing import Optional
from datetime import datetime, date, timedelta
import logging

# Supabase credentials
SUPABASE_URL = "https://xgoibwxiwfagcqjuslad.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhnb2lid3hpd2ZhZ2NxanVzbGFkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc5MjgzNDAsImV4cCI6MjA2MzUwNDM0MH0.75bE3UKyB5vt6hzfbfYa1MQmXU0hhORials6bV_V2bk"

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseManager:
    """Manager class for all Supabase operations"""
    
    def __init__(self):
        self.client = supabase
        
    def create_tables(self):
        """Create tables if they don't exist (run this once)"""
        # This would typically be done via Supabase dashboard or migration files
        # Including here for reference
        pass
        
    def add_workout(self, workout_data: dict) -> Optional[dict]:
        """Add a new workout to the database"""
        try:
            response = self.client.table('workouts').insert({
                'start_time': workout_data['start_time'],
                'end_time': workout_data['end_time'],
                'distance': workout_data['distance'],
                'steps': workout_data['steps'],
                'duration': workout_data['duration'],
                'workout_type': 'treadmill'
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logging.error(f"Error adding workout: {e}")
            return None
    
    def get_workouts(self, start_date: Optional[datetime] = None, 
                     end_date: Optional[datetime] = None) -> list:
        """Get workouts with optional date filtering"""
        try:
            query = self.client.table('workouts').select('*').eq('workout_type', 'treadmill')
            
            if start_date:
                query = query.gte('start_time', start_date.isoformat())
            if end_date:
                query = query.lte('start_time', end_date.isoformat())
                
            response = query.order('start_time', desc=True).execute()
            return response.data
        except Exception as e:
            logging.error(f"Error getting workouts: {e}")
            return []
    
    def get_pullups_today(self) -> int:
        """Get today's pull-up count"""
        try:
            today = date.today().isoformat()
            response = self.client.table('daily_pullups').select('reps').eq('date', today).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['reps']
            return 0
        except Exception as e:
            logging.error(f"Error getting pull-ups: {e}")
            return 0
    
    def get_pullups_history(self, days: int = 7) -> list:
        """Get pull-up history for the last N days"""
        try:
            start_date = (date.today() - timedelta(days=days-1)).isoformat()
            response = self.client.table('daily_pullups').select('*').gte('date', start_date).order('date').execute()
            return response.data
        except Exception as e:
            logging.error(f"Error getting pull-up history: {e}")
            return []
    
    def update_workout(self, workout_id: int, data: dict) -> bool:
        """Update an existing workout"""
        try:
            response = self.client.table('workouts').update(data).eq('id', workout_id).execute()
            return bool(response.data)
        except Exception as e:
            logging.error(f"Error updating workout: {e}")
            return False
    
    def delete_workout(self, workout_id: int) -> bool:
        """Delete a workout"""
        try:
            response = self.client.table('workouts').delete().eq('id', workout_id).execute()
            return True
        except Exception as e:
            logging.error(f"Error deleting workout: {e}")
            return False
            
    def migrate_from_sqlite(self, sqlite_workouts: list) -> int:
        """Migrate workouts from SQLite to Supabase"""
        migrated_count = 0
        for workout in sqlite_workouts:
            try:
                # Skip if already synced
                if workout.get('synced', False):
                    continue
                    
                workout_data = {
                    'start_time': workout['start_time'],
                    'end_time': workout['end_time'],
                    'distance': workout['distance'],
                    'steps': workout['steps'],
                    'duration': workout['duration'],
                    'workout_type': 'treadmill'
                }
                
                if self.add_workout(workout_data):
                    migrated_count += 1
                    
            except Exception as e:
                logging.error(f"Error migrating workout: {e}")
                continue
                
        return migrated_count
