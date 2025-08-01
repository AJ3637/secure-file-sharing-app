from flask import Flask, request, render_template_string, send_from_directory, session, redirect, url_for
import os
import secrets
import sqlite3
from datetime import datetime
from encryption import generate_key, encrypt_file, decrypt_file

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = "files"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
generate_key()

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("app.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            username TEXT,
            filename TEXT,
            token TEXT,
            PRIMARY KEY (username, filename)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            username TEXT,
            filename TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Secure File Sharing</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f0f4f8;
            padding: 40px;
            text-align: center;
        }
        h1 { color: #2d3748; }
        form {
            margin: 20px auto;
            padding: 20px;
            background: white;
            width: 300px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        input[type="file"], input[type="text"], input[type="password"] {
            width: 90%;
            padding: 10px;
            margin-bottom: 15px;
        }
        input[type="submit"] {
            background-color: #2b6cb0;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
        }
        input[type="submit"]:hover { background-color: #2c5282; }
    </style>
</head>
<body>
    <h1>🔐 Secure File Sharing App</h1>
    {% if 'user' in session %}
        <p>Welcome, {{ session['user'] }} | <a href="/logout">Logout</a></p>
        {% if session['user'] == 'admin' %}
            <p><a href="/admin">⚙️ Admin Dashboard</a></p>
        {% else %}
            <p><a href="/files">📁 View Uploaded Files</a></p>
        {% endif %}

        <form method="POST" enctype="multipart/form-data" action="/upload">
            <h3>Upload & Encrypt</h3>
            <input type="file" name="file" required><br>
            <input type="submit" value="Upload File">
        </form>

        <form method="GET" action="/download">
            <h3>Download & Decrypt</h3>
            <input type="text" name="filename" placeholder="Enter filename.ext" required><br>
            <input type="text" name="token" placeholder="Enter access token" required><br>
            <input type="submit" value="Download File">
        </form>

        <form method="POST" action="/delete">
            <h3>Delete File</h3>
            <input type="text" name="filename" placeholder="Enter filename.ext" required><br>
            <input type="submit" value="Delete File">
        </form>
    {% else %}
        <p><a href="/login">Login</a> or <a href="/register">Register</a> to use the app.</p>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (username,))
            if c.fetchone():
                return "Username already exists."
            c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
            conn.commit()
        return redirect('/login')
    return '''<h2>Register</h2><form method="POST"><input name="username"><input name="password" type="password"><input type="submit"></form>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            if c.fetchone():
                session['user'] = username
                return redirect('/')
        return "❌ Invalid login. Try again"
    return '''<h2>Login</h2><form method="POST"><input name="username"><input name="password" type="password"><input type="submit"></form>'''

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/login')
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    encrypt_file(filepath)
    token = secrets.token_urlsafe(12)
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)", (session['user'], file.filename, token))
        conn.commit()
    return f"✅ File uploaded and encrypted.<br>Your token is: <b>{token}</b><br><a href='/'>Back to Home</a>"

@app.route('/download')
def download():
    filename = request.args.get('filename')
    token = request.args.get('token')
    if 'user' not in session:
        return redirect('/login')
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE filename=? AND token=?", (filename, token))
        if not c.fetchone():
            return "⛔ File does not exist or invalid token."
        decrypt_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        c.execute("INSERT INTO downloads VALUES (?, ?, ?)", (session['user'], filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete', methods=['POST'])
def delete():
    if 'user' not in session:
        return redirect('/login')
    filename = request.form['filename']
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE username=? AND filename=?", (session['user'], filename))
        conn.commit()
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return f"🗑 File '{filename}' deleted.<br><a href='/'>Back to Home</a>"

@app.route('/files')
def list_files():
    if 'user' not in session:
        return redirect('/login')
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("SELECT filename, token FROM files WHERE username=?", (session['user'],))
        files = c.fetchall()
    if not files:
        return "<h2>No uploaded files.</h2><a href='/'>Back to Home</a>"
    output = "<ul>"
    for f in files:
        output += f"<li>{f[0]} — Token: <code>{f[1]}</code></li>"
    output += "</ul><a href='/'>Back to Home</a>"
    return output

@app.route('/admin')
def admin():
    if 'user' not in session or session['user'] != 'admin':
        return "⛔ Access denied."
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        c.execute("SELECT * FROM files")
        files = c.fetchall()
        c.execute("SELECT * FROM downloads")
        logs = c.fetchall()

    user_html = "".join([f"<li>{u[0]}</li>" for u in users])
    file_html = "".join([f"<li>{f[1]} (by {f[0]}) — Token: {f[2]}</li>" for f in files])
    log_html = "".join([f"<li>{l[1]} downloaded by {l[0]} at {l[2]}</li>" for l in logs])

    return f"""
    <h2>⚙️ Admin Dashboard</h2>
    <h3>👥 Users</h3><ul>{user_html}</ul>
    <h3>📁 Files</h3><ul>{file_html}</ul>
    <h3>📊 Download Logs</h3><ul>{log_html}</ul>
    <a href='/'>Back to Home</a>
    """

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
