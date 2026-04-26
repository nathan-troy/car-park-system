from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'secret'

DB = 'parking.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

# --- Setup (run once) ---
def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                is_admin BOOL DEFAULT 0
            );         
            CREATE TABLE IF NOT EXISTS car_parks (
                car_park_id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                capacity INTEGER
            );
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                car_park_id INTEGER,
                date_start DATETIME,
                date_end DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (car_park_id) REFERENCES car_parks(car_park_id)
            );     
        ''')
        add_example_users(db)
        add_car_parks(db)

def add_example_users(db):
    try:
        db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 1))
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
            ('staff1', generate_password_hash('pass123')))
    except:
        pass  # already exists

def add_car_parks(db):
    try:
        db.execute("INSERT INTO car_parks (name, capacity) VALUES (?, ?)",
            ('Car Park A', 25))
        db.execute("INSERT INTO car_parks (name, capacity) VALUES (?, ?)",
            ('Car Park B', 40))
    except:
        pass  # already exists
    
#routes
@app.route('/')
def index():
    if 'user_id' not in session: #if user hasnt logged in
        return redirect(url_for('login'))
    
    db = get_db()
    bookings = db.execute(
        '''SELECT b.*, cp.name as car_park_name
           FROM bookings b
           JOIN car_parks cp ON b.car_park_id = cp.car_park_id
           WHERE b.user_id = ?
           ORDER BY b.date_start''',
        (session['user_id'],)
    ).fetchall()
    car_parks = db.execute(
        'SELECT * FROM car_parks'
    ).fetchall()
    return render_template('index.html', bookings=bookings, car_parks=car_parks)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?',
            (request.form['username'],)
        ).fetchone()
        # if username and password match up correctly, set session stuff
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/book', methods=['POST'])
def book():
    car_park_id = request.form['car_park_id']
    date_start = request.form['date_start']
    date_end = request.form['date_end']
    db = get_db()

    # Validate dates
    if date_end <= date_start:
        flash('End date must be after start date.')
        return redirect(url_for('index'))

    # Get car park details
    car_park = db.execute(
        'SELECT * FROM car_parks WHERE car_park_id = ?', (car_park_id,)
    ).fetchone()

    # check user doesn't already have an overlapping booking
    conflict = db.execute('''
        SELECT COUNT(*) FROM bookings
        WHERE user_id = ?
        AND date_start < ?
        AND date_end > ?
    ''', (session['user_id'], date_end, date_start)).fetchone()[0]

    if conflict:
        flash('You already have a booking during that period.')
        return redirect(url_for('index'))

    # check car park isnt full during that period
    taken = db.execute('''
        SELECT COUNT(*) FROM bookings
        WHERE car_park_id = ?
        AND date_start < ?
        AND date_end > ?
    ''', (car_park_id, date_end, date_start)).fetchone()[0]

    if taken >= car_park['capacity']:
        flash(f"{car_park['name']} is full during that period.")
        return redirect(url_for('index'))

    db.execute(
        'INSERT INTO bookings (user_id, car_park_id, date_start, date_end) VALUES (?, ?, ?, ?)',
        (session['user_id'], car_park_id, date_start, date_end)
    )
    db.commit()
    flash('Booking confirmed!')
    return redirect(url_for('index'))

@app.route('/cancel/<int:booking_id>')
def cancel(booking_id):
    db = get_db()
    if session.get('is_admin'):
        # admins can cancel any booking
        db.execute('DELETE FROM bookings WHERE booking_id = ?', (booking_id,))
    else:
        # regular users can only cancel their own
        db.execute(
            'DELETE FROM bookings WHERE booking_id = ? AND user_id = ?',
            (booking_id, session['user_id'])
        )
    db.commit()
    return redirect(url_for('admin') if session.get('is_admin') else url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    db = get_db()
    bookings = db.execute(
        '''SELECT b.*, u.username, cp.name as car_park_name
           FROM bookings b
           JOIN users u ON b.user_id = u.user_id
           JOIN car_parks cp ON b.car_park_id = cp.car_park_id
           ORDER BY b.date_start'''
    ).fetchall()
    return render_template('admin.html', bookings=bookings)

if __name__ == '__main__':
    init_db()
    app.run(debug=False)