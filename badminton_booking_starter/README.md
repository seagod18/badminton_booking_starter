# Sobha Daffodils Badminton Booking — Python starter

## Files
- `3T.py`: Flask app, HTML/CSS interface, booking logic, and SQLite database initialization.
- `badminton_bookings.db`: created automatically when you run the app.

## Setup in VS Code
1. Open this folder in VS Code.
2. Open Terminal → New Terminal.
3. (Recommended) create a virtual environment:
   - Windows: `py -m venv .venv`
   - PowerShell: `.venv\Scripts\Activate.ps1`
   - Command Prompt: `.venv\Scripts\activate.bat`
4. Install Flask: `py -m pip install flask`
5. Run: `py 3T.py`
6. Open http://127.0.0.1:5000 in your browser.

If `py` does not work, try `python` instead.

## Current prototype limitations
- Booking records are local to this computer.
- There is no authentication yet.
- One booking per hourly slot is implemented; the >6-player second-hour rule is only noted in the UI and still needs full implementation.
- The “previous slot booked” exception is implemented for online booking, but we should test/refine exact policy details with real examples.
- The date/time check uses the computer's local timezone.
- `debug=True` is for local development only; turn it off before deployment.
