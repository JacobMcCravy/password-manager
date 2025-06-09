import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Encryption setup
f = Fernet(os.getenv('ENCRYPTION_KEY').encode())

# Database helper
def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, pw_hash):
        self.id = id
        self.username = username
        self.password_hash = pw_hash

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
    conn.close()
    return User(row['id'], row['username'], row['password_hash']) if row else None

# Index route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        uname, pwd = request.form['username'], request.form['password']
        pw_hash = generate_password_hash(pwd)
        conn = get_db_connection()
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO users (username,password_hash) VALUES (%s,%s)", (uname,pw_hash))
                conn.commit()
                flash('Registered! Please log in.')
                return redirect(url_for('login'))
            except pymysql.err.IntegrityError:
                flash('Username taken.')
        conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname, pwd = request.form['username'], request.form['password']
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s", (uname,))
            user = cur.fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], pwd):
            login_user(User(user['id'], user['username'], user['password_hash']))
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM entries WHERE user_id=%s", (current_user.id,))
        entries = cur.fetchall()
    conn.close()
    for e in entries:
        e['password'] = f.decrypt(e['password_encrypted']).decode()
    return render_template('dashboard.html', entries=entries)

@app.route('/add', methods=['GET','POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        data = {k: request.form[k] for k in ('title','username','password','url','notes')}
        encrypted = f.encrypt(data['password'].encode())
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO entries (user_id,title,username,password_encrypted,url,notes) VALUES (%s,%s,%s,%s,%s,%s)",
                (current_user.id, data['title'], data['username'], encrypted, data['url'], data['notes'])
            )
            conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    return render_template('add_entry.html')

@app.route('/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_entry(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM entries WHERE id=%s AND user_id=%s", (id,current_user.id))
        entry = cur.fetchone()
    if not entry:
        flash('Entry not found.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = {k: request.form[k] for k in ('title','username','password','url','notes')}
        encrypted = f.encrypt(data['password'].encode())
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE entries SET title=%s,username=%s,password_encrypted=%s,url=%s,notes=%s WHERE id=%s",
                (data['title'], data['username'], encrypted, data['url'], data['notes'], id)
            )
            conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    entry['password'] = f.decrypt(entry['password_encrypted']).decode()
    conn.close()
    return render_template('edit_entry.html', entry=entry)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_entry(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM entries WHERE id=%s AND user_id=%s", (id,current_user.id))
        conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

# Updated logout to POST
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()
