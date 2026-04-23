from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'secret'

DB = 'parking.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# --- Setup (run once) ---
def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                is_admin INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                car_park TEXT,
                date TEXT,
                UNIQUE(user_id, date)
            );
        ''')
        add_example_users(db)

def add_example_users(db):
    try:
        db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 1))
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
            ('staff1', generate_password_hash('pass123')))
    except:
        pass  # already seeded

# --- Routes ---
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    bookings = db.execute(
        'SELECT * FROM bookings WHERE user_id = ? ORDER BY date', (session['user_id'],)
    ).fetchall()
    return render_template('index.html', bookings=bookings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('index'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/book', methods=['POST'])
def book():
    car_park = request.form['car_park']
    date = request.form['date']
    capacity = 20 if car_park == 'A' else 15
    db = get_db()
    taken = db.execute(
        'SELECT COUNT(*) FROM bookings WHERE car_park = ? AND date = ?', (car_park, date)
    ).fetchone()[0]
    if taken >= capacity:
        flash(f'Car Park {car_park} is full on that date.')
    else:
        try:
            db.execute('INSERT INTO bookings (user_id, car_park, date) VALUES (?, ?, ?)',
                (session['user_id'], car_park, date))
            db.commit()
            flash('Booking confirmed!')
        except:
            flash('You already have a booking that day.')
    return redirect(url_for('index'))

@app.route('/cancel/<int:booking_id>')
def cancel(booking_id):
    db = get_db()
    db.execute('DELETE FROM bookings WHERE id = ? AND user_id = ?', (booking_id, session['user_id']))
    db.commit()
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    db = get_db()
    bookings = db.execute(
        'SELECT b.*, u.username FROM bookings b JOIN users u ON b.user_id = u.id ORDER BY date'
    ).fetchall()
    return render_template('admin.html', bookings=bookings)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)