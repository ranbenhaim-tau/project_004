from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from dotenv import load_dotenv
from datetime import date, datetime
import os
import io
import csv
import re
import time
import random

from config import Config
from db import query_one, query_all, execute, executemany, get_conn
from utils import parse_date, parse_time, add_minutes_to_dt, hours_until

# Chart.js is used for interactive charts (loaded via CDN in templates)

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# ----------------- Input validation helpers -----------------
# English name: allow letters with optional spaces/hyphens/apostrophes (e.g., "Anne-Marie", "O'Neil").
# We keep it intentionally simple and consistent across the site.
_EN_NAME_RE = re.compile(r"^[A-Za-z](?:[A-Za-z \-']{0,48}[A-Za-z])?$")


def _is_valid_english_name(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    return _EN_NAME_RE.fullmatch(value) is not None


def _parse_positive_int(value: str):
    """Return int(value) if it's a positive integer, otherwise None."""
    s = (value or "").strip()
    if not s.isdigit():
        return None
    try:
        n = int(s)
    except Exception:
        return None
    return n if n > 0 else None

# When the server restarts, we want any previously issued session cookies to be treated as logged out.
# We do this by storing a lightweight boot marker in the session and clearing the session if it differs.
# Using a second-resolution timestamp makes it stable across multi-process starts that happen together.
_SERVER_BOOT_ID = str(int(time.time()))


@app.before_request
def _logout_on_server_restart():
    """Force logout when the Flask server process group restarts."""
    try:
        prev = session.get("_server_boot_id")
        if prev is not None and prev != _SERVER_BOOT_ID:
            session.clear()
        session["_server_boot_id"] = _SERVER_BOOT_ID
    except Exception:
        # Never block a request.
        pass

# --- Auto status refresh (fallback if MySQL EVENT scheduler is disabled) ---
# Periodically mark flights and related active orders as Completed once the *departure* timestamp has passed.
_LAST_FLIGHT_STATUS_REFRESH = {"ts": None}


@app.before_request
def _auto_complete_flights():
    """Best-effort status refresh.

    Some MySQL installations have the EVENT scheduler disabled by default.
    This lightweight fallback keeps the UI consistent without requiring DB-level jobs.
    """
    try:
        now = datetime.now()
        last = _LAST_FLIGHT_STATUS_REFRESH["ts"]
        if last is None or (now - last).total_seconds() >= 300:
            # 1) Flights become Completed once they *depart* (per project requirements).
            execute(
                """
                UPDATE FLIGHT
                SET Status='Completed'
                WHERE Status IN ('Active','Full')
                  AND datetime(Date_of_departure || ' ' || Time_of_departure) <= datetime('now', 'localtime')
                """
            )

            # 2) Member orders become Completed once their flight departs.
            #    (Orders that were canceled by customer/system must keep their cancellation status.)
            execute(
                """
                UPDATE "ORDER"
                SET Status = 'Completed'
                WHERE Status = 'Active'
                  AND ID IN (
                    SELECT TO1.Order_ID
                    FROM TICKET_ORDER TO1
                    JOIN FLIGHT F ON F.ID = TO1.Flight_ID
                    WHERE datetime(F.Date_of_departure || ' ' || F.Time_of_departure) <= datetime('now', 'localtime')
                  )
                """
            )
            _LAST_FLIGHT_STATUS_REFRESH["ts"] = now
    except Exception:
        # Never block a request because of a refresh failure.
        pass


# ---------- JINJA HELPERS ----------
@app.template_filter('currency')
def currency_filter(value):
    """Format number as currency with commas and 2 decimal places."""
    try:
        num = float(value)
        return f"${num:,.2f}"
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('hm')
def hm(value):
    """Format time-like values as HH:MM (drop seconds)."""
    if value is None:
        return ""

    # datetime.time
    try:
        from datetime import time as _time
        if isinstance(value, _time):
            return value.strftime('%H:%M')
    except Exception:
        pass

    # timedelta (some MySQL drivers may return TIME as timedelta)
    try:
        from datetime import timedelta as _td
        if isinstance(value, _td):
            total = int(value.total_seconds())
            h = (total // 3600) % 24
            m = (total % 3600) // 60
            return f"{h:02d}:{m:02d}"
    except Exception:
        pass

    # string fallback
    s = str(value)
    # Common: HH:MM:SS -> HH:MM
    if len(s) >= 5 and s[2] == ':' and s[5:6] in (':', ''):
        return s[:5]
    return s

# Airport labels (used in dropdowns)
AIRPORT_LABELS = {
    'TLV': 'TLV — Tel Aviv',
    'JFK': 'JFK — New York',
    'LHR': 'LHR — London Heathrow',
    'CDG': 'CDG — Paris',
    'FRA': 'FRA — Frankfurt',
    'AMS': 'AMS — Amsterdam',
    'MAD': 'MAD — Madrid',
    'BCN': 'BCN — Barcelona',
    'ATH': 'ATH — Athens',
    'FCO': 'FCO — Rome Fiumicino',
    'MUC': 'MUC — Munich',
    'ZRH': 'ZRH — Zurich',
    'VIE': 'VIE — Vienna',
    'BRU': 'BRU — Brussels',
    'CPH': 'CPH — Copenhagen',
    'ARN': 'ARN — Stockholm',
    'OSL': 'OSL — Oslo',
    'HEL': 'HEL — Helsinki',
    'WAW': 'WAW — Warsaw',
    'PRG': 'PRG — Prague',
    'BUD': 'BUD — Budapest',
    'IST': 'IST — Istanbul',
    'DXB': 'DXB — Dubai',
    'DOH': 'DOH — Doha',
    'CAI': 'CAI — Cairo',
    'NBO': 'NBO — Nairobi',
    'JNB': 'JNB — Johannesburg',
    'DEL': 'DEL — Delhi',
    'BOM': 'BOM — Mumbai',
    'BKK': 'BKK — Bangkok',
    'SIN': 'SIN — Singapore',
    'HKG': 'HKG — Hong Kong',
    'PEK': 'PEK — Beijing',
    'PVG': 'PVG — Shanghai',
    'ICN': 'ICN — Seoul',
    'HND': 'HND — Tokyo Haneda',
    'KIX': 'KIX — Osaka',
    'SYD': 'SYD — Sydney',
    'MEL': 'MEL — Melbourne',
    'AKL': 'AKL — Auckland',
    'GRU': 'GRU — Sao Paulo',
    'EZE': 'EZE — Buenos Aires',
    'MEX': 'MEX — Mexico City',
    'LAX': 'LAX — Los Angeles',
    'SFO': 'SFO — San Francisco',
}

def is_logged_in(role=None):
    if "role" not in session:
        return False
    return role is None or session.get("role") == role

@app.context_processor
def inject_globals():
    return dict(
        session_role=session.get("role"),
        session_user=session.get("user"),
    )

@app.route("/")
def index():
    session.pop("force_login_member", None)
    return render_template("index.html")

# ---------- AUTH ----------
# Separate login pages (member / manager)

@app.route("/login")
def login():
    return render_template("login_hub.html")

@app.route("/login/member", methods=["GET","POST"])
def login_member():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pwd = request.form.get("password","")
        u = query_one(
            "SELECT Email, First_name_in_English, Last_name_in_English FROM MEMBER WHERE Email=%s AND Password=%s",
            (email, pwd)
        )
        if not u:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login_member"))
        session["role"] = "member"
        session["user"] = u["Email"]
        session["user_name"] = f'{u["First_name_in_English"]} {u["Last_name_in_English"]}'
        flash("Logged in successfully.", "success")
        session.pop("force_login_member", None)
        next_url = session.pop("next_url", None)
        return redirect(next_url) if next_url else redirect(url_for("index"))
    return render_template("login_member.html")

@app.route("/login/manager", methods=["GET","POST"])
def login_manager():
    if request.method == "POST":
        mid = request.form.get("manager_id","").strip()
        pwd = request.form.get("password","")
        u = query_one("SELECT ID, First_name, Last_name FROM MANAGER WHERE ID=%s AND Password=%s", (mid, pwd))
        if not u:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login_manager"))
        session["role"] = "manager"
        session["user"] = u["ID"]
        session["user_name"] = f'{u["First_name"]} {u["Last_name"]}'
        flash("Logged in as manager.", "success")
        session.pop("force_login_member", None)
        return redirect(url_for("manager_dashboard"))
    return render_template("login_manager.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/register", methods=["GET","POST"])
def register():
    # Customers must be 18+ years old
    today = date.today()
    try:
        max_dob_date = today.replace(year=today.year - 18)
    except ValueError:
        # Handle Feb 29 on non-leap years
        max_dob_date = today.replace(month=2, day=28, year=today.year - 18)
    max_dob = max_dob_date.isoformat()

    if request.method == "POST":
        email = request.form.get("email","").strip()
        first = request.form.get("first","").strip()
        last = request.form.get("last","").strip()
        passport = request.form.get("passport","").strip()
        dob = request.form.get("dob","").strip()
        phone = request.form.get("phone","").strip()
        pwd = request.form.get("password","")
        if not (email and first and last and passport and dob and phone and pwd):
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("register"))

        # Names must be provided in English letters.
        if not _is_valid_english_name(first):
            flash("Please enter a valid first name using English letters only.", "warning")
            return redirect(url_for("register"))
        if not _is_valid_english_name(last):
            flash("Please enter a valid last name using English letters only.", "warning")
            return redirect(url_for("register"))

        # Server-side age validation (do not rely only on the browser)
        try:
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
        except Exception:
            flash("Invalid date of birth.", "danger")
            return redirect(url_for("register"))

        if dob_date > max_dob_date:
            flash("You must be at least 18 years old to create an account.", "danger")
            return redirect(url_for("register"))

        exists = query_one("SELECT 1 AS x FROM MEMBER WHERE Email=%s", (email,))
        if exists:
            flash("This email is already registered.", "danger")
            return redirect(url_for("register"))

        execute(
            "INSERT INTO MEMBER(Email, First_name_in_English, Last_name_in_English, Passport_number, Date_of_birth, Register_date, Password) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (email, first, last, passport, dob, date.today().isoformat(), pwd)
        )
        execute("INSERT INTO PHONE_NUMBER_MEMBER(Email, Phone_number) VALUES(%s,%s)", (email, phone))
        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", max_dob=max_dob)

# ---------- CUSTOMER: FLIGHTS + PURCHASE ----------
@app.route("/flights/search", methods=["GET"])
def flights_search():
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    # Allow everyone to browse. Show flights that are still bookable (not departed yet).
    dep_date = request.args.get("dep_date","").strip()
    origin = request.args.get("origin","").strip().upper()
    dest = request.args.get("dest","").strip().upper()

    params = []
    # "Open for sale" means: Active/Full AND not departed yet AND at least one available seat.
    where = [
        "F.Status IN ('Active','Full')",
        "datetime(F.Date_of_departure || ' ' || F.Time_of_departure) >= datetime('now', 'localtime')"
    ]

    if dep_date:
        where.append("F.Date_of_departure = %s")
        params.append(dep_date)
    if origin:
        where.append("F.Origin_airport = %s")
        params.append(origin)
    if dest:
        where.append("F.Arrival_airport = %s")
        params.append(dest)

    where_sql = "WHERE " + " AND ".join(where)

    flights = query_all(f"""
        SELECT
            F.*,
            A.Manufacturer, A.Size,
            (SELECT MIN(Price) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.CLASS_Type='Regular') AS price_regular,
            (SELECT MIN(Price) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.CLASS_Type='First') AS price_first,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID) AS total_tickets,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.Availability=1) AS available_tickets
        FROM FLIGHT F
        JOIN AIRPLANE A ON A.ID = F.Airplane_ID
        {where_sql}
        ORDER BY F.Date_of_departure, F.Time_of_departure, F.ID
        LIMIT 200
    """, tuple(params))

    return render_template("flights_search.html", flights=flights, dep_date=dep_date, origin=origin, dest=dest)
# ---------- CUSTOMER: SEARCH API (for dropdowns + calendar) ----------
@app.route("/api/origins")
def api_origins():
    rows = query_all("SELECT DISTINCT Origin_airport AS code FROM FLIGHT_ROUTE ORDER BY Origin_airport")
    origins = [{"code": r["code"], "label": AIRPORT_LABELS.get(r["code"], r["code"])} for r in rows]
    return {"origins": origins}

@app.route("/api/destinations")
def api_destinations():
    origin = request.args.get("origin","").strip().upper()
    if not origin:
        return {"destinations": []}
    rows = query_all(
        "SELECT DISTINCT Arrival_airport AS code FROM FLIGHT_ROUTE WHERE Origin_airport=%s ORDER BY Arrival_airport",
        (origin,)
    )
    destinations = [{"code": r["code"], "label": AIRPORT_LABELS.get(r["code"], r["code"])} for r in rows]
    return {"destinations": destinations}

@app.route("/api/available_dates")
def api_available_dates():
    origin = request.args.get("origin","").strip().upper()
    dest = request.args.get("dest","").strip().upper()
    if not (origin and dest):
        return {"dates": []}

    # Only show dates that can actually be booked (Active/Full), that are not yet departed,
    # and that still have at least one available seat.
    rows = query_all(
        """
        SELECT DISTINCT Date_of_departure AS d
        FROM FLIGHT
        WHERE Origin_airport=%s AND Arrival_airport=%s
          AND Status IN ('Active','Full')
          AND datetime(Date_of_departure || ' ' || Time_of_departure) >= datetime('now', 'localtime')
        ORDER BY Date_of_departure
        """,
        (origin, dest)
    )
    return {"dates": [r["d"].isoformat() if hasattr(r["d"],'isoformat') else str(r["d"]) for r in rows]}

@app.route("/flights/results")
def flights_results():
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    dep_date = request.args.get("dep_date","").strip()
    origin = request.args.get("origin","").strip().upper()
    dest = request.args.get("dest","").strip().upper()

    params=[]
    # Only show flights that can still be booked (not departed yet).
    where=[
        "F.Status IN ('Active','Full')",
        "datetime(F.Date_of_departure || ' ' || F.Time_of_departure) >= datetime('now', 'localtime')"
    ]
    if dep_date:
        where.append("F.Date_of_departure = %s")
        params.append(dep_date)
    if origin:
        where.append("F.Origin_airport = %s")
        params.append(origin)
    if dest:
        where.append("F.Arrival_airport = %s")
        params.append(dest)

    # Show Active/Full/Completed/Canceled for browsing, but only Active/Full can be purchased (we'll enforce later)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = query_all(f"""
        SELECT
            F.*,
            A.Manufacturer, A.Size,
            (SELECT MIN(Price) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.CLASS_Type='Regular') AS price_regular,
            (SELECT MIN(Price) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.CLASS_Type='First') AS price_first,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID) AS total_tickets,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.Availability=1) AS available_tickets
        FROM FLIGHT F
        JOIN AIRPLANE A ON A.ID = F.Airplane_ID
        {where_sql}
        ORDER BY F.Date_of_departure, F.Time_of_departure
    """, tuple(params))
    return render_template("flights_results.html", flights=rows, dep_date=dep_date, origin=origin, dest=dest)


@app.route("/flights/<flight_id>/book", methods=["GET","POST"])
def flight_book(flight_id):
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    f = query_one(
        """
        SELECT F.*, (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.Availability=1) AS available_tickets
        FROM FLIGHT F
        WHERE F.ID=%s
        """,
        (flight_id,)
    )
    if not f:
        flash("Flight not found.", "danger")
        return redirect(url_for("flights_search"))

    # Safety: do not allow booking a flight that has already departed (even if status wasn't refreshed yet).
    try:
        d = f.get("Date_of_departure")
        t = f.get("Time_of_departure")
        if isinstance(d, str):
            d = parse_date(d)
        if isinstance(t, str):
            t = parse_time(t)
        dep_dt = datetime.combine(d, t)
        if dep_dt <= datetime.now():
            flash("This flight has already departed.", "warning")
            return redirect(url_for("flights_search"))
    except Exception:
        pass

    if f.get("Status") not in ["Active", "Full"]:
        flash("This flight is not open for booking.", "warning")
        return redirect(url_for("flights_results", origin=f.get("Origin_airport"), dest=f.get("Arrival_airport"), dep_date=f.get("Date_of_departure")))

    if int(f.get("available_tickets") or 0) <= 0:
        flash("This flight is sold out.", "warning")
        return redirect(url_for("flights_results", origin=f.get("Origin_airport"), dest=f.get("Arrival_airport"), dep_date=f.get("Date_of_departure")))

    if request.method == "POST":
        avail = int(f.get("available_tickets") or 0)
        if avail <= 0:
            flash("No available seats on this flight.", "danger")
            return redirect(url_for("flights_search"))


        try:
            qty = int(request.form.get("qty", "1"))
        except ValueError:
            qty = 1
        qty = max(1, qty)
        if qty > avail:
            flash(f"Only {avail} seat(s) are available for this flight.", "warning")
            qty = avail

        # Store desired quantity in session per flight
        seat_qty = session.get("seat_qty", {})
        seat_qty[flight_id] = qty
        session["seat_qty"] = seat_qty
        return redirect(url_for("flight_seats", flight_id=flight_id))

    # prefill qty
    qty_pref = 1
    try:
        qty_pref = int(session.get("seat_qty", {}).get(flight_id, 1))
    except Exception:
        qty_pref = 1
    # cap prefilled qty by available seats
    try:
        qty_pref = min(qty_pref, int(f.get("available_tickets") or qty_pref))
    except Exception:
        pass
    return render_template("flight_book.html", flight=f, qty_pref=qty_pref)

@app.route("/flights/<flight_id>/seats", methods=["GET","POST"])
def flight_seats(flight_id):
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    f = query_one("""
        SELECT F.*, A.Size, A.Manufacturer
        FROM FLIGHT F JOIN AIRPLANE A ON A.ID=F.Airplane_ID
        WHERE F.ID=%s
    """, (flight_id,))
    if not f:
        flash("Flight not found.", "danger")
        return redirect(url_for("flights_search"))

    tickets = query_all("""
        SELECT Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type, Price, Availability
        FROM TICKET
        WHERE Flight_ID=%s
        ORDER BY CLASS_Type, SEAT_Row_num, SEAT_Column_number
    """, (flight_id,))

    # group by class -> rows -> cols
    seatmap={}
    for t in tickets:
        cls=t["CLASS_Type"]
        seatmap.setdefault(cls, {})
        seatmap[cls].setdefault(t["SEAT_Row_num"], [])
        seatmap[cls][t["SEAT_Row_num"]].append(t)

    qty_required = 1
    try:
        qty_required = int(session.get("seat_qty", {}).get(flight_id, 1))
    except Exception:
        qty_required = 1

    if request.method == "POST":
        selected = request.form.getlist("seat_key")
        selected = [s for s in selected if s]
        if not selected:
            flash("No seats selected.", "warning")
            return redirect(url_for("flight_seats", flight_id=flight_id))

        if len(selected) != qty_required:
            flash(f"You must select exactly {qty_required} seat(s).", "warning")
            return redirect(url_for("flight_seats", flight_id=flight_id))

        # Validate availability server-side
        for sk in selected:
            try:
                cls, r, c = sk.split("|")
                r = int(r)
            except Exception:
                flash("Invalid seat selection.", "danger")
                return redirect(url_for("flight_seats", flight_id=flight_id))
            row = query_one(
                """
                SELECT Availability
                FROM TICKET
                WHERE Flight_ID=%s AND CLASS_Type=%s AND SEAT_Row_num=%s AND SEAT_Column_number=%s
                """,
                (flight_id, cls, r, c)
            )
            # Check availability: must exist and be 1 (available), and not linked to active order
            if not row:
                flash("One or more selected seats are no longer available. Please choose again.", "danger")
                return redirect(url_for("flight_seats", flight_id=flight_id))
            
            # Convert to int for comparison (SQLite may return as string)
            availability = row.get("Availability")
            if availability is None or int(availability) != 1:
                flash("One or more selected seats are no longer available. Please choose again.", "danger")
                return redirect(url_for("flight_seats", flight_id=flight_id))
            
            # Also check if seat is linked to an active order
            active_order_check = query_one(
                """
                SELECT 1
                FROM TICKET_ORDER TO1
                JOIN `ORDER` O1 ON O1.ID = TO1.Order_ID
                WHERE TO1.Flight_ID=%s AND TO1.CLASS_Type=%s AND TO1.SEAT_Row_num=%s AND TO1.SEAT_Column_number=%s
                  AND O1.Status='Active'
                LIMIT 1
                """,
                (flight_id, cls, r, c)
            )
            if active_order_check:
                flash("One or more selected seats are no longer available. Please choose again.", "danger")
                return redirect(url_for("flight_seats", flight_id=flight_id))

        # store selection in session
        session["cart"] = {"flight_id": flight_id, "seats": selected, "qty": qty_required}
        return redirect(url_for("checkout"))

    return render_template("flight_seats.html", flight=f, seatmap=seatmap, qty_required=qty_required)

@app.route("/checkout", methods=["GET","POST"])
def checkout():
    # Managers must not access customer booking flow
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    cart = session.get("cart")
    if not cart:
        flash("No active seat selection.", "warning")
        return redirect(url_for("flights_search"))

    flight_id = cart["flight_id"]
    seat_keys = cart["seats"]  # each: cls|row|col

    parsed = []
    for k in seat_keys:
        try:
            cls, row, col = k.split("|")
            parsed.append((cls, int(row), col))
        except Exception:
            pass

    if not parsed:
        flash("Invalid seat selection.", "danger")
        return redirect(url_for("flights_search"))

    f = query_one("SELECT * FROM FLIGHT WHERE ID=%s", (flight_id,))
    if not f:
        flash("Flight not found.", "danger")
        return redirect(url_for("flights_search"))

    # fetch tickets and validate availability (server-side)
    # SQLite doesn't support tuple IN syntax well, so we use OR conditions instead
    if not parsed:
        flash("Invalid seat selection.", "danger")
        return redirect(url_for("flights_search"))
    
    or_conditions = []
    params = [flight_id]
    for cls, row, col in parsed:
        or_conditions.append("(CLASS_Type=? AND SEAT_Row_num=? AND SEAT_Column_number=?)")
        params.extend([cls, row, col])
    
    where_clause = " OR ".join(or_conditions)
    tickets = query_all(f"""
        SELECT CLASS_Type, SEAT_Row_num, SEAT_Column_number, Price, Availability
        FROM TICKET
        WHERE Flight_ID=? AND ({where_clause})
    """, tuple(params))

    if len(tickets) != len(parsed):
        flash("One or more selected seats are no longer available. Please choose again.", "danger")
        return redirect(url_for("flight_seats", flight_id=flight_id))
    
    # Check availability: convert to int for comparison
    for t in tickets:
        availability = t.get("Availability")
        if availability is None or int(availability) != 1:
            flash("One or more selected seats are no longer available. Please choose again.", "danger")
            return redirect(url_for("flight_seats", flight_id=flight_id))

    total = float(sum([t["Price"] for t in tickets]))

    # Member profile (for prefilling + optional updates on checkout)
    member_profile = None
    if is_logged_in("member"):
        member_email = session["user"]
        member_profile = query_one("""
            SELECT
              M.Email,
              M.First_name_in_English AS first,
              M.Last_name_in_English AS last,
              (SELECT Phone_number
               FROM PHONE_NUMBER_MEMBER P
               WHERE P.Email = M.Email
               ORDER BY Phone_number
               LIMIT 1) AS phone
            FROM MEMBER M
            WHERE M.Email=%s
        """, (member_email,)) or {"Email": member_email, "first": "", "last": "", "phone": ""}

    if request.method == "POST":
        buyer_type = "member" if is_logged_in("member") else "guest"

        if buyer_type == "member":
            member_email = session["user"]

            # Allow edits + persist them
            member_first = request.form.get("member_first", "").strip()
            member_last = request.form.get("member_last", "").strip()
            member_phone = request.form.get("member_phone", "").strip()

            if not (member_first and member_last and member_phone):
                flash("Please confirm your details (first name, last name, phone).", "warning")
                return redirect(url_for("checkout"))

            if not _is_valid_english_name(member_first):
                flash("Please enter a valid first name using English letters only.", "warning")
                return redirect(url_for("checkout"))
            if not _is_valid_english_name(member_last):
                flash("Please enter a valid last name using English letters only.", "warning")
                return redirect(url_for("checkout"))

            execute(
                "UPDATE MEMBER SET First_name_in_English=%s, Last_name_in_English=%s WHERE Email=%s",
                (member_first, member_last, member_email)
            )
            # Keep history of phones (do not delete older ones)
            execute("INSERT OR IGNORE INTO PHONE_NUMBER_MEMBER(Email, Phone_number) VALUES(%s,%s)", (member_email, member_phone))

            guest_email = None

        else:
            guest_email = request.form.get("guest_email", "").strip()
            guest_first = request.form.get("guest_first", "").strip()
            guest_last = request.form.get("guest_last", "").strip()
            guest_phone = request.form.get("guest_phone", "").strip()

            if not (guest_email and guest_first and guest_last and guest_phone):
                flash("Please enter guest details (email, first and last name in English, phone).", "warning")
                return redirect(url_for("checkout"))

            if not _is_valid_english_name(guest_first):
                flash("Please enter a valid first name using English letters only.", "warning")
                return redirect(url_for("checkout"))
            if not _is_valid_english_name(guest_last):
                flash("Please enter a valid last name using English letters only.", "warning")
                return redirect(url_for("checkout"))

            # If this email belongs to a registered member -> force login
            mrow = query_one("SELECT Email FROM MEMBER WHERE Email=%s", (guest_email,))
            if mrow:
                flash("This email belongs to a registered member. Please log in to continue.", "danger")
                session["next_url"] = url_for("checkout")
                session["force_login_member"] = True
                return redirect(url_for("login_member"))

            # Create / update guest profile
            grow = query_one("SELECT Email FROM GUEST WHERE Email=%s", (guest_email,))
            if not grow:
                execute(
                    "INSERT INTO GUEST(Email, First_name_in_English, Last_name_in_English) VALUES(%s,%s,%s)",
                    (guest_email, guest_first, guest_last)
                )
            else:
                execute(
                    "UPDATE GUEST SET First_name_in_English=%s, Last_name_in_English=%s WHERE Email=%s",
                    (guest_first, guest_last, guest_email)
                )

            # Keep history of phones (do not delete older ones)
            execute("INSERT OR IGNORE INTO PHONE_NUMBER_GUEST(Email, Phone_number) VALUES(%s,%s)", (guest_email, guest_phone))

            member_email = None

        # generate order id (schema has no auto increment)
        mx = query_one("SELECT IFNULL(MAX(ID),0) AS mx FROM `ORDER`")
        order_id = int(mx["mx"]) + 1

        # Cancellation fee is stored at order creation time (5% of the original total).
        # If the customer later cancels, Total_price becomes this value.
        cancellation_fee = round(float(total) * 0.05, 2)

        # Create order + ticket links in a single transaction.
        # All seat-availability constraints are enforced here in code (no triggers).
        conn = get_conn()
        try:
            cur = conn.cursor()

            # Create the order first (ID is generated in code).
            cur.execute(
                "INSERT INTO `ORDER`(ID, Status, Total_price, Date_of_purchase, Cancellation_fee, GUEST_Email, MEMBER_Email) "
                "VALUES(?, 'Active', ?, ?, ?, ?, ?)",
                (order_id, total, date.today().isoformat(), cancellation_fee, guest_email, member_email),
            )

            for cls, row, col in parsed:
                # Lock the ticket row to prevent double-booking in concurrent checkouts.
                cur.execute(
                    """SELECT Airplane_ID, Availability
                       FROM TICKET
                       WHERE Flight_ID=? AND CLASS_Type=? AND SEAT_Row_num=? AND SEAT_Column_number=?""",
                    (flight_id, cls, row, col),
                )
                trow = cur.fetchone()
                if not trow:
                    raise Exception('Seat not found')
                # Access Row object - use dictionary-style access, not .get()
                try:
                    availability = trow['Availability']
                    if availability is None or int(availability) != 1:
                        raise Exception('Seat not available')
                except (KeyError, ValueError, TypeError):
                    raise Exception('Seat not available')

                airplane_id = trow['Airplane_ID']

                # Sanity check: a ticket may not be linked to another ACTIVE order.
                cur.execute(
                    """SELECT 1
                       FROM TICKET_ORDER TO1
                       JOIN `ORDER` O1 ON O1.ID = TO1.Order_ID
                       WHERE TO1.Airplane_ID=? AND TO1.Flight_ID=?
                         AND TO1.SEAT_Row_num=? AND TO1.SEAT_Column_number=? AND TO1.CLASS_Type=?
                         AND O1.Status='Active'
                       LIMIT 1""",
                    (airplane_id, flight_id, row, col, cls),
                )
                if cur.fetchone():
                    raise Exception('Seat already linked to an active order')

                # Link ticket to order (history is kept forever).
                cur.execute(
                    """INSERT INTO TICKET_ORDER(Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type, Order_ID)
                       VALUES(?,?,?,?,?,?)""",
                    (airplane_id, flight_id, row, col, cls, order_id),
                )

                # Mark ticket as unavailable.
                cur.execute(
                    """UPDATE TICKET
                       SET Availability=0
                       WHERE Airplane_ID=? AND Flight_ID=? AND CLASS_Type=? AND SEAT_Row_num=? AND SEAT_Column_number=?""",
                    (airplane_id, flight_id, cls, row, col),
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            # Show actual error for debugging
            error_msg = str(e)
            flash(f'Failed to complete order: {error_msg}. Please try again.', 'danger')
            return redirect(url_for('flight_seats', flight_id=flight_id))
        finally:
            try:
                conn.close()
            except Exception:
                pass

        session.pop("cart", None)
        flash(f"Order completed! Order number: {order_id}", "success")

        # Guest must be redirected with email for verification
        if guest_email:
            return redirect(url_for("order_details", order_id=order_id, email=guest_email))
        return redirect(url_for("order_details", order_id=order_id))

    return render_template(
        "checkout.html",
        flight=f,
        tickets=tickets,
        total=total,
        buyer_role=session.get("role"),
        member_profile=member_profile
    )

@app.route("/orders/my")
def my_orders():
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    if not is_logged_in("member"):
        flash("This page is for registered members.", "warning")
        return redirect(url_for("login"))
    email = session["user"]
    status = request.args.get("status","").strip()

    params=[email]
    where="WHERE O.MEMBER_Email=%s"
    if status:
        where += " AND O.Status=%s"
        params.append(status)

    rows = query_all(f"""
        SELECT O.ID, O.Status, O.Total_price, O.Date_of_purchase,
               COUNT(TO1.Order_ID) AS tickets_count,
               MIN(F.Date_of_departure) AS dep_date,
               MIN(F.Time_of_departure) AS dep_time,
               MIN(F.Origin_airport) AS origin,
               MIN(F.Arrival_airport) AS dest
        FROM `ORDER` O
        LEFT JOIN TICKET_ORDER TO1 ON TO1.Order_ID=O.ID
        LEFT JOIN TICKET T ON T.Airplane_ID=TO1.Airplane_ID AND T.Flight_ID=TO1.Flight_ID AND T.SEAT_Row_num=TO1.SEAT_Row_num AND T.SEAT_Column_number=TO1.SEAT_Column_number AND T.CLASS_Type=TO1.CLASS_Type
        LEFT JOIN FLIGHT F ON F.ID=T.Flight_ID
        {where}
        GROUP BY O.ID, O.Status, O.Total_price, O.Date_of_purchase
        ORDER BY O.Date_of_purchase DESC, O.ID DESC
    """, tuple(params))
    return render_template("my_orders.html", orders=rows, status=status)

@app.route("/orders/guest", methods=["GET","POST"])
def guest_lookup():
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    if request.method == "POST":
        email=request.form.get("email","").strip()
        oid_raw=request.form.get("order_id","").strip()
        oid = _parse_positive_int(oid_raw)
        if oid is None:
            flash("Please enter a valid order number (digits only).", "warning")
            return redirect(url_for("guest_lookup"))
        return redirect(url_for("order_details", order_id=oid, email=email))
    return render_template("guest_lookup.html")

@app.route("/orders/<int:order_id>")
def order_details(order_id):
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    # guest can pass email as extra validation; member/manager can view without it
    email = request.args.get("email","").strip()
    o = query_one("SELECT * FROM `ORDER` WHERE ID=%s", (order_id,))
    if not o:
        flash("Order not found.", "danger")
        return redirect(url_for("index"))

    # Authorization:
    member_email = o.get("MEMBER_Email")
    guest_email = o.get("GUEST_Email")
    
    if is_logged_in("member"):
        # Member can only view their own orders
        if member_email is None or member_email != session["user"]:
            flash("You are not authorized to view this order.", "danger")
            return redirect(url_for("my_orders"))
    elif is_logged_in("manager"):
        # Managers are blocked from customer area (handled above)
        pass
    else:
        # guest - must provide email for validation
        if not email:
            flash("Please enter the email used for this order.", "warning")
            return redirect(url_for("guest_lookup"))

        # Validate guest email - handle NULL case
        if guest_email is None or guest_email != email:
            flash("Email does not match this order. Please enter the correct email.", "danger")
            return redirect(url_for("guest_lookup"))

        # If the order exists and the email is correct, provide a clear message when the order is inactive.
        if o.get("Status") != "Active":
            flash("This order is no longer active.", "warning")
            return redirect(url_for("guest_lookup"))

    tickets = query_all("""
        SELECT T.CLASS_Type, T.SEAT_Row_num, T.SEAT_Column_number, T.Price, T.Flight_ID,
               F.Date_of_departure, F.Time_of_departure, F.Origin_airport, F.Arrival_airport, F.Status AS flight_status
        FROM TICKET_ORDER TO1
        JOIN TICKET T ON T.Airplane_ID=TO1.Airplane_ID AND T.Flight_ID=TO1.Flight_ID AND T.SEAT_Row_num=TO1.SEAT_Row_num AND T.SEAT_Column_number=TO1.SEAT_Column_number AND T.CLASS_Type=TO1.CLASS_Type
        JOIN FLIGHT F ON F.ID=T.Flight_ID
        WHERE TO1.Order_ID=%s
        ORDER BY T.Flight_ID, T.CLASS_Type, T.SEAT_Row_num, T.SEAT_Column_number
    """, (order_id,))
    
    # Handle empty tickets list gracefully
    if not tickets:
        tickets = []

    # can cancel? only for active order, all tickets must belong to one flight (as per design), and >=36h
    can_cancel=False
    reason=None
    order_status = o.get("Status", "")
    if order_status=="Active" and tickets:
        try:
            dep_date = tickets[0].get("Date_of_departure")
            dep_time = tickets[0].get("Time_of_departure")
            # Parse date and time if they are strings
            if isinstance(dep_date, str):
                dep_date = parse_date(dep_date)
            if isinstance(dep_time, str):
                dep_time = parse_time(dep_time)
            hrs = hours_until(dep_date, dep_time)
            if hrs >= 36:
                can_cancel=True
            else:
                reason="Orders can't be cancelled less than 36 hours before departure."
        except Exception as e:
            # If we can't calculate hours, don't allow cancellation
            reason=f"Unable to calculate cancellation eligibility: {str(e)}"
    elif order_status!="Active":
        reason="Order is not active."

    return render_template("order_details.html", order=o, tickets=tickets, can_cancel=can_cancel, cancel_reason=reason, guest_email=email)

@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    if is_logged_in("manager"):
        flash("Managers cannot access the customer booking area.", "warning")
        return redirect(url_for("manager_dashboard"))

    o = query_one("SELECT * FROM `ORDER` WHERE ID=%s", (order_id,))
    if not o:
        flash("Order not found.", "danger")
        return redirect(url_for("index"))

    # auth: member owns it, or guest provides email
    guest_email = request.form.get("guest_email","").strip()
    member_email = o.get("MEMBER_Email")
    order_guest_email = o.get("GUEST_Email")
    
    if is_logged_in("member"):
        if member_email is None or member_email != session["user"]:
            flash("You are not allowed to cancel this order.", "danger")
            return redirect(url_for("my_orders"))
    elif is_logged_in("manager"):
        flash("Managers cancel orders by cancelling the flight.", "warning")
        return redirect(url_for("manager_dashboard"))
    else:
        if not guest_email or order_guest_email is None or order_guest_email != guest_email:
            flash("Guest verification failed.", "danger")
            return redirect(url_for("guest_lookup"))

    tickets = query_all("""SELECT T.Flight_ID, F.Date_of_departure, F.Time_of_departure
                             FROM TICKET_ORDER TO1
                             JOIN TICKET T ON T.Airplane_ID=TO1.Airplane_ID AND T.Flight_ID=TO1.Flight_ID AND T.SEAT_Row_num=TO1.SEAT_Row_num AND T.SEAT_Column_number=TO1.SEAT_Column_number AND T.CLASS_Type=TO1.CLASS_Type
                             JOIN FLIGHT F ON F.ID=T.Flight_ID
                             WHERE TO1.Order_ID=%s""", (order_id,))
    if not tickets:
        flash("No tickets were found for this order.", "danger")
        return redirect(url_for("order_details", order_id=order_id, email=guest_email))

    # Parse date and time before calling hours_until
    try:
        dep_date = tickets[0].get("Date_of_departure")
        dep_time = tickets[0].get("Time_of_departure")
        if isinstance(dep_date, str):
            dep_date = parse_date(dep_date)
        if isinstance(dep_time, str):
            dep_time = parse_time(dep_time)
        if hours_until(dep_date, dep_time) < 36:
            flash("Orders can't be cancelled less than 36 hours before departure.", "danger")
            return redirect(url_for("order_details", order_id=order_id, email=guest_email))
    except Exception as e:
        flash(f"Error calculating cancellation eligibility: {str(e)}. Please try again.", "danger")
        return redirect(url_for("order_details", order_id=order_id, email=guest_email))

    order_status = o.get("Status", "")
    if order_status != "Active":
        flash("This order is no longer active.", "warning")
        return redirect(url_for("order_details", order_id=order_id, email=guest_email))

    # Cancellation fee is stored at order creation time.
    # When the customer cancels, the order's Total_price becomes this stored fee.

    # Perform the cancellation and ticket release atomically (no triggers).
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Get the order row to verify status and get cancellation fee
        cur.execute("SELECT * FROM `ORDER` WHERE ID=?", (order_id,))
        o_locked = cur.fetchone()
        if not o_locked:
            raise Exception('Order not found')
        # Access Row object - sqlite3.Row supports dictionary-style access
        try:
            order_status = o_locked['Status']
        except (KeyError, TypeError):
            raise Exception('Order status not found')
        if order_status != 'Active':
            raise Exception('Order is no longer active')

        # Use the stored cancellation fee (5% of the original total at creation time).
        try:
            cancellation_fee = o_locked['Cancellation_fee']
            fee = float(cancellation_fee or 0)
        except (KeyError, ValueError, TypeError):
            fee = 0.0
        # Fallback (should not happen): if fee is missing/zero but total is positive, compute 5%.
        if fee <= 0:
            try:
                total_price = o_locked['Total_price']
                fee = round(float(total_price or 0) * 0.05, 2)
            except (KeyError, ValueError, TypeError):
                fee = 0.0

        # Update order status and final price. (Do NOT change Cancellation_fee here.)
        cur.execute(
            "UPDATE `ORDER` SET Status='Customer Cancellation', Total_price=? WHERE ID=?",
            (fee, order_id),
        )

        # Get all tickets in this order.
        cur.execute(
            """SELECT Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type
               FROM TICKET_ORDER
               WHERE Order_ID=?""",
            (order_id,),
        )
        keys = cur.fetchall() or []

        # Release tickets: a ticket becomes available if it has NO ACTIVE link.
        for k in keys:
            # Access Row object fields - Row objects support dictionary access
            airplane_id = k['Airplane_ID']
            flight_id = k['Flight_ID']
            seat_row = k['SEAT_Row_num']
            seat_col = k['SEAT_Column_number']
            class_type = k['CLASS_Type']
            
            cur.execute(
                """SELECT Availability
                   FROM TICKET
                   WHERE Airplane_ID=? AND Flight_ID=? AND SEAT_Row_num=? AND SEAT_Column_number=? AND CLASS_Type=?""",
                (airplane_id, flight_id, seat_row, seat_col, class_type),
            )
            _ = cur.fetchone()

            cur.execute(
                """SELECT 1
                   FROM TICKET_ORDER TO2
                   JOIN `ORDER` O2 ON O2.ID = TO2.Order_ID
                   WHERE TO2.Airplane_ID=? AND TO2.Flight_ID=? AND TO2.SEAT_Row_num=? AND TO2.SEAT_Column_number=? AND TO2.CLASS_Type=?
                     AND O2.Status='Active'
                   LIMIT 1""",
                (airplane_id, flight_id, seat_row, seat_col, class_type),
            )
            has_active = cur.fetchone() is not None

            cur.execute(
                """UPDATE TICKET
                   SET Availability=?
                   WHERE Airplane_ID=? AND Flight_ID=? AND SEAT_Row_num=? AND SEAT_Column_number=? AND CLASS_Type=?""",
                (0 if has_active else 1, airplane_id, flight_id, seat_row, seat_col, class_type),
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        # Show actual error for debugging - this will help identify the real issue
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        # In production, log traceback instead of showing to user
        flash(f'Failed to cancel order: {error_msg}. Please try again or contact support.', 'danger')
        return redirect(url_for('order_details', order_id=order_id, email=guest_email))
    finally:
        try:
            conn.close()
        except Exception:
            pass

    flash("Order cancelled.", "success")
    return redirect(url_for("order_details", order_id=order_id, email=guest_email))

# ---------- MANAGER ----------
@app.route("/manager")
def manager_dashboard():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    stats = query_one("""
        SELECT
          (SELECT COUNT(*) FROM FLIGHT) AS flights,
          (SELECT COUNT(*) FROM `ORDER`) AS orders,
          (SELECT COUNT(*) FROM AIRCREW) AS aircrew,
          (SELECT COUNT(*) FROM AIRPLANE) AS airplanes
    """)
    _load_report_sql()
    avg_row = query_one(_REPORT_SQL_CACHE.get(1, "SELECT NULL AS avg_occupancy_percentage"))
    stats["avg_occ_pct"] = avg_row.get("average_occupancy_percentage") if avg_row else None
    return render_template("manager_dashboard.html", stats=stats)



@app.route("/manager/orders")
def manager_orders():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))

    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    params = []
    where = "WHERE 1=1"
    if status:
        where += " AND O.Status=%s"
        params.append(status)
    if q:
        where += " AND (CAST(O.ID AS CHAR) LIKE %s OR O.MEMBER_Email LIKE %s OR O.GUEST_Email LIKE %s)"
        like = f"%{q}%"
        params += [like, like, like]

    orders = query_all(
        f"""
        SELECT
          O.ID,
          O.Status,
          O.Total_price,
          O.Date_of_purchase,
          O.MEMBER_Email,
          O.GUEST_Email,
          COUNT(TO1.Order_ID) AS tickets_count,
          MIN(T.Flight_ID) AS flight_id,
          MIN(F.Date_of_departure) AS dep_date,
          MIN(F.Time_of_departure) AS dep_time,
          MIN(F.Origin_airport) AS origin,
          MIN(F.Arrival_airport) AS dest
        FROM `ORDER` O
        LEFT JOIN TICKET_ORDER TO1 ON TO1.Order_ID=O.ID
        LEFT JOIN TICKET T ON T.Airplane_ID=TO1.Airplane_ID AND T.Flight_ID=TO1.Flight_ID AND T.SEAT_Row_num=TO1.SEAT_Row_num AND T.SEAT_Column_number=TO1.SEAT_Column_number AND T.CLASS_Type=TO1.CLASS_Type
        LEFT JOIN FLIGHT F ON F.ID=T.Flight_ID
        {where}
        GROUP BY O.ID, O.Status, O.Total_price, O.Date_of_purchase, O.MEMBER_Email, O.GUEST_Email
        ORDER BY O.Date_of_purchase DESC, O.ID DESC
        """,
        tuple(params),
    )
    return render_template("manager_orders.html", orders=orders, status=status, q=q)


@app.route("/manager/aircraft")
def manager_aircraft():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))

    aircraft = query_all(
        """
        SELECT
          A.ID,
          A.Manufacturer,
          A.Size,
          SUM(CASE WHEN S.Class_Type='Regular' THEN 1 ELSE 0 END) AS reg_seats,
          SUM(CASE WHEN S.Class_Type<>'Regular' THEN 1 ELSE 0 END) AS first_seats,
          COUNT(*) AS total_seats
        FROM AIRPLANE A
        LEFT JOIN SEAT S ON S.Airplane_ID=A.ID
        GROUP BY A.ID, A.Manufacturer, A.Size
        ORDER BY A.Size DESC, A.Manufacturer, A.ID
        """
    )
    return render_template("manager_aircraft.html", aircraft=aircraft)


@app.route("/manager/aircraft/add", methods=["GET", "POST"])
def manager_aircraft_add():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))

    if request.method == "POST":
        airplane_id = request.form.get("airplane_id", "").strip()
        purchase_date = request.form.get("purchase_date", "").strip()
        manufacturer = request.form.get("manufacturer", "").strip()
        size = request.form.get("size", "").strip()

        reg_rows = request.form.get("reg_rows", "").strip()
        reg_cols = request.form.get("reg_cols", "").strip()
        first_rows = request.form.get("first_rows", "").strip()
        first_cols = request.form.get("first_cols", "").strip()

        # Basic validation
        if not (airplane_id and purchase_date and manufacturer and size and reg_rows and reg_cols):
            flash("Please fill in all required fields.", "warning")
            return redirect(url_for("manager_aircraft_add"))
        # Purchase date must not be in the future
        try:
            pd = date.fromisoformat(purchase_date)
        except Exception:
            flash("Invalid purchase date format.", "warning")
            return redirect(url_for("manager_aircraft_add"))
        if pd > date.today():
            flash("Purchase date cannot be in the future.", "warning")
            return redirect(url_for("manager_aircraft_add"))



        # ---- parse numeric fields with field-specific messages ----
        try:
            aid = int(airplane_id)
        except ValueError:
            flash("Aircraft ID must be a whole number.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        try:
            reg_rows_i = int(reg_rows)
        except ValueError:
            flash("Regular class rows must be a whole number.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        try:
            reg_cols_i = int(reg_cols)
        except ValueError:
            flash("Regular class columns must be a whole number.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        if first_rows:
            try:
                first_rows_i = int(first_rows)
            except ValueError:
                flash("Business class rows must be a whole number.", "warning")
                return redirect(url_for("manager_aircraft_add"))
        else:
            first_rows_i = 0

        if first_cols:
            try:
                first_cols_i = int(first_cols)
            except ValueError:
                flash("Business class columns must be a whole number.", "warning")
                return redirect(url_for("manager_aircraft_add"))
        else:
            first_cols_i = 0
        if reg_cols_i > 26 or (first_cols_i and first_cols_i > 26):
            flash("Columns must be between 1 and 26 (A–Z). Please check Regular/Business columns.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        if aid <= 0 or reg_rows_i <= 0 or reg_cols_i <= 0:
            flash("Aircraft ID, Regular rows, and Regular columns must be positive numbers.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        if size == "Small":
            first_rows_i, first_cols_i = 0, 0
        else:
            # Big aircraft requires business/first config
            if first_rows_i <= 0 or first_cols_i <= 0:
                flash("For Big aircraft, please fill Business class rows and columns.", "warning")
                return redirect(url_for("manager_aircraft_add"))

        def _cols(n: int):
            return [chr(ord('A') + i) for i in range(n)]

        # Build seat rows for batch insert
        seat_rows = []
        for r in range(1, reg_rows_i + 1):
            for c in _cols(reg_cols_i):
                seat_rows.append(("Regular", aid, r, c))
        if size == "Big":
            for r in range(1, first_rows_i + 1):
                for c in _cols(first_cols_i):
                    seat_rows.append(("First", aid, r, c))


        # Enforce unique Aircraft ID
        if query_one("SELECT 1 AS x FROM AIRPLANE WHERE ID=%s", (aid,)):
            flash("Aircraft ID already exists. Please choose a different ID.", "warning")
            return redirect(url_for("manager_aircraft_add"))

        # Insert airplane + classes + seats in a single transaction
        conn = get_conn()
        try:
            cur = conn.cursor()

            cur.execute(
                """INSERT INTO AIRPLANE(ID, Date_of_purchase, Manufacturer, Size)
                   VALUES(?,?,?,?)""",
                (aid, purchase_date, manufacturer, size),
            )

            # Regular class
            cur.execute(
                """INSERT INTO CLASS(Type, Airplane_ID, Number_of_rows, Number_of_columns)
                   VALUES('Regular',?,?,?)""",
                (aid, reg_rows_i, reg_cols_i),
            )

            # Business class (stored as First)
            if size == "Big":
                cur.execute(
                    """INSERT INTO CLASS(Type, Airplane_ID, Number_of_rows, Number_of_columns)
                       VALUES('First',?,?,?)""",
                    (aid, first_rows_i, first_cols_i),
                )

            cur.executemany(
                """INSERT INTO SEAT(Class_Type, Airplane_ID, Row_num, Column_number)
                   VALUES(?,?,?,?)""",
                seat_rows,
            )

            conn.commit()
            flash("Aircraft added and seats generated.", "success")
            return redirect(url_for("manager_aircraft"))
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            # Provide a helpful message without leaking stack traces
            msg = str(e)
            if "Duplicate" in msg or "duplicate" in msg:
                flash("Aircraft ID already exists.", "danger")
            else:
                flash(f"Failed to add aircraft: {msg}", "danger")
            return redirect(url_for("manager_aircraft_add"))
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return render_template("manager_aircraft_add.html", today=date.today().isoformat())

@app.route("/manager/flights")
def manager_flights():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    status = request.args.get("status","").strip()
    params=[]
    where=""
    if status:
        where="WHERE F.Status=%s"
        params.append(status)

    rows=query_all(f"""
        SELECT
            F.ID,
            F.Date_of_departure,
            F.Time_of_departure,
            F.Status,
            F.Arrival_date,
            F.Arrival_time,
            F.Type,
            F.Airplane_ID,
            F.Origin_airport,
            F.Arrival_airport,
            A.Size,
            A.Manufacturer,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID) AS total_tickets,
            (SELECT COUNT(*) FROM TICKET T WHERE T.Flight_ID=F.ID AND T.Availability=1) AS available_tickets,
            GROUP_CONCAT(CASE WHEN AC.Type='Pilot'
                THEN AC.First_name || ' ' || AC.Last_name || ' (#' || AC.ID || ')' END, ', ') AS pilots,
            GROUP_CONCAT(CASE WHEN AC.Type='Flight attendant'
                THEN AC.First_name || ' ' || AC.Last_name || ' (#' || AC.ID || ')' END, ', ') AS attendants
        FROM FLIGHT F
        JOIN AIRPLANE A ON A.ID=F.Airplane_ID
        LEFT JOIN AIRCREW_ASSIGNMENT AA ON AA.Flight_ID=F.ID
        LEFT JOIN AIRCREW AC ON AC.ID=AA.Aircrew_ID
        {where}
        GROUP BY
            F.ID, F.Date_of_departure, F.Time_of_departure, F.Status, F.Arrival_date, F.Arrival_time, F.Type,
            F.Airplane_ID, F.Origin_airport, F.Arrival_airport, A.Size, A.Manufacturer
        ORDER BY F.Date_of_departure DESC, F.Time_of_departure DESC
    """, tuple(params))
    return render_template("manager_flights.html", flights=rows, status=status)

@app.route("/manager/flights/add", methods=["GET","POST"])
def manager_add_flight_step1():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    # Route list (Flight_duration is stored in minutes)
    routes_raw = query_all(
        "SELECT Origin_airport, Arrival_airport, Flight_duration "
        "FROM FLIGHT_ROUTE "
        "ORDER BY Origin_airport, Arrival_airport"
    )
    routes = []
    for r in routes_raw:
        dur = int(r["Flight_duration"])
        # Long if strictly more than 6 hours, Short if up to (and including) 6 hours
        ftype = "Long" if dur > 360 else "Short"  # minutes
        routes.append({
            "Origin_airport": r["Origin_airport"],
            "Arrival_airport": r["Arrival_airport"],
            "Flight_duration": dur,
            "Type": ftype,
        })
    if request.method=="POST":
        dep_date = request.form.get("dep_date","").strip()
        dep_time = request.form.get("dep_time","").strip()
        route_val = request.form.get("route","").strip()

        if not (dep_date and dep_time and route_val):
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("manager_add_flight_step1"))

        # Departure date must be a future date (strictly after today)
        try:
            dep_d = parse_date(dep_date)
            if dep_d <= date.today():
                flash("Departure date must be a future date.", "danger")
                return redirect(url_for("manager_add_flight_step1"))
        except Exception:
            flash("Invalid departure date.", "danger")
            return redirect(url_for("manager_add_flight_step1"))

        # parse selected route
        try:
            origin, dest = route_val.split("|")
            origin = origin.strip().upper()
            dest = dest.strip().upper()
        except Exception:
            flash("Invalid route selection.", "danger")
            return redirect(url_for("manager_add_flight_step1"))

        # validate route exists
        r = query_one(
            "SELECT Flight_duration FROM FLIGHT_ROUTE WHERE Origin_airport=%s AND Arrival_airport=%s",
            (origin, dest)
        )
        if not r:
            flash("The route does not exist in FLIGHT_ROUTE.", "danger")
            return redirect(url_for("manager_add_flight_step1"))

        duration_min = int(r["Flight_duration"])
        ftype = "Long" if duration_min > 360 else "Short"  # minutes

        # compute arrival
        arr_d, arr_t = add_minutes_to_dt(parse_date(dep_date), parse_time(dep_time), duration_min)

        session["new_flight"] = dict(
            dep_date=dep_date,
            dep_time=dep_time,
            origin=origin,
            dest=dest,
            duration_min=duration_min,
            ftype=ftype,
            arr_date=arr_d.isoformat(),
            arr_time=arr_t.strftime("%H:%M:%S"),
        )
        return redirect(url_for("manager_add_flight_step2"))
    return render_template(
        "manager_add_flight_step1.html",
        routes=routes,
        AIRPORT_LABELS=AIRPORT_LABELS,
    )

@app.route("/manager/flights/add/step2", methods=["GET","POST"])
def manager_add_flight_step2():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    nf = session.get("new_flight")
    if not nf:
        return redirect(url_for("manager_add_flight_step1"))

    # Determine airplane constraints
    # Long flights: must be Big airplane (per requirements).
    size_needed = "Big" if nf["ftype"]=="Long" else None

    # candidate airplanes not assigned at same departure date/time
    params=[]
    where="WHERE 1=1"
    if size_needed:
        where += " AND A.Size=%s"
        params.append(size_needed)
    where += """ AND A.ID NOT IN (
        SELECT Airplane_ID FROM FLIGHT
        WHERE Date_of_departure=%s AND Time_of_departure=%s
    )"""
    params += [nf["dep_date"], nf["dep_time"]]

    airplanes = query_all(f"""SELECT A.* FROM AIRPLANE A {where} ORDER BY A.Size DESC, A.Manufacturer, A.ID""", tuple(params))

    # Crew candidates (exclude those already assigned at same date/time)
    busy_ids = query_all("""
        SELECT DISTINCT AA.Aircrew_ID
        FROM AIRCREW_ASSIGNMENT AA
        JOIN FLIGHT F ON F.ID=AA.Flight_ID
        WHERE F.Date_of_departure=%s AND F.Time_of_departure=%s
    """, (nf["dep_date"], nf["dep_time"]))
    busy_set = set([x["Aircrew_ID"] for x in busy_ids])

    # Get boarding airport for the new flight
    boarding_airport = nf["origin"]
    dep_datetime_str = f"{nf['dep_date']} {nf['dep_time']}"

    # Find crew members who are at the boarding airport (their last completed flight landed there)
    # Also include new staff members who have never been on any flight
    available_at_airport = query_all("""
        SELECT DISTINCT AA.Aircrew_ID
        FROM AIRCREW_ASSIGNMENT AA
        JOIN FLIGHT F ON F.ID = AA.Flight_ID
        WHERE F.Status = 'Completed'
          AND F.Arrival_airport = %s
          AND (F.Arrival_date || ' ' || F.Arrival_time) = (
            SELECT MAX(F2.Arrival_date || ' ' || F2.Arrival_time)
            FROM AIRCREW_ASSIGNMENT AA2
            JOIN FLIGHT F2 ON F2.ID = AA2.Flight_ID
            WHERE F2.Status = 'Completed'
              AND AA2.Aircrew_ID = AA.Aircrew_ID
          )
    """, (boarding_airport,))
    available_at_airport_set = set([x["Aircrew_ID"] for x in available_at_airport])

    # Find new staff members who have never been on any flight (they can be selected from any airport)
    all_crew_with_flights = query_all("SELECT DISTINCT Aircrew_ID FROM AIRCREW_ASSIGNMENT")
    all_crew_with_flights_set = set([x["Aircrew_ID"] for x in all_crew_with_flights])
    all_crew = query_all("SELECT ID FROM AIRCREW")
    all_crew_set = set([x["ID"] for x in all_crew])
    new_staff_set = all_crew_set - all_crew_with_flights_set

    # Combine: staff at airport OR new staff (no flights yet)
    available_staff_set = available_at_airport_set | new_staff_set

    # Long flights require long-haul certification (Training=TRUE) for ALL assigned crew.
    if nf["ftype"] == "Long":
        pilots = query_all("SELECT * FROM AIRCREW WHERE Type='Pilot' AND Training=1 ORDER BY ID")
        attendants = query_all("SELECT * FROM AIRCREW WHERE Type='Flight attendant' AND Training=1 ORDER BY ID")
    else:
        pilots = query_all("SELECT * FROM AIRCREW WHERE Type='Pilot' ORDER BY Training DESC, ID")
        attendants = query_all("SELECT * FROM AIRCREW WHERE Type='Flight attendant' ORDER BY Training DESC, ID")

    # filter busy and filter by airport location (or new staff)
    pilots=[p for p in pilots if p["ID"] not in busy_set and p["ID"] in available_staff_set]
    attendants=[a for a in attendants if a["ID"] not in busy_set and a["ID"] in available_staff_set]

    # Keep only airplanes that are feasible with the currently-available crew pool.
    def req_counts_for_size(size: str):
        return (3, 6) if size == "Big" else (2, 3)

    feasible_airplanes = []
    for ap in airplanes:
        rp, ra = req_counts_for_size(ap["Size"])
        if len(pilots) >= rp and len(attendants) >= ra:
            feasible_airplanes.append(ap)

    if not feasible_airplanes:
        # No combination possible at the chosen date/time.
        if not airplanes:
            flash("No suitable aircraft is available at the selected departure date/time.", "danger")
        else:
            # Check if there are future flights that will bring staff to the boarding airport
            # Find the earliest arrival time at the boarding airport from future flights
            future_arrivals = query_all("""
                SELECT F.Arrival_date, F.Arrival_time, COUNT(DISTINCT AA.Aircrew_ID) as crew_count
                FROM FLIGHT F
                JOIN AIRCREW_ASSIGNMENT AA ON AA.Flight_ID = F.ID
                WHERE F.Arrival_airport = %s
                  AND F.Status IN ('Active', 'Full')
                  AND datetime(F.Arrival_date || ' ' || F.Arrival_time) > datetime(%s)
                GROUP BY F.Arrival_date, F.Arrival_time
                ORDER BY F.Arrival_date, F.Arrival_time
                LIMIT 1
            """, (boarding_airport, dep_datetime_str))
            
            if future_arrivals and len(future_arrivals) > 0:
                earliest = future_arrivals[0]
                suggested_date = earliest["Arrival_date"]
                suggested_time = earliest["Arrival_time"]
                crew_count = earliest["crew_count"]
                flash(f"No available crew members at {boarding_airport} for the selected departure time. "
                      f"The earliest time when staff will be available at this airport is {suggested_date} at {suggested_time} "
                      f"(after a flight arrives with {crew_count} crew member(s)). Please consider scheduling the flight after this time.", 
                      "warning")
            else:
                flash("Not enough available crew members at the selected departure date/time. "
                      f"No future flights are scheduled to arrive at {boarding_airport} with crew members.", 
                      "danger")
        return redirect(url_for("manager_add_flight_step1"))

    airplanes = feasible_airplanes

    # Recommended auto-selection (can be overridden)
    recommended_plane_id = airplanes[0]["ID"] if airplanes else None
    rp, ra = req_counts_for_size(airplanes[0]["Size"]) if airplanes else (2, 3)
    recommended_pilot_ids = [str(p["ID"]) for p in pilots[:rp]]
    recommended_att_ids = [str(a["ID"]) for a in attendants[:ra]]

    if request.method=="POST":
        airplane_id = request.form.get("airplane_id","").strip()
        price_regular = request.form.get("price_regular","").strip()
        price_first = request.form.get("price_first","").strip()

        selected_pilots = request.form.getlist("pilot_ids")
        selected_att = request.form.getlist("att_ids")

        if not airplane_id or not price_regular:
            flash("Please select an aircraft and enter a Regular class price.", "warning")
            return redirect(url_for("manager_add_flight_step2"))

        # fetch airplane
        ap = query_one("SELECT * FROM AIRPLANE WHERE ID=%s", (airplane_id,))
        if not ap:
            flash("Aircraft not found.", "danger")
            return redirect(url_for("manager_add_flight_step2"))

        # If a big aircraft is selected, a Business/First price is required
        if ap["Size"] == "Big" and not price_first:
            flash("For a big aircraft, you must enter a Business (First) class price.", "warning")
            return redirect(url_for("manager_add_flight_step2"))

        # Enforce flight-type constraints
        if nf["ftype"] == "Long" and ap["Size"] != "Big":
            flash("Long-haul flights must use a big aircraft.", "danger")
            return redirect(url_for("manager_add_flight_step2"))

        # crew required by airplane size
        if ap["Size"]=="Big":
            req_pilots, req_att = 3, 6
        else:
            req_pilots, req_att = 2, 3

        if len(selected_pilots)!=req_pilots or len(selected_att)!=req_att:
            flash(f"You must select {req_pilots} pilots and {req_att} attendants based on aircraft size.", "danger")
            return redirect(url_for("manager_add_flight_step2"))

        # training required for Long flight
        if nf["ftype"]=="Long":
            # all selected must have Training=TRUE
            ids = [int(x) for x in selected_pilots+selected_att]
            rows = query_all("SELECT ID, Training FROM AIRCREW WHERE ID IN (" + ",".join(["%s"]*len(ids)) + ")", tuple(ids))
            training_ok = all(r["Training"] for r in rows)
            if not training_ok:
                flash("For long-haul flights, all selected crew must be long-haul certified (Training=TRUE).", "danger")
                return redirect(url_for("manager_add_flight_step2"))

        # Generate a unique Flight ID automatically (no user input)
        mx = query_one(
            "SELECT MAX(CAST(SUBSTR(ID,2) AS INTEGER)) AS mx FROM FLIGHT WHERE ID LIKE 'F%'")
        n = int((mx or {}).get("mx") or 0) + 1
        flight_id = f"F{n:05d}"
        # extremely defensive: ensure uniqueness
        while query_one("SELECT 1 AS x FROM FLIGHT WHERE ID=%s", (flight_id,)):
            n += 1
            flight_id = f"F{n:05d}"

        # insert flight
        execute("""INSERT INTO FLIGHT(ID, Date_of_departure, Time_of_departure, Status, Arrival_date, Arrival_time, Type, Airplane_ID, Origin_airport, Arrival_airport)
                  VALUES(%s,%s,%s,'Active',%s,%s,%s,%s,%s,%s)""",
                (flight_id, nf["dep_date"], nf["dep_time"], nf["arr_date"], nf["arr_time"], nf["ftype"], airplane_id, nf["origin"], nf["dest"]))

        # assign crew
        for cid in selected_pilots + selected_att:
            execute("INSERT INTO AIRCREW_ASSIGNMENT(Aircrew_ID, Flight_ID) VALUES(%s,%s)", (cid, flight_id))

        # create tickets for all seats in airplane
        seats = query_all("SELECT * FROM SEAT WHERE Airplane_ID=%s ORDER BY Class_Type, Row_num, Column_number", (airplane_id,))
        if not seats:
            flash("No seats are defined for this aircraft (SEAT). Please check the seed data.", "danger")
            return redirect(url_for("manager_add_flight_step1"))

        reg=float(price_regular)
        first=float(price_first) if price_first else None

        ticket_rows=[]
        for s in seats:
            cls=s["Class_Type"]
            price = reg if cls=="Regular" else (first if first is not None else reg)
            ticket_rows.append((airplane_id, flight_id, s["Row_num"], s["Column_number"], cls, price))

        executemany("""INSERT INTO TICKET(Airplane_ID, Flight_ID, SEAT_Row_num, SEAT_Column_number, CLASS_Type, Price, Availability)
                      VALUES(%s,%s,%s,%s,%s,%s,1)""", ticket_rows)

        session.pop("new_flight", None)
        flash(f"Flight created successfully. Flight ID: {flight_id}", "success")
        return redirect(url_for("manager_flights"))

    return render_template(
        "manager_add_flight_step2.html",
        nf=nf,
        airplanes=airplanes,
        pilots=pilots,
        attendants=attendants,
        recommended_plane_id=recommended_plane_id,
        recommended_pilot_ids=recommended_pilot_ids,
        recommended_att_ids=recommended_att_ids,
    )

@app.route("/manager/flights/<flight_id>/cancel", methods=["POST"])
def manager_cancel_flight(flight_id):
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    f = query_one("SELECT * FROM FLIGHT WHERE ID=%s", (flight_id,))
    if not f:
        flash("Flight not found.", "danger")
        return redirect(url_for("manager_flights"))

    # Parse date and time (handle string or date/time objects)
    try:
        dep_date = f.get("Date_of_departure")
        dep_time = f.get("Time_of_departure")
        if isinstance(dep_date, str):
            dep_date = parse_date(dep_date)
        if isinstance(dep_time, str):
            dep_time = parse_time(dep_time)
        hrs = hours_until(dep_date, dep_time)
    except Exception as e:
        flash(f"Error calculating flight time: {str(e)}. Please try again.", "danger")
        return redirect(url_for("manager_flights"))
    
    if hrs < 72:
        flash("Flights can't be cancelled less than 72 hours before departure.", "danger")
        return redirect(url_for("manager_flights"))

    # set flight canceled + update related orders atomically (no triggers)
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Get flight status
        cur.execute("SELECT Status FROM FLIGHT WHERE ID=?", (flight_id,))
        f_locked = cur.fetchone()
        if not f_locked:
            raise Exception('Flight not found')

        cur.execute("UPDATE FLIGHT SET Status='Canceled' WHERE ID=?", (flight_id,))

        # Find active orders on this flight and lock them
        cur.execute(
            """SELECT DISTINCT O.ID
               FROM `ORDER` O
               JOIN TICKET_ORDER to1 ON to1.Order_ID=O.ID
               WHERE to1.Flight_ID=? AND O.Status='Active'""",
            (flight_id,),
        )
        orders = cur.fetchall() or []
        for orec in orders:
            cur.execute(
                "UPDATE `ORDER` SET Status='System Cancellation', Total_price=0, Cancellation_fee=0 WHERE ID=?",
                (orec['ID'],),
            )

        # Keep ticket-to-order linkage for history/audit purposes.
        # Since the flight is cancelled, tickets should not become re-sellable.
        cur.execute("UPDATE TICKET SET Availability=0 WHERE Flight_ID=?", (flight_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        # Log the actual error for debugging (in production, use proper logging)
        error_msg = str(e)
        flash(f'Failed to cancel flight: {error_msg}. Please try again.', 'danger')
        return redirect(url_for('manager_flights'))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    flash("The flight was cancelled. Active orders were refunded.", "success")
    return redirect(url_for("manager_flights"))

@app.route("/manager/aircrew")
def manager_aircrew():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))

    rows = query_all("SELECT * FROM AIRCREW ORDER BY Type, Training DESC, ID")
    return render_template("manager_aircrew.html", aircrew=rows)


@app.route("/manager/aircrew/add", methods=["GET","POST"])
def manager_aircrew_add():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    if request.method=="POST":
        cid = request.form.get("id","").strip()
        first = request.form.get("first","").strip()
        last = request.form.get("last","").strip()
        phone = request.form.get("phone","").strip()
        city = request.form.get("city","").strip()
        street = request.form.get("street","").strip()
        house = request.form.get("house","").strip()
        start = request.form.get("start","").strip()
        typ = request.form.get("typ","").strip()
        training = 1 if request.form.get("training")=="1" else 0
        if not (cid and first and last and phone and city and street and house and start and typ):
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("manager_aircrew_add"))

        # Field-specific validation
        try:
            cid_i = int(cid)
        except ValueError:
            flash("Crew ID must be a whole number.", "warning")
            return redirect(url_for("manager_aircrew_add"))
        if cid_i <= 0:
            flash("Crew ID must be a positive number.", "warning")
            return redirect(url_for("manager_aircrew_add"))

        # Names must be provided in English letters.
        if not _is_valid_english_name(first):
            flash("Please enter a valid first name using English letters only.", "warning")
            return redirect(url_for("manager_aircrew_add"))
        if not _is_valid_english_name(last):
            flash("Please enter a valid last name using English letters only.", "warning")
            return redirect(url_for("manager_aircrew_add"))

        try:
            house_i = int(house)
        except ValueError:
            flash("House number must be a whole number.", "warning")
            return redirect(url_for("manager_aircrew_add"))
        if house_i <= 0:
            flash("House number must be a positive number.", "warning")
            return redirect(url_for("manager_aircrew_add"))

        # Enforce unique Crew ID
        if query_one("SELECT 1 AS x FROM AIRCREW WHERE ID=%s", (cid_i,)):
            flash("Crew ID already exists. Please choose a different ID.", "warning")
            return redirect(url_for("manager_aircrew_add"))

        try:
            execute("""INSERT INTO AIRCREW(ID, City, Street, House_Number, Start_date_of_employment, First_name, Last_name, Phone_number, Type, Training)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (cid_i, city, street, house_i, start, first, last, phone, typ, training))
            flash("Crew member added.", "success")
            return redirect(url_for("manager_aircrew"))
        except Exception as e:
            msg = str(e)
            if "Duplicate entry" in msg or "1062" in msg:
                flash("Crew ID already exists. Please choose a different ID.", "warning")
            else:
                flash("Failed to add crew member. Please check your input.", "danger")
            return redirect(url_for("manager_aircrew_add"))
    return render_template("manager_aircrew_add.html")

# ---------- REPORTS ----------
def _prepare_revenue_chart_data(table_rows):
    """Prepare chart data for JavaScript rendering (Report 2 - Revenue)."""
    if not table_rows:
        return None
    
    try:
        # Group data by Plane_Type and CLASS_Type
        plane_types = {}
        class_types = set()
        
        for row in table_rows:
            # Access sqlite3.Row with dictionary-style access
            manufacturer = str(row['Manufacturer']).strip()
            size = str(row['Size']).strip()
            class_type = str(row['CLASS_Type']).strip()
            total_income = float(row['Total_Income'] or 0)
            
            plane_key = f"{manufacturer} ({size})"
            class_types.add(class_type)
            
            if plane_key not in plane_types:
                plane_types[plane_key] = {}
            plane_types[plane_key][class_type] = total_income
        
        # Sort plane types
        sorted_planes = sorted(plane_types.keys())
        sorted_classes = sorted(class_types)
        
        # Prepare datasets for each class type
        datasets = []
        colors = {
            'Regular': 'rgba(75, 192, 192, 1)',
            'First': 'rgba(255, 99, 132, 1)',
            'Business': 'rgba(54, 162, 235, 1)'
        }
        color_default = 'rgba(153, 102, 255, 1)'
        
        for class_type in sorted_classes:
            data = []
            for plane in sorted_planes:
                data.append(plane_types[plane].get(class_type, 0))
            
            datasets.append({
                'label': class_type,
                'data': data,
                'backgroundColor': colors.get(class_type, color_default),
                'borderColor': colors.get(class_type, color_default),
                'borderWidth': 1
            })
        
        result = {
            "labels": sorted_planes,
            "datasets": datasets
        }
        print(f"Revenue chart data prepared: {len(sorted_planes)} labels, {len(datasets)} datasets")
        return result
    except Exception as e:
        print(f"Error preparing revenue chart data: {e}")
        import traceback
        traceback.print_exc()
        return None

def _prepare_cancellation_chart_data(table_rows):
    """Prepare chart data for JavaScript rendering (Report 4 - Cancellation)."""
    if not table_rows:
        return None
    
    try:
        months = []
        rates = []
        for row in table_rows:
            # Access sqlite3.Row with dictionary-style access
            month = str(row['Month']).strip()
            try:
                rate = float(row['Cancellation_Rate'] or 0)
            except (ValueError, TypeError):
                rate = 0.0
            months.append(month)
            rates.append(rate)
        
        if not months:
            print("Cancellation chart: No months data found")
            return None
        
        result = {
            "labels": months,
            "data": rates
        }
        print(f"Cancellation chart data prepared: {len(months)} months")
        return result
    except Exception as e:
        print(f"Error preparing cancellation chart data: {e}")
        import traceback
        traceback.print_exc()
        return None

_REPORT_SQL_CACHE = None
_REPORT_TITLE_CACHE = None

def _load_report_sql():
    """Load manager report queries from sql/flytau_queries.sql."""
    global _REPORT_SQL_CACHE, _REPORT_TITLE_CACHE
    if _REPORT_SQL_CACHE is not None:
        return

    path = os.path.join(app.root_path, "sql", "flytau_queries.sql")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    markers = list(re.finditer(r"--\s*Query\s*(\d+)\s*-\s*(.*?)\s*-+\s*\n", text))
    sql_by_id = {}
    title_by_id = {}

    for i, mk in enumerate(markers):
        rid = int(mk.group(1))
        title = mk.group(2).strip()
        title = re.sub(r"-+$", "", title).strip()

        start = mk.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        block = text[start:end].strip()

        block = re.sub(r"^USE\s+[^;]+;\s*", "", block, flags=re.I)
        block = block.strip()
        if block.endswith(";"):
            block = block[:-1].strip()

        sql_by_id[rid] = block
        title_by_id[rid] = title

    _REPORT_SQL_CACHE = sql_by_id
    _REPORT_TITLE_CACHE = title_by_id


def _pretty_col_name(col: str) -> str:
    mapping = {
        "avg_occupancy_percentage": "Average occupancy (%)",
        "occupancy_percentage": "Occupancy (%)",
        "Cancellation_Rate": "Cancellation rate (%)",
        "Total_Income": "Total income ($)",
        "Flights_Executed": "Flights executed",
        "Flights_Canceled": "Flights canceled",
        "flights_done": "Flights executed",
        "flights_canceled": "Flights canceled",
        "utilization_pct": "Utilization (%)",
        "dominant_route": "Dominant route",
        "CLASS_Type": "Class type",
        "Airplane_ID": "Airplane ID",
        "Aircrew_ID": "Aircrew ID",
        "Flight_ID": "Flight ID",
    }
    if col in mapping:
        return mapping[col]

    s = col.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)

    words = []
    for w in s.split(" "):
        up = w.upper()
        if up in {"ID"}:
            words.append("ID")
        elif up in {"YM"}:
            words.append("Month")
        else:
            words.append(w[:1].upper() + w[1:].lower() if w else w)

    return " ".join(words)


def _get_report_data(report: str):
    _load_report_sql()

    table = []
    cols = []
    chart_path = None

    try:
        rid = int(str(report).strip())
    except Exception:
        rid = 1
    if rid not in _REPORT_SQL_CACHE:
        rid = 1

    title = _REPORT_TITLE_CACHE.get(rid, f"Report {rid}")
    sql = _REPORT_SQL_CACHE[rid]

    table = query_all(sql)

    if table:
        cols = list(table[0].keys())
    else:
        cols = []

    pretty_cols = [_pretty_col_name(c) for c in cols]
    
    # Prepare chart data for JavaScript rendering
    chart_data = None
    if rid == 2:
        chart_data = _prepare_revenue_chart_data(table)
    elif rid == 4:
        chart_data = _prepare_cancellation_chart_data(table)
    
    return str(rid), title, cols, pretty_cols, table, chart_data


def _hours_report_summary(table_rows):
    """Summary for Report 3: max/min hours overall + by Long/Short.

    Report 3 rows contain per-employee totals per flight type.
    We compute:
      - Overall: sum of available flight types per employee
      - Long: max/min within Flight_Type == 'Long'
      - Short: max/min within Flight_Type == 'Short'

    If there is a tie, we keep the first encountered row (arbitrary).
    """

    def _name(r):
        fn = str(r.get("First_name", "")).strip()
        ln = str(r.get("Last_name", "")).strip()
        return (fn + " " + ln).strip() or "Unknown"

    # Build overall sums per employee
    overall = {}
    for r in table_rows or []:
        try:
            crew_id = r.get("ID")
            hours = float(r.get("Total_Flight_Hours") or 0)
        except Exception:
            continue
        key = crew_id
        if key not in overall:
            overall[key] = {"ID": crew_id, "Name": _name(r), "Hours": 0.0}
        overall[key]["Hours"] += hours

    def _pick_max(items, hours_key):
        best = None
        for r in items:
            if best is None or r[hours_key] > best[hours_key]:
                best = r
        return best

    def _pick_min(items, hours_key):
        best = None
        for r in items:
            if best is None or r[hours_key] < best[hours_key]:
                best = r
        return best

    overall_list = list(overall.values())
    max_overall = _pick_max(overall_list, "Hours")
    min_overall = _pick_min(overall_list, "Hours")

    long_rows = []
    short_rows = []
    for r in table_rows or []:
        ft = str(r.get("Flight_Type", "")).strip()
        try:
            hours = float(r.get("Total_Flight_Hours") or 0)
        except Exception:
            hours = 0.0
        entry = {"ID": r.get("ID"), "Name": _name(r), "Hours": hours}
        if ft.lower() == "long":
            long_rows.append(entry)
        elif ft.lower() == "short":
            short_rows.append(entry)

    max_long = _pick_max(long_rows, "Hours")
    min_long = _pick_min(long_rows, "Hours")
    max_short = _pick_max(short_rows, "Hours")
    min_short = _pick_min(short_rows, "Hours")

    return {
        "max_overall": max_overall,
        "min_overall": min_overall,
        "max_long": max_long,
        "min_long": min_long,
        "max_short": max_short,
        "min_short": min_short,
    }

def _revenue_report2_summary(table_rows):
    """Summary for Report 2:
    Pick top-earning manufacturer in Regular, First, and Overall.
    Ties are broken arbitrarily by first encountered row.
    Expected columns: Manufacturer, CLASS_Type, Total_Income.
    """

    def _to_float(x):
        try:
            return float(x)
        except Exception:
            try:
            # handle Decimal / None
                return float(str(x))
            except Exception:
                return 0.0

    best_regular = None
    best_first = None

    overall = {}
    for r in table_rows or []:
        man = str(r.get("Manufacturer", "")).strip() or "Unknown"
        cls = str(r.get("CLASS_Type", "")).strip()
        inc = _to_float(r.get("Total_Income", 0))
        # per class best
        if cls.lower() == "regular":
            if best_regular is None or inc > _to_float(best_regular.get("Total_Income", 0)):
                best_regular = {"Manufacturer": man, "Total_Income": inc}
        if cls.lower() == "first":
            if best_first is None or inc > _to_float(best_first.get("Total_Income", 0)):
                best_first = {"Manufacturer": man, "Total_Income": inc}
        # overall sum
        overall.setdefault(man, 0.0)
        overall[man] += inc

    best_overall = None
    for man, inc in overall.items():
        if best_overall is None or inc > best_overall["Total_Income"]:
            best_overall = {"Manufacturer": man, "Total_Income": inc}

    # fallbacks
    if best_regular is None:
        best_regular = {"Manufacturer": "N/A", "Total_Income": 0.0}
    if best_first is None:
        best_first = {"Manufacturer": "N/A", "Total_Income": 0.0}
    if best_overall is None:
        best_overall = {"Manufacturer": "N/A", "Total_Income": 0.0}

    return {"regular": best_regular, "first": best_first, "overall": best_overall}


def _cancellation_report4_extremes(table_rows):
    """Report 4: pick months with lowest/highest cancellation rate.

    Ties are broken randomly.
    Expected columns: Month, Cancellation_Rate
    """

    def _to_float(x):
        try:
            return float(x)
        except Exception:
            try:
                return float(str(x))
            except Exception:
                return 0.0

    rows = []
    for r in table_rows or []:
        month = str(r.get("Month", "")).strip()
        rate = _to_float(r.get("Cancellation_Rate", 0))
        rows.append({"Month": month or "N/A", "Rate": rate})

    if not rows:
        return {"min": None, "max": None}

    min_val = min(x["Rate"] for x in rows)
    max_val = max(x["Rate"] for x in rows)
    min_candidates = [x for x in rows if x["Rate"] == min_val]
    max_candidates = [x for x in rows if x["Rate"] == max_val]

    return {
        "min": random.choice(min_candidates) if min_candidates else None,
        "max": random.choice(max_candidates) if max_candidates else None,
    }


def _fleet_report5_extremes(table_rows):
    """Report 5: for the selected month, pick aircraft with:
      - highest/lowest utilization
      - highest/lowest flights executed

    Month selection: current month (YYYY-MM) if present in data, otherwise latest month in data.
    Ties are broken randomly.

    Expected columns: Airplane_ID, Month, Flights_Executed, Utilization_Percentage
    """

    def _to_float(x):
        try:
            return float(x)
        except Exception:
            try:
                return float(str(x))
            except Exception:
                return 0.0

    def _to_int(x):
        try:
            return int(x)
        except Exception:
            try:
                return int(float(str(x)))
            except Exception:
                return 0

    if not table_rows:
        return {"month": None, "max_util": None, "min_util": None, "max_flights": None, "min_flights": None}

    months = sorted({str(r.get("Month", "")).strip() for r in table_rows if str(r.get("Month", "")).strip()})
    if not months:
        return {"month": None, "max_util": None, "min_util": None, "max_flights": None, "min_flights": None}

    current_month = date.today().strftime("%Y-%m")
    month_to_use = current_month if current_month in months else months[-1]

    rows = []
    for r in table_rows:
        if str(r.get("Month", "")).strip() != month_to_use:
            continue
        rows.append({
            "Airplane_ID": r.get("Airplane_ID"),
            "Util": _to_float(r.get("Utilization_Percentage", 0)),
            "Flights": _to_int(r.get("Flights_Executed", 0)),
        })

    if not rows:
        return {"month": month_to_use, "max_util": None, "min_util": None, "max_flights": None, "min_flights": None}

    max_util_val = max(x["Util"] for x in rows)
    min_util_val = min(x["Util"] for x in rows)
    max_flights_val = max(x["Flights"] for x in rows)
    min_flights_val = min(x["Flights"] for x in rows)

    return {
        "month": month_to_use,
        "max_util": random.choice([x for x in rows if x["Util"] == max_util_val]),
        "min_util": random.choice([x for x in rows if x["Util"] == min_util_val]),
        "max_flights": random.choice([x for x in rows if x["Flights"] == max_flights_val]),
        "min_flights": random.choice([x for x in rows if x["Flights"] == min_flights_val]),
    }



@app.route("/manager/reports")
def manager_reports():
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    report = request.args.get("r", "1").strip()
    report, title, cols, pretty_cols, table, chart_data = _get_report_data(report)
    return render_template("manager_reports.html", report=report, title=title, cols=cols, pretty_cols=pretty_cols, table=table, chart_data=chart_data)


@app.route("/manager/reports/<int:rid>")
def manager_report_page(rid: int):
    if not is_logged_in("manager"):
        return redirect(url_for("login"))
    if rid not in (1,2,3,4,5):
        return redirect(url_for("manager_reports"))
    report, title, cols, pretty_cols, table, chart_data = _get_report_data(str(rid))

    summary = None
    top_manufacturers = None
    cancel_extremes = None
    fleet_extremes = None
    if str(rid) == "3":
        summary = _hours_report_summary(table)
    if str(rid) == "2":
        top_manufacturers = _revenue_report2_summary(table)
    if str(rid) == "4":
        cancel_extremes = _cancellation_report4_extremes(table)
    if str(rid) == "5":
        fleet_extremes = _fleet_report5_extremes(table)

    return render_template(
        "manager_report_view.html",
        report=report,
        title=title,
        cols=cols,
        pretty_cols=pretty_cols,
        table=table,
        chart_data=chart_data,
        summary=summary,
        top_manufacturers=top_manufacturers,
        cancel_extremes=cancel_extremes,
        fleet_extremes=fleet_extremes,
    )

if __name__ == "__main__":
    app.run(debug=True)