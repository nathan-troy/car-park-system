from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_parking_key'
DB = 'parking.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, is_admin BOOL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS car_parks (car_park_id INTEGER PRIMARY KEY, name TEXT UNIQUE, capacity INTEGER);
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id INTEGER PRIMARY KEY, user_id INTEGER, car_park_id INTEGER, 
                spot_number INTEGER, date_start DATETIME, date_end DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        ''')
        try:
            db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('admin', generate_password_hash('admin123'), 1))
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('staff1', generate_password_hash('pass123')))
            db.execute("INSERT INTO car_parks (name, capacity) VALUES (?, ?)", ('Car Park A', 20))
            db.execute("INSERT INTO car_parks (name, capacity) VALUES (?, ?)", ('Car Park B', 10))
            db.commit()
        except sqlite3.IntegrityError: pass

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Vectura Park Management System</title>
    <link href="https://jsdelivr.net" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; padding-top: 90px; }
        .navbar { background-color: #ffffff !important; border-bottom: 2px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .navbar-brand { color: #212529 !important; font-weight: 700; letter-spacing: -0.5px; }
        .nav-link { color: #495057 !important; font-weight: 500; }
        .lot-wrapper { display: flex; justify-content: center; width: 100%; margin-bottom: 25px; }
        .parking-lot-container { 
            display: inline-grid; grid-template-columns: repeat(10, 1fr); gap: 0;
            background: #bdc3c7; padding: 15px; border-radius: 8px; border: 4px solid #95a5a6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .aisle { grid-column: 1 / -1; height: 40px; background: #95a5a6; margin: 10px 0; border-top: 2px dashed #ecf0f1; border-bottom: 2px dashed #ecf0f1; }
        .spot-wrapper { border-right: 2px solid #ecf0f1; padding: 3px; min-width: 65px; }
        .spot-wrapper:last-child { border-right: none; }
        .spot { 
            height: 90px; display: flex; align-items: center; justify-content: center; 
            font-weight: bold; cursor: pointer; border-radius: 4px; color: white; 
            transition: 0.2s; border: none; font-size: 0.85rem;
        }
        .free { background-color: #2ecc71; }
        .free:hover { background-color: #27ae60; transform: translateY(-3px); }
        .occupied { background-color: #e74c3c; cursor: not-allowed; opacity: 0.8; }
        .selected { background-color: #0d6efd !important; border: 2px solid white; transform: scale(1.05); z-index: 2; }
        .card { border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-radius: 15px; }
        
        /* Positioning Titles riiiiiight on top of maps */
        .cp-title { font-weight: 800; font-size: 0.75rem; color: #6c757d; text-transform: uppercase; margin-bottom: 2px; }
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-light fixed-top">
  <div class="container">
    <a class="navbar-brand" href="/">🅿️ PARK MANAGEMENT SYSTEM</a>
    <div class="collapse navbar-collapse justify-content-center">
      <ul class="navbar-nav">
        <li class="nav-item"><a class="nav-link" href="#">Profile</a></li>
        <li class="nav-item"><a class="nav-link" href="#">Settings</a></li>
        {% if session['is_admin'] %}
        <li class="nav-item"><a class="nav-link text-primary fw-bold" href="{{ url_for('admin_dashboard') }}">Admin Dashboard</a></li>
        {% endif %}
      </ul>
    </div>
    <div class="navbar-text">
        <span class="me-3 small text-muted">User: <strong>{{ session['username'] }}</strong></span>
        <a href="{{ url_for('logout') }}" class="btn btn-sm btn-outline-danger px-3">Logout</a>
    </div>
  </div>
</nav>

<div class="container pb-5">
    <div class="row">
        <div class="col-12 text-center">
            {% for cp in car_parks %}
            <div class="cp-title mt-4">{{ cp.name }}</div>
            <div class="lot-wrapper">
                <div class="parking-lot-container">
                    {% set prefix = cp.name[-1] %}
                    {% for i in range(1, (cp.capacity // 2) + 1) %}
                        <div class="spot-wrapper"><div class="spot {{ 'occupied' if i in cp.occupied_spots else 'free' }}" onclick="selectSpot(this, {{ cp.id }}, {{ i }}, '{{ cp.name }}', '{{ prefix }}{{ i }}')">{{ prefix }}{{ i }}</div></div>
                    {% endfor %}
                    <div class="aisle"></div>
                    {% for i in range((cp.capacity // 2) + 1, cp.capacity + 1) %}
                        <div class="spot-wrapper"><div class="spot {{ 'occupied' if i in cp.occupied_spots else 'free' }}" onclick="selectSpot(this, {{ cp.id }}, {{ i }}, '{{ cp.name }}', '{{ prefix }}{{ i }}')">{{ prefix }}{{ i }}</div></div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Staff's individual reservation history -->
    <div class="row justify-content-center mb-5">
        <div class="col-md-10">
            <div class="card shadow-sm"><div class="card-body">
                <h6 class="fw-bold mb-3">My Current Reservations</h6>
                <table class="table table-sm small align-middle">
                    <thead class="table-light"><tr><th>Lot</th><th>Spot</th><th>Start</th><th>End</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for b in user_bookings %}
                        <tr>
                            <td>{{ b.car_park_name }}</td>
                            <td>{{ b.car_park_name[-1] }}{{ b.spot_number }}</td>
                            <td>{{ b.date_start.replace('T', ' ') }}</td>
                            <td>{{ b.date_end.replace('T', ' ') }}</td>
                            <td><a href="{{ url_for('cancel', booking_id=b.booking_id) }}" class="btn btn-xs btn-danger" style="font-size:0.7rem">Cancel</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div></div>
        </div>
    </div>

    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card shadow-sm"><div class="card-body p-4 text-center">
                <h5 class="fw-bold mb-4">Book Your Space</h5>
                <form action="{{ url_for('book') }}" method="POST">
                    <input type="hidden" name="car_park_id" id="form_cp_id">
                    <div class="mb-3">
                        <input type="text" id="display_info" class="form-control text-center bg-light border-0 fw-bold py-3" readonly placeholder="Click a spot above">
                        <input type="hidden" name="spot_number" id="form_spot_num">
                    </div>
                    <div class="row mb-3">
                        <div class="col"><label class="small fw-bold">From</label><input type="datetime-local" name="date_start" class="form-control" required></div>
                        <div class="col"><label class="small fw-bold">Until</label><input type="datetime-local" name="date_end" class="form-control" required></div>
                    </div>
                    <button type="submit" class="btn btn-primary btn-lg w-100 shadow" id="book_btn" disabled>Confirm Booking</button>
                </form>
            </div></div>
        </div>
    </div>
</div>
<script>
function selectSpot(el, cpId, spotNum, cpName, displayLabel) {
    if (el.classList.contains('occupied')) return;
    document.querySelectorAll('.spot').forEach(s => s.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('form_cp_id').value = cpId;
    document.getElementById('form_spot_num').value = spotNum;
    document.getElementById('display_info').value = cpName + " - " + displayLabel;
    document.getElementById('book_btn').disabled = false;
}
</script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel</title>
    <link href="https://jsdelivr.net" rel="stylesheet">
</head>
<body class="bg-light" style="padding-top: 90px;">
<nav class="navbar navbar-expand-lg navbar-light bg-white border-bottom fixed-top"><div class="container"><a class="navbar-brand fw-bold" href="/">🅿️ ADMIN PANEL</a><a href="/" class="btn btn-outline-primary btn-sm">Back to Map</a></div></nav>
<div class="container py-4"><div class="card border-0 shadow-sm"><div class="card-body p-4">
    <h4 class="fw-bold mb-4">All Active Reservations</h4>
    <table class="table table-striped small">
        <thead class="table-dark"><tr><th>User</th><th>Lot</th><th>Spot</th><th>Start</th><th>End</th><th>Action</th></tr></thead>
        <tbody>
            {% for b in all_bookings %}
            <tr><td><strong>{{ b.username }}</strong></td><td>{{ b.car_park_name }}</td><td>{{ b.car_park_name[-1] }}{{ b.spot_number }}</td><td>{{ b.date_start }}</td><td>{{ b.date_end }}</td><td><a href="{{ url_for('cancel', booking_id=b.booking_id) }}" class="btn btn-sm btn-danger">Void</a></td></tr>
            {% endfor %}
        </tbody>
    </table>
</div></div></div>
</body>
</html>
"""

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    db, now = get_db(), datetime.now().strftime('%Y-%m-%dT%H:%M')
    car_parks = []
    for cp in db.execute('SELECT * FROM car_parks').fetchall():
        rows = db.execute('SELECT spot_number FROM bookings WHERE car_park_id = ? AND ? BETWEEN date_start AND date_end', (cp['car_park_id'], now)).fetchall()
        car_parks.append({'id': cp['car_park_id'], 'name': cp['name'], 'capacity': cp['capacity'], 'occupied_spots': [r['spot_number'] for r in rows]})
    
    user_bookings = db.execute('''SELECT b.*, cp.name as car_park_name FROM bookings b 
                                 JOIN car_parks cp ON b.car_park_id = cp.car_park_id 
                                 WHERE b.user_id = ? ORDER BY b.date_start DESC''', (session['user_id'],)).fetchall()
    return render_template_string(INDEX_HTML, car_parks=car_parks, user_bookings=user_bookings)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('index'))
    db = get_db()
    all_bookings = db.execute('''SELECT b.*, u.username, cp.name as car_park_name FROM bookings b 
                                JOIN users u ON b.user_id = u.user_id 
                                JOIN car_parks cp ON b.car_park_id = cp.car_park_id 
                                ORDER BY b.date_start DESC''').fetchall()
    return render_template_string(ADMIN_HTML, all_bookings=all_bookings)

@app.route('/book', methods=['POST'])
def book():
    db = get_db()
    db.execute('INSERT INTO bookings (user_id, car_park_id, spot_number, date_start, date_end) VALUES (?,?,?,?,?)', 
               (session['user_id'], request.form['car_park_id'], request.form['spot_number'], request.form['date_start'], request.form['date_end']))
    db.commit()
    return redirect(url_for('index'))

@app.route('/cancel/<int:booking_id>')
def cancel(booking_id):
    db = get_db()
    db.execute('DELETE FROM bookings WHERE booking_id = ?', (booking_id,))
    db.commit()
    # Return to Admin Panel if user is admin, otherwise return to Home
    if session.get('is_admin'):
        # Only go back to dashboard if we actually came from there (simple check)
        return redirect(request.referrer or url_for('admin_dashboard'))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session.update({'user_id': user['user_id'], 'username': user['username'], 'is_admin': user['is_admin']})
            return redirect(url_for('index'))
    return render_template_string('<link href="https://jsdelivr.net" rel="stylesheet"><body class="bg-light d-flex align-items-center vh-100"><div class="container card p-4 shadow-sm" style="max-width:400px"><h4 class="text-center mb-4">SYSTEM LOGIN</h4><form method="POST"><input name="username" class="form-control mb-3" placeholder="User" required><input name="password" type="password" class="form-control mb-4" placeholder="Pass" required><button class="btn btn-primary w-100">Sign In</button></form></div></body>')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)



