import sqlite3
import os
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None
from main import app
from db import get_conn

_JERUSALEM_TZ = None
try:
    if ZoneInfo is not None:
        _JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")
except Exception:
    _JERUSALEM_TZ = None


def _now_jerusalem() -> datetime:
    if _JERUSALEM_TZ is None:
        return datetime.now()
    return datetime.now(_JERUSALEM_TZ)


def _pick_airplane_with_seats(cur):
    row = cur.execute(
        """
        SELECT A.ID
        FROM AIRPLANE A
        WHERE EXISTS (SELECT 1 FROM SEAT S WHERE S.Airplane_ID = A.ID)
        ORDER BY A.ID
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else None


def _pick_route(cur):
    # Prefer TLV as origin for easier testing
    row = cur.execute(
        """
        SELECT Origin_airport, Arrival_airport, Flight_duration
        FROM FLIGHT_ROUTE
        WHERE Origin_airport='TLV'
        ORDER BY Arrival_airport
        LIMIT 1
        """
    ).fetchone()
    if not row:
        row = cur.execute(
            "SELECT Origin_airport, Arrival_airport, Flight_duration FROM FLIGHT_ROUTE ORDER BY Origin_airport, Arrival_airport LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"origin": row[0], "dest": row[1], "duration_min": int(row[2])}


def _next_flight_id(cur) -> str:
    mx = cur.execute(
        "SELECT MAX(CAST(SUBSTR(ID,2) AS INTEGER)) FROM FLIGHT WHERE ID LIKE 'F%'"
    ).fetchone()
    n = (mx[0] or 0) + 1
    return f"F{n:05d}"


def _create_flight_with_tickets(cur, *, flight_id: str, origin: str, dest: str, dep_dt: datetime, duration_min: int, airplane_id: int):
    dep_date = dep_dt.date().isoformat()
    dep_time = dep_dt.time().strftime("%H:%M:%S")
    arr_dt = dep_dt + timedelta(minutes=int(duration_min))
    arr_date = arr_dt.date().isoformat()
    arr_time = arr_dt.time().strftime("%H:%M:%S")
    ftype = "Long" if int(duration_min) > 360 else "Short"

    # Skip if an identical route+datetime already exists (avoid duplicate inserts on re-run).
    exists = cur.execute(
        """
        SELECT 1
        FROM FLIGHT
        WHERE Origin_airport=? AND Arrival_airport=?
          AND Date_of_departure=? AND Time_of_departure=?
        LIMIT 1
        """,
        (origin, dest, dep_date, dep_time),
    ).fetchone()
    if exists:
        return None

    cur.execute(
        """
        INSERT INTO FLIGHT(ID, Date_of_departure, Time_of_departure, Status, Arrival_date, Arrival_time, Type, Airplane_ID, Origin_airport, Arrival_airport)
        VALUES(?, ?, ?, 'Active', ?, ?, ?, ?, ?, ?)
        """,
        (flight_id, dep_date, dep_time, arr_date, arr_time, ftype, airplane_id, origin, dest),
    )

    # Create tickets for every seat in the airplane.
    seats = cur.execute(
        "SELECT Class_Type, Row_num, Column_number FROM SEAT WHERE Airplane_ID=? ORDER BY Class_Type, Row_num, Column_number",
        (airplane_id,),
    ).fetchall()
    if not seats:
        return flight_id  # Flight exists; tickets skipped (shouldn't happen with seatful airplane)

    # Simple realistic-ish pricing
    regular_price = 120.0 if ftype == "Short" else 240.0
    first_price = regular_price * 1.8

    ticket_rows = []
    for cls, row_num, col in seats:
        price = regular_price if cls == "Regular" else first_price
        ticket_rows.append((airplane_id, flight_id, int(row_num), str(col), str(cls), float(price)))

    cur.executemany(
        """
        INSERT INTO TICKET(Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type, Price, Availability)
        VALUES(?, ?, ?, ?, ?, ?, 1)
        """,
        ticket_rows,
    )
    return flight_id


def add_time_based_test_data():
    """
    Add small dynamic dataset for QA:
    - Flight departing ~1 hour ago (should be blocked)
    - Flight departing ~now (+1 minute, so you can still click through)
    - Flight departing ~1 hour from now (should be bookable)
    """
    print("Adding time-based test flights (Jerusalem time)...")
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    route = _pick_route(cur)
    airplane_id = _pick_airplane_with_seats(cur)
    if not route or airplane_id is None:
        print("Skipping time-based test flights: missing FLIGHT_ROUTE or airplane seats.")
        return

    now = _now_jerusalem().replace(second=0, microsecond=0)
    dep_list = [
        now - timedelta(hours=1),
        now + timedelta(minutes=1),  # near-now but stable for clicking through
        now + timedelta(hours=1),
    ]

    created = []
    for dep_dt in dep_list:
        fid = _next_flight_id(cur)
        new_id = _create_flight_with_tickets(
            cur,
            flight_id=fid,
            origin=route["origin"],
            dest=route["dest"],
            dep_dt=dep_dt,
            duration_min=route["duration_min"],
            airplane_id=airplane_id,
        )
        if new_id:
            created.append(new_id)

    conn.commit()
    if created:
        print(f"Added {len(created)} time-based test flight(s): {', '.join(created)}")
    else:
        print("No new time-based flights added (they may already exist).")


def add_more_realistic_upcoming_flights():
    """Add a few extra upcoming flights in the next days for more realistic browsing."""
    print("Adding extra upcoming flights...")
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    route = _pick_route(cur)
    airplane_id = _pick_airplane_with_seats(cur)
    if not route or airplane_id is None:
        print("Skipping extra flights: missing FLIGHT_ROUTE or airplane seats.")
        return

    now = _now_jerusalem().replace(second=0, microsecond=0)
    # Small set: next 3 days, 3 departures/day
    dep_times = [(8, 0), (12, 0), (17, 30)]
    created = []
    for day in range(1, 4):
        base = now + timedelta(days=day)
        for hh, mm in dep_times:
            dep_dt = base.replace(hour=hh, minute=mm)
            fid = _next_flight_id(cur)
            new_id = _create_flight_with_tickets(
                cur,
                flight_id=fid,
                origin=route["origin"],
                dest=route["dest"],
                dep_dt=dep_dt,
                duration_min=route["duration_min"],
                airplane_id=airplane_id,
            )
            if new_id:
                created.append(new_id)

    conn.commit()
    if created:
        print(f"Added {len(created)} extra upcoming flight(s).")
    else:
        print("No new extra flights added (they may already exist).")


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
            # After loading the SQL data, append a small dynamic dataset for QA
            try:
                add_time_based_test_data()
                add_more_realistic_upcoming_flights()
            except Exception as e:
                print(f"Warning: failed to add extra test data: {e}")
        except Exception as e:
            print(f"Error seeding data: {e}")
            raise
    else:
        print("sql/flytau_data.sql not found!")

if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_data()
