"""
Database Initialization Script

This script initializes the database by creating all tables defined in the models.
"""

import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.database import engine, Base
    import backend.models  # Ensure models are registered
    
    print("🚀 Initializing database...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database initialized successfully!")
    print(f"📍 Database file: {os.path.abspath('crypto_agent.db')}")

except Exception as e:
    print(f"❌ Error initializing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("Database initialization complete.")
