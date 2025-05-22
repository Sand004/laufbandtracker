"""
Quick setup script for Fitness Tracker Pro
"""
import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"   Your version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_dependencies():
    """Install required packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies!")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    if not Path(".env").exists():
        print("\n❌ .env file not found!")
        print("   Please copy .env.example to .env and update with your credentials")
        return False
    
    print("\n✅ .env file found")
    
    # Check for required variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables are set")
    return True

def check_supabase_connection():
    """Test Supabase connection"""
    print("\n🔍 Testing Supabase connection...")
    try:
        from supabase_config import SupabaseManager
        manager = SupabaseManager()
        
        # Try to get workouts (should work even if empty)
        workouts = manager.get_workouts()
        print(f"✅ Supabase connection successful!")
        print(f"   Found {len(workouts)} existing workouts")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("   Please check your credentials and database setup")
        return False

def check_sqlite_database():
    """Check for existing SQLite database"""
    db_path = "treadmill_workouts.db"
    if Path(db_path).exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workouts")
            count = cursor.fetchone()[0]
            conn.close()
            
            if count > 0:
                print(f"\n📊 Found existing SQLite database with {count} workouts")
                response = input("   Would you like to migrate them to Supabase? (y/n): ")
                return response.lower() == 'y'
        except Exception as e:
            print(f"⚠️  Error reading SQLite database: {e}")
    return False

def run_migration():
    """Run the migration script"""
    print("\n🚀 Starting migration...")
    try:
        subprocess.check_call([sys.executable, "migrate_to_supabase.py"])
        print("✅ Migration completed!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Migration failed!")
        return False

def main():
    """Main setup process"""
    print("====================================")
    print("🏃‍♂️ Fitness Tracker Pro - Setup")
    print("====================================")
    
    # Check Python version
    if not check_python_version():
        return
    
    # Install dependencies
    if not install_dependencies():
        print("\n⚠️  Please install dependencies manually:")
        print("   pip install -r requirements.txt")
        return
    
    # Check environment configuration
    if not check_env_file():
        print("\n📝 Setup Instructions:")
        print("1. Copy .env.example to .env")
        print("2. Update SUPABASE_URL and SUPABASE_KEY with your credentials")
        print("3. Run this setup script again")
        return
    
    # Test Supabase connection
    if not check_supabase_connection():
        print("\n📝 Supabase Setup Instructions:")
        print("1. Create a project at https://supabase.com")
        print("2. Run the SQL from supabase_schema.sql in the SQL editor")
        print("3. Update your .env file with the correct credentials")
        print("4. Run this setup script again")
        return
    
    # Check for existing data to migrate
    if check_sqlite_database():
        run_migration()
    
    print("\n✨ Setup completed successfully!")
    print("\n🚀 You can now run the application:")
    print("   python treadmill_app_modern.py")
    print("\n💡 Tips:")
    print("   - Make sure Bluetooth is enabled for treadmill connection")
    print("   - The ESP32 pull-up sensor should be configured with the same Supabase credentials")
    print("   - Check the README.md for detailed usage instructions")

if __name__ == "__main__":
    main()
