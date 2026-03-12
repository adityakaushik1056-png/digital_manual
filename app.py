import sqlite3, qrcode
from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)
app.secret_key = "industrial_secret"

DB_FILE = "factory_app.db"

# --- Database Connection ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # dictionary-like access
    return conn

# --- Initialize DB ---
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # Admins table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # Machines table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS machines (
        m_id TEXT PRIMARY KEY,
        m_name TEXT NOT NULL,
        manual TEXT,
        ppt TEXT,
        image TEXT,
        video TEXT
    )
    """)

    # --- Insert default admin if none exists ---
    cursor.execute("SELECT COUNT(*) FROM admins")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ("admin", "admin123"))

    conn.commit()
    conn.close()


@app.route('/')
def index():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    uname, pword, role = request.form['username'], request.form['password'], request.form['role']
    conn = get_db()
    cursor = conn.cursor()
    table = "admins" if role == "admin" else "users"

    cursor.execute(f"SELECT * FROM {table} WHERE username=? AND password=?", (uname, pword))
    account = cursor.fetchone()
    conn.close()

    if account:
        session['username'], session['role'] = uname, role
        return redirect(url_for('admin_dash' if role == 'admin' else 'user_home'))
    return "Invalid Credentials! <a href='/'>Try Again</a>"


@app.route('/admin/dashboard')
def admin_dash():
    if session.get('role') != 'admin':
        return redirect('/')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines")
    machines = cursor.fetchall()
    conn.close()
    return render_template('admin_dash.html', machines=machines)


@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if session.get('role') == 'admin':
        uname = request.form['username']
        pword = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (uname, pword))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dash'))
    return redirect(url_for('index'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') == 'admin':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('all_data'))
    return redirect(url_for('index'))



@app.route('/admin/add_machine', methods=['POST'])
def add_machine():
    if session.get('role') != 'admin':
        return redirect('/')

    m_id = request.form.get('m_id')
    m_name = request.form.get('m_name')

    manual = request.files.get('manual')
    ppt = request.files.get('ppt')
    image = request.files.get('image')
    video = request.files.get('video')

    # Ensure upload directories exist
    upload_dir = os.path.join(app.root_path, 'static/uploads')
    qr_dir = os.path.join(app.root_path, 'static/qrcodes')
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(qr_dir, exist_ok=True)

    # Save files only if provided
    manual_filename = None
    ppt_filename = None
    image_filename = None
    video_filename = None

    if manual and manual.filename.strip():
        manual_filename = manual.filename
        manual.save(os.path.join(upload_dir, manual_filename))

    if ppt and ppt.filename.strip():
        ppt_filename = ppt.filename
        ppt.save(os.path.join(upload_dir, ppt_filename))

    if image and image.filename.strip():
        image_filename = image.filename
        image.save(os.path.join(upload_dir, image_filename))

    if video and video.filename.strip():
        video_filename = video.filename
        video.save(os.path.join(upload_dir, video_filename))

    # Insert into DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO machines (m_id, m_name, manual, ppt, image, video) VALUES (?, ?, ?, ?, ?, ?)",
            (m_id, m_name, manual_filename, ppt_filename, image_filename, video_filename)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Machine ID already exists! <a href='/admin/dashboard'>Go Back</a>"
    conn.close()

    # Generate QR Code
    filename_safe = f"{m_id.replace(' ', '_')}.png"
    qr_path = os.path.join(qr_dir, filename_safe)

    # Dynamic domain (works locally and on Render)
    machine_url = request.host_url.rstrip('/') + url_for('machine_view', m_id=m_id)

    qr_img = qrcode.make(machine_url)
    qr_img.save(qr_path)

    # Redirect back to admin dashboard
    return redirect(url_for('admin_dash'))

@app.route('/admin/delete_machine/<m_id>', methods=['POST'])
def delete_machine(m_id):
    if session.get('role') == 'admin':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM machines WHERE m_id=?", (m_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dash'))
    return redirect(url_for('index'))



@app.route('/user/home')
def user_home():
    if 'username' in session and session.get('role') == 'user':
        return render_template('user_home.html', user=session['username'])
    return redirect(url_for('index'))


@app.route('/machine/<m_id>')
def machine_view(m_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM machines WHERE m_id=?", (m_id,))
    m = cursor.fetchone()
    conn.close()
    if not m:
        return "Machine not found!"
    return render_template('machine_view.html', m=m)


@app.route('/admin/all_data')
def all_data():
    if session.get('role') != 'admin':
        return redirect('/')
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM admins")
    admins = cursor.fetchall()

    cursor.execute("SELECT * FROM machines")
    machines = cursor.fetchall()

    conn.close()
    return render_template('all_data.html', users=users, admins=admins, machines=machines)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)





