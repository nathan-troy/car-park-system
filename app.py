from flask import Flask, render_template, request, redirect, url_for, session, flash
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
    return render_template('index.html', car_parks=car_parks, user_bookings=user_bookings)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('index'))
    db = get_db()
    all_bookings = db.execute('''SELECT b.*, u.username, cp.name as car_park_name FROM bookings b 
                                JOIN users u ON b.user_id = u.user_id 
                                JOIN car_parks cp ON b.car_park_id = cp.car_park_id 
                                ORDER BY b.date_start DESC''').fetchall()
    return render_template('admin.html', all_bookings=all_bookings)

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
        flash('Invalid username or password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)



