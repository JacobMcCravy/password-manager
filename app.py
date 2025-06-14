import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import re
from datetime import timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.permanent_session_lifetime = timedelta(minutes=30)  # Session timeout

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
login_manager.login_message = 'Please log in to access this page.'

class User(UserMixin):
    def __init__(self, id, username, email, pw_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = pw_hash

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        # First check if email column exists
        cur.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'email'
        """)
        has_email = cur.fetchone() is not None
        
        if has_email:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        else:
            cur.execute("SELECT id, username, password_hash, '' as email FROM users WHERE id=%s", (user_id,))
        
        row = cur.fetchone()
    conn.close()
    return User(row['id'], row['username'], row.get('email', ''), row['password_hash']) if row else None

# Password strength validator
def is_strong_password(password):
    """Check if password meets minimum requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, "Password is strong"

# Index route
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        pwd = request.form.get('password', '')
        confirm_pwd = request.form.get('confirm_password', '')
        
        # For backward compatibility - if no email provided, use empty string
        if not email:
            email = ''
        
        # Validation
        if not uname or not pwd:
            flash('Username and password are required.', 'error')
            return render_template('register.html')
        
        if pwd != confirm_pwd:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        # Check password strength
        is_strong, msg = is_strong_password(pwd)
        if not is_strong:
            flash(msg, 'error')
            return render_template('register.html')
        
        # Validate email format if provided
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Please enter a valid email address.', 'error')
            return render_template('register.html')
        
        pw_hash = generate_password_hash(pwd)
        conn = get_db_connection()
        
        try:
            with conn.cursor() as cur:
                # Check if email column exists
                cur.execute("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'users' 
                    AND COLUMN_NAME = 'email'
                """)
                has_email = cur.fetchone() is not None
                
                if has_email:
                    cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s)", 
                               (uname, email, pw_hash))
                else:
                    cur.execute("INSERT INTO users (username, password_hash) VALUES (%s,%s)", 
                               (uname, pw_hash))
                
                conn.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
        except pymysql.err.IntegrityError:
            flash('Username already taken.', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        pwd = request.form.get('password', '')
        
        if not login_input or not pwd:
            flash('Please enter your username/email and password.', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Check if email column exists
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'email'
            """)
            has_email = cur.fetchone() is not None
            
            # Check if input looks like an email
            is_email_input = '@' in login_input
            
            if has_email:
                if is_email_input:
                    # Try to find by email first
                    cur.execute("SELECT * FROM users WHERE email=%s", (login_input,))
                else:
                    # Try username
                    cur.execute("SELECT * FROM users WHERE username=%s", (login_input,))
                
                user = cur.fetchone()
                
                # If not found and has_email, try the opposite
                if not user:
                    if is_email_input:
                        cur.execute("SELECT * FROM users WHERE username=%s", (login_input,))
                    else:
                        cur.execute("SELECT * FROM users WHERE email=%s", (login_input,))
                    user = cur.fetchone()
            else:
                # Old database without email column
                cur.execute("SELECT id, username, password_hash, '' as email FROM users WHERE username=%s", (login_input,))
                user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], pwd):
            login_user(User(user['id'], user['username'], user.get('email', ''), user['password_hash']), 
                      remember=True)
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username/email or password.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    
    # Get selected folder from query parameter
    selected_folder_id = request.args.get('folder', type=int)
    
    with conn.cursor() as cur:
        # Check if folders table exists
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'folders'
        """)
        has_folders = cur.fetchone()['count'] > 0
        
        folders = []
        if has_folders:
            # Get user's folders
            cur.execute("""
                SELECT f.*, COUNT(e.id) as entry_count 
                FROM folders f 
                LEFT JOIN entries e ON f.id = e.folder_id 
                WHERE f.user_id = %s 
                GROUP BY f.id 
                ORDER BY f.name
            """, (current_user.id,))
            folders = cur.fetchall()
            
            # Create default folders if user has none
            if not folders:
                cur.execute("""
                    INSERT INTO folders (user_id, name, color, icon) VALUES
                    (%s, 'Personal', '#10b981', 'user'),
                    (%s, 'Work', '#3b82f6', 'briefcase'),
                    (%s, 'Financial', '#f59e0b', 'credit-card'),
                    (%s, 'Social Media', '#8b5cf6', 'share-2')
                """, (current_user.id, current_user.id, current_user.id, current_user.id))
                conn.commit()
                
                # Fetch again
                cur.execute("""
                    SELECT f.*, COUNT(e.id) as entry_count 
                    FROM folders f 
                    LEFT JOIN entries e ON f.id = e.folder_id 
                    WHERE f.user_id = %s 
                    GROUP BY f.id 
                    ORDER BY f.name
                """, (current_user.id,))
                folders = cur.fetchall()
        
        # Check if created_at column exists
        cur.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'entries' 
            AND COLUMN_NAME = 'created_at'
        """)
        has_created_at = cur.fetchone() is not None
        
        # Build query based on folder selection
        if selected_folder_id is not None:
            if selected_folder_id == 0:
                # Show unorganized entries
                query = "SELECT e.*, NULL as folder_name, NULL as folder_color FROM entries e WHERE e.user_id=%s AND e.folder_id IS NULL"
            else:
                # Show entries from specific folder
                query = """
                    SELECT e.*, f.name as folder_name, f.color as folder_color 
                    FROM entries e 
                    LEFT JOIN folders f ON e.folder_id = f.id 
                    WHERE e.user_id=%s AND e.folder_id=%s
                """
        else:
            # Show all entries
            query = """
                SELECT e.*, f.name as folder_name, f.color as folder_color 
                FROM entries e 
                LEFT JOIN folders f ON e.folder_id = f.id 
                WHERE e.user_id=%s
            """
        
        # Add ordering
        if has_created_at:
            query += " ORDER BY e.created_at DESC"
        else:
            query += " ORDER BY e.id DESC"
        
        # Execute query
        if selected_folder_id is not None and selected_folder_id != 0:
            cur.execute(query, (current_user.id, selected_folder_id))
        else:
            cur.execute(query, (current_user.id,))
        
        entries = cur.fetchall()
        
        # Get count of unorganized entries
        cur.execute("SELECT COUNT(*) as count FROM entries WHERE user_id=%s AND folder_id IS NULL", (current_user.id,))
        unorganized_count = cur.fetchone()['count']
    
    conn.close()
    
    for e in entries:
        try:
            e['password'] = f.decrypt(e['password_encrypted']).decode()
        except:
            e['password'] = "Error decrypting"
    
    return render_template('dashboard.html', 
                         entries=entries, 
                         folders=folders,
                         selected_folder_id=selected_folder_id,
                         unorganized_count=unorganized_count,
                         username=current_user.username)

@app.route('/add', methods=['GET','POST'])
@login_required
def add_entry():
    conn = get_db_connection()
    
    # Get folders for dropdown
    folders = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'folders'
        """)
        if cur.fetchone()['count'] > 0:
            cur.execute("SELECT * FROM folders WHERE user_id=%s ORDER BY name", (current_user.id,))
            folders = cur.fetchall()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        url = request.form.get('url', '').strip()
        notes = request.form.get('notes', '').strip()
        folder_id = request.form.get('folder_id', type=int)
        
        if not title or not username or not password:
            flash('Title, username, and password are required.', 'error')
            return render_template('add_entry.html', folders=folders)
        
        encrypted = f.encrypt(password.encode())
        
        with conn.cursor() as cur:
            # Check if folder_id column exists
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'entries' 
                AND COLUMN_NAME = 'folder_id'
            """)
            has_folder_id = cur.fetchone() is not None
            
            if has_folder_id and folder_id:
                cur.execute(
                    "INSERT INTO entries (user_id,title,username,password_encrypted,url,notes,folder_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (current_user.id, title, username, encrypted, url, notes, folder_id)
                )
            else:
                cur.execute(
                    "INSERT INTO entries (user_id,title,username,password_encrypted,url,notes) VALUES (%s,%s,%s,%s,%s,%s)",
                    (current_user.id, title, username, encrypted, url, notes)
                )
            conn.commit()
        conn.close()
        flash('Entry added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('add_entry.html', folders=folders)

@app.route('/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_entry(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM entries WHERE id=%s AND user_id=%s", (id, current_user.id))
        entry = cur.fetchone()
    
    if not entry:
        flash('Entry not found.', 'error')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        url = request.form.get('url', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not title or not username or not password:
            flash('Title, username, and password are required.', 'error')
            return render_template('edit_entry.html', entry=entry)
        
        encrypted = f.encrypt(password.encode())
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE entries SET title=%s,username=%s,password_encrypted=%s,url=%s,notes=%s WHERE id=%s",
                (title, username, encrypted, url, notes, id)
            )
            conn.commit()
        conn.close()
        flash('Entry updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    try:
        entry['password'] = f.decrypt(entry['password_encrypted']).decode()
    except:
        entry['password'] = ""
    
    conn.close()
    return render_template('edit_entry.html', entry=entry)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_entry(id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        result = cur.execute("DELETE FROM entries WHERE id=%s AND user_id=%s", (id, current_user.id))
        conn.commit()
    conn.close()
    
    if result:
        flash('Entry deleted successfully!', 'success')
    else:
        flash('Entry not found.', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Password generator endpoint
@app.route('/generate-password')
@login_required
def generate_password():
    import secrets
    import string
    
    length = 16
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return {'password': password}

# Create folder endpoint
@app.route('/create-folder', methods=['POST'])
@login_required
def create_folder():
    import random
    
    data = request.get_json()
    folder_name = data.get('name', '').strip()
    
    if not folder_name:
        return {'success': False, 'message': 'Folder name is required'}
    
    # Random color from a nice palette
    colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
    color = random.choice(colors)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO folders (user_id, name, color, icon) 
                VALUES (%s, %s, %s, 'folder')
            """, (current_user.id, folder_name, color))
            conn.commit()
        return {'success': True}
    except pymysql.err.IntegrityError:
        return {'success': False, 'message': 'A folder with this name already exists'}
    except Exception as e:
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)