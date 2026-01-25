import sqlite3
import os
from main import app
from db import get_conn

def init_db():
    print("Initializing Database from sql/flytau_schema.sql...")
    conn = get_conn()
    
    # Read schema file
    try:
        with open('sql/flytau_schema.sql', 'r') as f:
            schema_sql = f.read()
            
        conn.executescript(schema_sql)
        print("Schema created.")
    except Exception as e:
        print(f"Error creating schema: {e}")
        raise

def seed_data():
    print("Seeding Data from sql/flytau_data.sql...")
    conn = get_conn()
    # Disable FK checks for seeding because data might be out of order
    conn.execute("PRAGMA foreign_keys = OFF")
    
    # Read data file
    if os.path.exists('sql/flytau_data.sql'):
        try:
            with open('sql/flytau_data.sql', 'r') as f:
                # Read line by line to find error
                statement = ""
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('--'):
                        continue
                    statement += line + " "
                    if line.endswith(';'):
                        try:
                            conn.execute(statement)
                            statement = ""
                        except Exception as e:
                            print(f"Error on line {line_num}: {e}")
                            print(f"Statement: {statement[:100]}...")
                            raise
            
            conn.commit()
            print("Data seeded successfully.")
        except Exception as e:
            print(f"Error seeding data: {e}")
            raise
    else:
        print("sql/flytau_data.sql not found!")

if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_data()
