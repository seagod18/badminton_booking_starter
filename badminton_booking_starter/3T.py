from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3

from flask import Flask, redirect, render_template_string, request, url_for, flash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "badminton_bookings.db"

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret-before-deploying"

# Court hours: 5:00 AM to 10:00 PM, with 17 one-hour slots.
SLOT_STARTS = list(range(5, 22))


def connect_db():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_date TEXT NOT NULL,
                start_hour INTEGER NOT NULL,
                apartment TEXT NOT NULL,
                players INTEGER NOT NULL,
                booking_type TEXT NOT NULL DEFAULT 'online',
                created_at TEXT NOT NULL,
                UNIQUE (booking_date, start_hour)
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_bookings_date
            ON bookings (booking_date)
        """)


def hour_label(hour):
    def fmt(h):
        suffix = "AM" if h < 12 else "PM"
        shown = h % 12 or 12
        return f"{shown} {suffix}"
    return f"{fmt(hour)} – {fmt(hour + 1)}"


def get_bookings_for_day(day):
    with connect_db() as db:
        rows = db.execute(
            "SELECT * FROM bookings WHERE booking_date = ? ORDER BY start_hour",
            (day,)
        ).fetchall()
    return {row["start_hour"]: dict(row) for row in rows}


def can_book(day_text, hour, players, bookings, now=None):
    """
    Booking rules implemented:
    - Only court slots from 5 AM through 9 PM starts are valid.
    - A slot normally opens for online booking one hour before it starts.
    - If the immediately previous slot is booked, the next slot can be booked
      earlier (the apartment's consecutive-slot exception).
    - A booking may cover two consecutive hours only when players > 6.
    """
    if hour not in SLOT_STARTS:
        return False, "That time is outside court hours."

    if hour in bookings:
        return False, "That slot has already been booked."

    now = now or datetime.now()
    selected_date = date.fromisoformat(day_text)
    slot_start = datetime.combine(selected_date, datetime.min.time()).replace(hour=hour)

    # Allow future dates only when the booking window is open at that date/time.
    previous_slot_booked = (hour - 1) in bookings
    booking_window_open = now >= slot_start - timedelta(hours=1)

    if selected_date < now.date():
        return False, "You cannot book a slot in the past."

    if selected_date == now.date() and not booking_window_open and not previous_slot_booked:
        return False, "Online booking opens one hour before the slot, unless the previous slot is booked."

    if players < 1 or players > 20:
        return False, "Enter a valid number of players (1–20)."

    return True, ""


PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sobha Daffodils | Badminton Booking</title>
  <style>
    :root { --ink:#17212f; --muted:#667085; --line:#e5eaf0; --bg:#f4f7fb;
            --blue:#275df5; --green:#e8f8ef; --green-ink:#137547;
            --red:#fff0ef; --red-ink:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;
           background:var(--bg); color:var(--ink); }
    header { background:#10233f; color:white; padding:26px 20px; }
    .wrap { max-width:1100px; margin:auto; }
    .eyebrow { color:#9db7ff; font-size:.8rem; text-transform:uppercase;
               letter-spacing:.12em; font-weight:700; }
    h1 { margin:6px 0; font-size:clamp(1.5rem,4vw,2.1rem); }
    header p { color:#d4dced; margin:8px 0 0; }
    main { max-width:1100px; margin:24px auto; padding:0 16px 40px;
           display:grid; grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr); gap:20px; }
    .panel { background:white; border:1px solid var(--line); border-radius:16px;
             padding:20px; box-shadow:0 6px 24px #14213d08; }
    .panel h2 { margin:0 0 6px; font-size:1.15rem; }
    .muted { color:var(--muted); font-size:.92rem; }
    form { display:grid; gap:12px; }
    label { display:block; font-weight:650; font-size:.9rem; margin-bottom:6px; }
    input, select { width:100%; padding:11px 12px; border:1px solid #cfd7e3;
                    border-radius:9px; background:white; color:var(--ink); font:inherit; }
    button { border:0; border-radius:9px; padding:12px 14px; font:inherit;
             font-weight:700; cursor:pointer; }
    .primary { background:var(--blue); color:white; }
    .secondary { background:#eef2f7; color:#344054; }
    .slots { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:18px; }
    .slot { padding:12px; border:1px solid #cdebd8; border-radius:11px;
            background:var(--green); color:var(--green-ink); text-align:left; }
    .slot strong { display:block; font-size:.95rem; }
    .slot small { display:block; margin-top:5px; opacity:.85; }
    .slot.booked { border-color:#f3c5c2; background:var(--red); color:var(--red-ink); }
    .slot.selected { outline:2px solid var(--blue); outline-offset:1px; }
    .slot:disabled { cursor:not-allowed; opacity:.9; }
    .legend { display:flex; flex-wrap:wrap; gap:12px; margin-top:14px; font-size:.82rem; color:var(--muted); }
    .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
    .message { padding:11px 13px; border-radius:9px; background:#eef4ff; color:#2447a8; margin:0 0 12px; }
    .error { background:#fff0ef; color:#b42318; }
    .success { background:#e8f8ef; color:#137547; }
    .booking-row { border-top:1px solid var(--line); padding:11px 0; font-size:.9rem; }
    .booking-row:first-of-type { margin-top:10px; }
    .booking-row strong { display:block; }
    .full { grid-column:1/-1; }
    @media(max-width:760px) { main { grid-template-columns:1fr; } .slots { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media(max-width:390px) { .slots { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="eyebrow">Resident facilities</div>
    <h1>🏸 Sobha Daffodils Court Booking</h1>
    <p>Check today's schedule and reserve your badminton session.</p>
  </div>
</header>
<main>
  <section class="panel">
    <h2>Daily schedule</h2>
    <p class="muted">Choose a date to view the court's 5 AM–10 PM schedule.</p>
    {% for category, message in get_flashed_messages(with_categories=true) %}
      <div class="message {{ category }}">{{ message }}</div>
    {% endfor %}
    <form method="get" action="/" style="grid-template-columns:1fr auto; align-items:end;">
      <div>
        <label for="date">Booking date</label>
        <input id="date" type="date" name="date" value="{{ selected_date }}" min="{{ today }}">
      </div>
      <button class="secondary" type="submit">View date</button>
    </form>
    <div class="slots">
      {% for slot in slots %}
        <button type="button"
          class="slot {% if slot.booked %}booked{% endif %}"
          {% if slot.booked %}disabled{% else %}onclick="selectSlot({{ slot.hour }}, '{{ slot.label }}')"{% endif %}>
          <strong>{{ slot.label }}</strong>
          <small>{% if slot.booked %}Booked · Apt {{ slot.apartment }}{% else %}Available{% endif %}</small>
        </button>
      {% endfor %}
    </div>
    <div class="legend">
      <span><i class="dot" style="background:#32a56a"></i>Available</span>
      <span><i class="dot" style="background:#d92d20"></i>Booked</span>
    </div>
  </section>

  <aside class="panel" id="booking">
    <h2>Book a slot</h2>
    <p class="muted">Select an available slot, then enter your details.</p>
    <form method="post" action="/book">
      <input type="hidden" name="date" value="{{ selected_date }}">
      <input type="hidden" name="start_hour" id="start_hour" value="{{ default_hour }}">
      <div>
        <label>Selected time</label>
        <input id="selected_label" value="{{ default_label }}" readonly>
      </div>
      <div>
        <label for="apartment">4-digit apartment number</label>
        <input id="apartment" name="apartment" inputmode="numeric" pattern="[0-9]{4}"
               maxlength="4" placeholder="e.g. 1203" required>
      </div>
      <div>
        <label for="players">Number of players</label>
        <input id="players" name="players" type="number" min="1" max="20" value="4" required>
        <p class="muted">More than 6 players may qualify for a second consecutive hour.</p>
      </div>
      <button class="primary" type="submit">Book court</button>
    </form>
    <p class="muted" style="margin-top:14px;">Prototype note: the current version stores one booking per hourly slot. Two-hour bookings will be added next.</p>
  </aside>

  <section class="panel full">
    <h2>Bookings for {{ selected_date }}</h2>
    <p class="muted">Bookings recorded in the local SQLite database.</p>
    {% if booking_list %}
      {% for b in booking_list %}
        <div class="booking-row">
          <strong>{{ b.label }} · Apartment {{ b.apartment }}</strong>
          <span class="muted">{{ b.players }} player(s) · {{ b.booking_type|capitalize }} booking</span>
        </div>
      {% endfor %}
    {% else %}
      <p class="muted">No bookings have been made for this date yet.</p>
    {% endif %}
  </section>
</main>
<script>
  function selectSlot(hour, label) {
    document.getElementById('start_hour').value = hour;
    document.getElementById('selected_label').value = label;
    document.querySelectorAll('.slot:not(.booked)').forEach(el => el.classList.remove('selected'));
    const clicked = [...document.querySelectorAll('.slot')].find(el => el.querySelector('strong')?.textContent === label);
    if (clicked) clicked.classList.add('selected');
    document.getElementById('booking').scrollIntoView({behavior:'smooth', block:'start'});
  }
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    selected_date = request.args.get("date", date.today().isoformat())
    try:
        date.fromisoformat(selected_date)
    except ValueError:
        selected_date = date.today().isoformat()

    bookings = get_bookings_for_day(selected_date)
    slots = []
    for hour in SLOT_STARTS:
        booking = bookings.get(hour)
        slots.append({
            "hour": hour,
            "label": hour_label(hour),
            "booked": booking is not None,
            "apartment": booking["apartment"] if booking else None,
        })

    booking_list = []
    for hour, booking in sorted(bookings.items()):
        booking_list.append({
            **booking,
            "label": hour_label(hour),
        })

    default_hour = next((h for h in SLOT_STARTS if h not in bookings), 17)
    return render_template_string(
        PAGE,
        selected_date=selected_date,
        today=date.today().isoformat(),
        slots=slots,
        booking_list=booking_list,
        default_hour=default_hour,
        default_label=hour_label(default_hour),
    )


@app.route("/book", methods=["POST"])
def book():
    selected_date = request.form.get("date", "")
    apartment = request.form.get("apartment", "").strip()
    try:
        day = date.fromisoformat(selected_date)
        hour = int(request.form.get("start_hour", ""))
        players = int(request.form.get("players", ""))
    except (ValueError, TypeError):
        flash("Please enter a valid date, time, and player count.", "error")
        return redirect(url_for("home"))

    if len(apartment) != 4 or not apartment.isdigit():
        flash("Apartment number must contain exactly four digits.", "error")
        return redirect(url_for("home", date=selected_date))

    bookings = get_bookings_for_day(selected_date)
    allowed, reason = can_book(selected_date, hour, players, bookings)
    if not allowed:
        flash(reason, "error")
        return redirect(url_for("home", date=selected_date))

    try:
        with connect_db() as db:
            db.execute("""
                INSERT INTO bookings
                (booking_date, start_hour, apartment, players, booking_type, created_at)
                VALUES (?, ?, ?, ?, 'online', ?)
            """, (
                day.isoformat(), hour, apartment, players,
                datetime.now().isoformat(timespec="seconds")
            ))
        flash(f"Booked {hour_label(hour)} for apartment {apartment}.", "success")
    except sqlite3.IntegrityError:
        flash("Someone has just booked that slot. Please choose another.", "error")

    return redirect(url_for("home", date=selected_date))


if __name__ == "__main__":
    init_db()
    print(f"Database: {DB_PATH}")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)
