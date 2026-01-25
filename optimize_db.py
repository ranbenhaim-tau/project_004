import sqlite3
import os

DB_NAME = "flytau.db"

def optimize():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found in current directory!")
        return

    print(f"Connecting to {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    
    indices = [
        # Critical for flight search performance (joins TICKET by Flight_ID)
        "CREATE INDEX IF NOT EXISTS idx_ticket_flight_id ON TICKET(Flight_ID);",
        
        # Critical for filtering flights by date/route
        "CREATE INDEX IF NOT EXISTS idx_flight_date ON FLIGHT(Date_of_departure);",
        "CREATE INDEX IF NOT EXISTS idx_flight_origin ON FLIGHT(Origin_airport);",
        "CREATE INDEX IF NOT EXISTS idx_flight_dest ON FLIGHT(Arrival_airport);",
        "CREATE INDEX IF NOT EXISTS idx_flight_status ON FLIGHT(Status);",

        # Availability/location checks for manager flight creation
        "CREATE INDEX IF NOT EXISTS idx_flight_airplane_dep ON FLIGHT(Airplane_ID, Date_of_departure, Time_of_departure);",
        "CREATE INDEX IF NOT EXISTS idx_flight_airplane_arr ON FLIGHT(Airplane_ID, Arrival_date, Arrival_time);",
        "CREATE INDEX IF NOT EXISTS idx_aircrew_assignment_aircrew ON AIRCREW_ASSIGNMENT(Aircrew_ID);",
        "CREATE INDEX IF NOT EXISTS idx_aircrew_assignment_flight ON AIRCREW_ASSIGNMENT(Flight_ID);",
    ]
    
    for sql in indices:
        print(f"Executing: {sql}")
        try:
            conn.execute(sql)
        except Exception as e:
            print(f"Error: {e}")
            
    conn.commit()
    conn.close()
    print("Optimization complete. Indices added.")

if __name__ == "__main__":
    optimize()
