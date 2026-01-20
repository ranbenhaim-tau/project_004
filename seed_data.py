import sqlite3
from datetime import date, datetime, timedelta
from main import app
from db import execute, query_one, query_all, get_conn

def init_db():
    print("Initializing Database...")
    
    # Enable foreign keys support
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys = OFF") # Disable temporarily for drops
    
    tables = [
        "AIRCREW_ASSIGNMENT", "TICKET_ORDER", "TICKET", "FLIGHT", "SEAT", "CLASS", 
        "AIRPLANE", "PHONE_NUMBER_MEMBER", "PHONE_NUMBER_GUEST", "`ORDER`", 
        "MEMBER", "GUEST", "FLIGHT_ROUTE", "AIRCREW", "MANAGER"
    ]
    
    for t in tables:
        execute(f"DROP TABLE IF EXISTS {t}")
        
    conn.execute("PRAGMA foreign_keys = ON")

    # Create Tables
    schema = [
        """CREATE TABLE MANAGER (
            ID TEXT NOT NULL PRIMARY KEY,
            City TEXT NOT NULL,
            Street TEXT NOT NULL,
            House_Number TEXT NOT NULL,
            Start_date_of_employment TEXT NOT NULL,
            First_name TEXT NOT NULL,
            Last_name TEXT NOT NULL,
            Phone_number TEXT NOT NULL,
            Password TEXT NOT NULL
        )""",
        """CREATE TABLE AIRCREW (
            ID INTEGER NOT NULL PRIMARY KEY,
            City TEXT NOT NULL,
            Street TEXT NOT NULL,
            House_Number TEXT NOT NULL,
            Start_date_of_employment TEXT NOT NULL,
            First_name TEXT NOT NULL,
            Last_name TEXT NOT NULL,
            Phone_number TEXT NOT NULL,
            Type TEXT NOT NULL CHECK(Type IN ('Pilot','Flight attendant')),
            Training INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE FLIGHT_ROUTE (
            Origin_airport TEXT NOT NULL,
            Arrival_airport TEXT NOT NULL,
            Flight_duration INTEGER NOT NULL,
            PRIMARY KEY (Origin_airport, Arrival_airport),
            CHECK (Flight_duration > 0)
        )""",
        """CREATE TABLE GUEST (
            Email TEXT NOT NULL PRIMARY KEY,
            First_name_in_English TEXT NOT NULL,
            Last_name_in_English TEXT NOT NULL
        )""",
        """CREATE TABLE MEMBER (
            Email TEXT NOT NULL PRIMARY KEY,
            First_name_in_English TEXT NOT NULL,
            Last_name_in_English TEXT NOT NULL,
            Passport_number TEXT NOT NULL,
            Date_of_birth TEXT NOT NULL,
            Register_date TEXT NOT NULL,
            Password TEXT NOT NULL
        )""",
        """CREATE TABLE "ORDER" (
            ID INTEGER NOT NULL PRIMARY KEY,
            Status TEXT NOT NULL CHECK(Status IN ('Active','Completed','Customer Cancellation','System Cancellation')),
            Total_price REAL NOT NULL,
            Date_of_purchase TEXT NOT NULL,
            Cancellation_fee REAL NOT NULL DEFAULT 0,
            GUEST_Email TEXT,
            MEMBER_Email TEXT,
            FOREIGN KEY (GUEST_Email) REFERENCES GUEST(Email) ON UPDATE CASCADE,
            FOREIGN KEY (MEMBER_Email) REFERENCES MEMBER(Email) ON UPDATE CASCADE
        )""",
        """CREATE TABLE PHONE_NUMBER_GUEST (
            Email TEXT NOT NULL,
            Phone_number TEXT NOT NULL,
            PRIMARY KEY (Email, Phone_number),
            FOREIGN KEY (Email) REFERENCES GUEST(Email) ON UPDATE CASCADE
        )""",
        """CREATE TABLE PHONE_NUMBER_MEMBER (
            Email TEXT NOT NULL,
            Phone_number TEXT NOT NULL,
            PRIMARY KEY (Email, Phone_number),
            FOREIGN KEY (Email) REFERENCES MEMBER(Email) ON UPDATE CASCADE
        )""",
        """CREATE TABLE AIRPLANE (
            ID INTEGER NOT NULL PRIMARY KEY,
            Date_of_purchase TEXT NOT NULL,
            Manufacturer TEXT NOT NULL CHECK(Manufacturer IN ('Boeing','Airbus','Dassault')),
            Size TEXT NOT NULL CHECK(Size IN ('Big','Small'))
        )""",
        """CREATE TABLE CLASS (
            Type TEXT NOT NULL CHECK(Type IN ('First','Regular')),
            Airplane_ID INTEGER NOT NULL,
            Number_of_rows INTEGER NOT NULL,
            Number_of_columns INTEGER NOT NULL,
            PRIMARY KEY (Airplane_ID, Type),
            FOREIGN KEY (Airplane_ID) REFERENCES AIRPLANE(ID) ON UPDATE CASCADE,
            CHECK (Number_of_rows > 0 AND Number_of_columns > 0)
        )""",
        """CREATE TABLE SEAT (
            Class_Type TEXT NOT NULL CHECK(Class_Type IN ('First','Regular')),
            Airplane_ID INTEGER NOT NULL,
            Row_num INTEGER NOT NULL,
            Column_number TEXT NOT NULL,
            PRIMARY KEY (Airplane_ID, Class_Type, Row_num, Column_number),
            FOREIGN KEY (Airplane_ID, Class_Type) REFERENCES CLASS(Airplane_ID, Type) ON UPDATE CASCADE,
            CHECK (Column_number BETWEEN 'A' AND 'Z'),
            CHECK (Row_num > 0)
        )""",
        """CREATE TABLE FLIGHT (
            ID TEXT NOT NULL PRIMARY KEY,
            Date_of_departure TEXT NOT NULL,
            Time_of_departure TEXT NOT NULL,
            Status TEXT NOT NULL DEFAULT 'Active' CHECK(Status IN ('Active','Full','Completed','Canceled')),
            Arrival_date TEXT NOT NULL,
            Arrival_time TEXT NOT NULL,
            Type TEXT NOT NULL CHECK(Type IN ('Long','Short')),
            Airplane_ID INTEGER NOT NULL,
            Origin_airport TEXT NOT NULL,
            Arrival_airport TEXT NOT NULL,
            FOREIGN KEY (Airplane_ID) REFERENCES AIRPLANE(ID) ON UPDATE CASCADE,
            FOREIGN KEY (Origin_airport, Arrival_airport) REFERENCES FLIGHT_ROUTE(Origin_airport, Arrival_airport) ON UPDATE CASCADE
        )""",
        """CREATE TABLE TICKET (
            Airplane_ID INTEGER NOT NULL,
            Flight_ID TEXT NOT NULL,
            SEAT_Row_num INTEGER NOT NULL,
            SEAT_Column_number TEXT NOT NULL,
            CLASS_Type TEXT NOT NULL CHECK(CLASS_Type IN ('First','Regular')),
            Price REAL NOT NULL,
            Availability INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type),
            FOREIGN KEY (Airplane_ID, CLASS_Type, SEAT_Row_num, SEAT_Column_number) REFERENCES SEAT(Airplane_ID, Class_Type, Row_num, Column_number) ON UPDATE CASCADE,
            FOREIGN KEY (Flight_ID) REFERENCES FLIGHT(ID) ON UPDATE CASCADE
        )""",
        """CREATE TABLE TICKET_ORDER (
            Airplane_ID INTEGER NOT NULL,
            Flight_ID TEXT NOT NULL,
            SEAT_Row_num INTEGER NOT NULL,
            SEAT_Column_number TEXT NOT NULL,
            CLASS_Type TEXT NOT NULL CHECK(CLASS_Type IN ('First','Regular')),
            Order_ID INTEGER NOT NULL,
            PRIMARY KEY (Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type, Order_ID),
            FOREIGN KEY (Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type) REFERENCES TICKET(Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type) ON UPDATE CASCADE,
            FOREIGN KEY (Order_ID) REFERENCES "ORDER"(ID) ON UPDATE CASCADE
        )""",
        """CREATE TABLE AIRCREW_ASSIGNMENT (
            Aircrew_ID INTEGER NOT NULL,
            Flight_ID TEXT NOT NULL,
            PRIMARY KEY (Aircrew_ID, Flight_ID),
            FOREIGN KEY (Aircrew_ID) REFERENCES AIRCREW(ID) ON UPDATE CASCADE,
            FOREIGN KEY (Flight_ID) REFERENCES FLIGHT(ID) ON UPDATE CASCADE
        )"""
    ]

    for sql in schema:
        execute(sql)
    print("Schema created.")

def seed_data():
    print("Seeding Data...")
    
    # 1. 2 Admins
    admins = [
        ("100000001", "Tel Aviv", "Herzl", "1", "2020-01-01", "Admin", "One", "0500000001", "admin123"),
        ("100000002", "Haifa", "Ben Gurion", "2", "2020-02-01", "Admin", "Two", "0500000002", "admin456")
    ]
    for a in admins:
        execute("INSERT OR IGNORE INTO MANAGER VALUES (?,?,?,?,?,?,?,?,?)", a)

    # 2. 2 Registered Users
    members = [
        ("member1@example.com", "John", "Doe", "A1234567", "1990-01-01", "2023-01-01", "pass1"),
        ("member2@example.com", "Jane", "Smith", "B7654321", "1992-05-15", "2023-02-01", "pass2")
    ]
    for m in members:
        execute("INSERT OR IGNORE INTO MEMBER VALUES (?,?,?,?,?,?,?)", m)
        execute("INSERT OR IGNORE INTO PHONE_NUMBER_MEMBER VALUES (?,?)", (m[0], "0501111111"))

    # 3. 2 Guests
    guests = [
        ("guest1@example.com", "Guest", "One"),
        ("guest2@example.com", "Guest", "Two")
    ]
    for g in guests:
        execute("INSERT OR IGNORE INTO GUEST VALUES (?,?,?)", g)

    # 4. 10 Pilots & 5. 20 Flight Attendants
    # Total 30 Aircrew
    # ID start from 100
    base_id = 100
    for i in range(1, 31):
        role = 'Pilot' if i <= 10 else 'Flight attendant'
        training = 1
        execute("INSERT OR IGNORE INTO AIRCREW VALUES (?,?,?,?,?,?,?,?,?,?)", 
                (base_id + i, "City", "Street", "1", "2021-01-01", f"Crew{i}", "Last", "0500000000", role, training))

    # 6. 6 Airplanes (Mix)
    planes = [
        (1, "2015-01-01", "Boeing", "Big"),
        (2, "2016-01-01", "Airbus", "Big"),
        (3, "2017-01-01", "Dassault", "Small"),
        (4, "2018-01-01", "Boeing", "Small"),
        (5, "2019-01-01", "Airbus", "Small"),
        (6, "2020-01-01", "Dassault", "Small")
    ]
    for p in planes:
        execute("INSERT OR IGNORE INTO AIRPLANE VALUES (?,?,?,?)", p)
        # Create Classes and Seats for planes
        # Simplified: Small has 1 class, Big has 2
        if p[3] == 'Big':
            execute("INSERT OR IGNORE INTO CLASS VALUES (?,?,?,?)", ('First', p[0], 2, 2)) # 4 seats
            execute("INSERT OR IGNORE INTO CLASS VALUES (?,?,?,?)", ('Regular', p[0], 5, 4)) # 20 seats
        else:
            execute("INSERT OR IGNORE INTO CLASS VALUES (?,?,?,?)", ('Regular', p[0], 5, 4)) # 20 seats

        # Generate seats
        classes = query_all("SELECT * FROM CLASS WHERE Airplane_ID=?", (p[0],))
        for c in classes:
            for r in range(1, c['Number_of_rows'] + 1):
                for col_idx in range(c['Number_of_columns']):
                    col_char = chr(ord('A') + col_idx)
                    execute("INSERT OR IGNORE INTO SEAT VALUES (?,?,?,?)", (c['Type'], p[0], r, col_char))

    # Flight Routes (Need some to create flights)
    routes = [
        ('TLV', 'JFK', 660),
        ('JFK', 'TLV', 660),
        ('TLV', 'LHR', 300),
        ('LHR', 'TLV', 300)
    ]
    for r in routes:
        execute("INSERT OR IGNORE INTO FLIGHT_ROUTE VALUES (?,?,?)", r)

    # 7. 4 Active Flights
    flights = [
        ("FL001", date.today().isoformat(), "10:00:00", "Active", date.today().isoformat(), "21:00:00", "Long", 1, "TLV", "JFK"),
        ("FL002", (date.today() + timedelta(days=1)).isoformat(), "14:00:00", "Active", (date.today() + timedelta(days=1)).isoformat(), "19:00:00", "Short", 3, "TLV", "LHR"),
        ("FL003", (date.today() + timedelta(days=2)).isoformat(), "08:00:00", "Active", (date.today() + timedelta(days=2)).isoformat(), "13:00:00", "Short", 4, "LHR", "TLV"),
        ("FL004", (date.today() + timedelta(days=3)).isoformat(), "23:00:00", "Active", (date.today() + timedelta(days=4)).isoformat(), "10:00:00", "Long", 2, "JFK", "TLV")
    ]
    for f in flights:
        execute("INSERT OR IGNORE INTO FLIGHT VALUES (?,?,?,?,?,?,?,?,?,?)", f)
        # Generate Tickets for flights
        # For each seat in the airplane, create a ticket
        seats = query_all("SELECT * FROM SEAT WHERE Airplane_ID=?", (f[7],))
        price = 1000 if f[6] == 'Long' else 500
        for s in seats:
            p = price * 2 if s['Class_Type'] == 'First' else price
            execute("INSERT OR IGNORE INTO TICKET VALUES (?,?,?,?,?,?,?)", 
                    (f[7], f[0], s['Row_num'], s['Column_number'], s['Class_Type'], p, 1))

    # 8. 4 Orders
    # We need to book some tickets
    orders = [
        (1, "Active", 1000, date.today().isoformat(), 0, None, "member1@example.com"),
        (2, "Active", 500, date.today().isoformat(), 0, None, "member2@example.com"),
        (3, "Active", 1000, date.today().isoformat(), 0, "guest1@example.com", None),
        (4, "Active", 500, date.today().isoformat(), 0, "guest2@example.com", None)
    ]
    
    for i, o in enumerate(orders):
        execute("INSERT OR IGNORE INTO `ORDER` VALUES (?,?,?,?,?,?,?)", o)
        # Link a ticket
        flight_id = flights[i][0]
        airplane_id = flights[i][7]
        # Find an available ticket
        ticket = query_one("""
            SELECT * FROM TICKET 
            WHERE Flight_ID=? AND Airplane_ID=? AND Availability=1 
            LIMIT 1
        """, (flight_id, airplane_id))
        
        if ticket:
            # Mark ticket unavailable
            execute("""
                UPDATE TICKET SET Availability=0 
                WHERE Flight_ID=? AND Airplane_ID=? AND SEAT_Row_num=? AND SEAT_Column_number=? AND CLASS_Type=?
            """, (ticket['Flight_ID'], ticket['Airplane_ID'], ticket['SEAT_Row_num'], ticket['SEAT_Column_number'], ticket['CLASS_Type']))
            
            # Create Ticket Order
            execute("INSERT OR IGNORE INTO TICKET_ORDER VALUES (?,?,?,?,?,?)",
                   (ticket['Airplane_ID'], ticket['Flight_ID'], ticket['SEAT_Row_num'], ticket['SEAT_Column_number'], ticket['CLASS_Type'], o[0]))

    print("Data seeded successfully.")

if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_data()
