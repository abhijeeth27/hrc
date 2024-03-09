from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = '27'  # Change this to a secure secret key

def get_db_connection():
    conn = sqlite3.connect('employee_database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            contact TEXT NOT NULL,
            emergency_contact TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendanceRecord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkin_time DATETIME,
            checkout_time DATETIME,
            leave_applications TEXT DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

def register_user(name, email, password, contact, emergency_contact):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        cursor.execute('''
            INSERT INTO users (name, email, password, contact, emergency_contact)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, hashed_password, contact, emergency_contact))

        conn.commit()
        flash('Registration successful!', 'success')
    except sqlite3.IntegrityError:
        flash('Email address already exists. Please use a different email.', 'danger')
    finally:
        conn.close()

def login_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    conn.close()

    if user and check_password_hash(user['password'], password):
        return True
    else:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        contact = request.form['contact']
        emergency_contact = request.form['emergency_contact']

        # Check if password and confirm password match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('index'))

        # Register the user
        register_user(name, email, password, contact, emergency_contact)

        return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if login_user(email, password):
            session['user_email'] = email  # Store user email in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('index'))

        
@app.route('/dashboard')  
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM AttendanceRecord ORDER BY checkin_time DESC')
    records = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', attendance_records=records)

@app.route('/logout')
def logout():
    # Perform any logout actions here if needed
    return redirect(url_for('index'))

@app.route('/apply_leave', methods=['POST'])
def apply_leave():
    try:
        leave_reason = request.json['reason']  # Extract leave reason from the JSON data

        # Get user email from session
        user_email = session.get('user_email', None)

        if user_email:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if there's an open entry (check-in) for the current day
            cursor.execute('SELECT * FROM AttendanceRecord WHERE date(checkin_time) = date("now") AND checkout_time IS NULL AND user_email = ?',
                           (user_email,))
            existing_checkin = cursor.fetchone()

            if existing_checkin:
                # Update the leave applications column for the existing check-in entry
                cursor.execute('UPDATE AttendanceRecord SET leave_applications=? WHERE id=?',
                               (leave_reason, existing_checkin['id']))
                conn.commit()
                conn.close()

                return jsonify({'message': 'Leave application submitted successfully'})
            else:
                # If there's no open entry, create a new one with leave application information
                checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('INSERT INTO AttendanceRecord (checkin_time, leave_applications, user_email) VALUES (?, ?, ?)',
                               (checkin_time, leave_reason, user_email))
                conn.commit()
                conn.close()

                return jsonify({'message': 'Leave application submitted successfully'})
        else:
            return jsonify({'message': 'User not authenticated'})
    except Exception as e:
        return jsonify({'message': f'Error: {e}'})



@app.route('/toggle_check', methods=['POST'])
def toggle_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user email from session
        user_email = session.get('user_email', None)

        if user_email:
            # Check if there's an open entry (check-in) for the current day
            cursor.execute('SELECT * FROM AttendanceRecord WHERE date(checkin_time) = date("now") AND checkout_time IS NULL AND user_email = ?',
                           (user_email,))
            existing_checkin = cursor.fetchone()

            if existing_checkin:
                # Perform check-out if there's an open entry
                checkout_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('UPDATE AttendanceRecord SET checkout_time=?, leave_applications=? WHERE id=?',
                               (checkout_time, request.form.get('leave_applications'), existing_checkin['id']))
                checkin_time = existing_checkin['checkin_time']
            else:
                # Perform check-in if no open entry found
                checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('INSERT INTO AttendanceRecord (checkin_time, leave_applications, user_email) VALUES (?, ?, ?)',
                               (checkin_time, request.form.get('leave_applications'), user_email))
                checkout_time = None

            conn.commit()
            conn.close()

            return jsonify({'message': 'Success', 'checkinTime': checkin_time, 'checkoutTime': checkout_time})
        else:
            return jsonify({'message': 'User not authenticated'})
    except Exception as e:
        return jsonify({'message': f'Error: {e}', 'checkinTime': None, 'checkoutTime': None})



if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
