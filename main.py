from flask import Flask, request, redirect, session, send_from_directory, render_template_string, send_file
import os
import sqlite3
from cryptography.fernet import Fernet
from datetime import datetime
import qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Generate encryption key if not exists
if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as key_file:
        key_file.write(Fernet.generate_key())
with open("secret.key", "rb") as key_file:
    key = key_file.read()

fernet = Fernet(key)

# DB Init
def init_db():
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS files (username TEXT, filename TEXT, token TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS downloads (username TEXT, filename TEXT, timestamp TEXT)")
        conn.commit()

init_db()

# Home HTML with QR
home_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Secure File Sharing</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
  <div class="container-fluid">
    <a class="navbar-brand" href="/">🔐 SecureShare</a>
    <div class="d-flex">
      {% if 'user' in session %}
        <span class="navbar-text text-white me-3">Welcome, {{ session['user'] }}</span>
        <a href="/logout" class="btn btn-outline-light">Logout</a>
      {% else %}
        <a href="/login" class="btn btn-outline-light me-2">Login</a>
        <a href="/register" class="btn btn-outline-light">Register</a>
      {% endif %}
    </div>
  </div>
</nav>

<div class="container mt-5">
  {% if 'user' in session %}
    <h2 class="mb-4">📁 Secure File Sharing</h2>

    <div class="row">
      <div class="col-md-6">
        <div class="card p-3 mb-3 shadow-sm">
          <h5>Upload File</h5>
          <form method="POST" enctype="multipart/form-data" action="/upload">
              <input type="file" name="file" class="form-control my-2" required>
              <button type="submit" class="btn btn-primary w-100">Upload & Encrypt</button>
          </form>
        </div>
      </div>

      <div class="col-md-6">
        <div class="card p-3 mb-3 shadow-sm">
          <h5>Download File</h5>
          <form method="POST" action="/download">
              <input type="text" name="token" class="form-control my-2" placeholder="Enter Token" required>
              <button type="submit" class="btn btn-success w-100">Download & Decrypt</button>
          </form>
        </div>
      </div>
    </div>

    <div class="card p-3 shadow-sm">
      <h5>Uploaded Files (Your Account)</h5>
      <ul class="list-group">
        {% for f in files %}
          <li class="list-group-item d-flex justify-content-between align-items-center">
            {{ f[1] }} — Token: <code>{{ f[2] }}</code>
            <div>
              <a href="/qr/{{ f[2] }}" target="_blank" class="btn btn-sm btn-outline-secondary">📱 QR</a>
              <form method="POST" action="/delete_file" class="d-inline">
                <input type="hidden" name="filename" value="{{ f[1] }}">
                <button class="btn btn-sm btn-danger">Delete</button>
              </form>
            </div>
          </li>
        {% endfor %}
      </ul>
    </div>

    {% if session['user'] == 'admin' %}
    <div class="mt-4 text-end">
      <a href="/admin" class="btn btn-dark">🛠 Admin Dashboard</a>
    </div>
    {% endif %}

  {% else %}
    <div class="alert alert-info mt-5">🔐 Please <a href="/login">login</a> or <a href="/register">register</a> to use the app.</div>
  {% endif %}
</div>
</body>
</html>
'''

@app.route('/')
def home():
    if 'user' in session:
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM files WHERE username=?", (session['user'],))
            files = c.fetchall()
        return render_template_string(home_html, files=files)
    return render_template_string(home_html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users VALUES (?, ?)", (uname, pwd))
                conn.commit()
                return redirect('/login')
            except:
                return "Username already exists."
    return '''<form method="POST">Username: <input name="username"><br>Password: <input name="password"><br><input type="submit" value="Register"></form>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (uname, pwd))
            if c.fetchone():
                session['user'] = uname
                return redirect('/')
            return "❌ Invalid login. Try again"
    return '''<form method="POST">Username: <input name="username"><br>Password: <input name="password"><br><input type="submit" value="Login"></form>'''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/')
    file = request.files['file']
    filename = file.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    with open(path, 'rb') as f:
        encrypted = fernet.encrypt(f.read())
    with open(path, 'wb') as f:
        f.write(encrypted)
    token = Fernet.generate_key().decode()[:16]
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files VALUES (?, ?, ?)", (session['user'], filename, token))
        conn.commit()
    return f"<div class='alert alert-success'>✅ File uploaded!<br>Token: <b>{token}</b><br><a href='/'>Back to Home</a></div>"

@app.route('/download', methods=['POST'])
def download():
    token = request.form['token']
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE token=?", (token,))
        file = c.fetchone()
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file[1])
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                decrypted = fernet.decrypt(f.read())
            with open(filepath, 'wb') as f:
                f.write(decrypted)
            with sqlite3.connect("app.db") as conn:
                c = conn.cursor()
                c.execute("INSERT INTO downloads VALUES (?, ?, ?)", (session['user'], file[1], datetime.now().isoformat()))
                conn.commit()
            return send_from_directory(UPLOAD_FOLDER, file[1], as_attachment=True)
    return "<div class='alert alert-danger'>❌ Invalid token or file not found.<br><a href='/'>Back</a></div>"

@app.route('/delete_file', methods=['POST'])
def delete_file():
    if 'user' not in session:
        return redirect('/')
    filename = request.form['filename']
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE filename=? AND username=?", (filename, session['user']))
        conn.commit()
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect('/')

@app.route('/qr/<token>')
def generate_qr(token):
    url = request.url_root.rstrip('/') + "/download?token=" + token
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/admin')
def admin():
    if session.get('user') != 'admin':
        return "⛔ Access denied."
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        c.execute("SELECT * FROM files")
        files = c.fetchall()
        c.execute("SELECT * FROM downloads")
        logs = c.fetchall()
    return f"""
    <h2>🛠 Admin Dashboard</h2>
    <h4>👥 Registered Users</h4>
    <ul>{''.join([f"<li>{u[0]} <form method='POST' action='/admin/delete_user' style='display:inline;'><input type='hidden' name='username' value='{u[0]}'><button>Delete</button></form></li>" for u in users])}</ul>
    <h4>📁 All Uploaded Files</h4>
    <ul>{''.join([f"<li>{f[1]} (by {f[0]}) — Token: {f[2]} <form method='POST' action='/admin/delete_file' style='display:inline;'><input type='hidden' name='filename' value='{f[1]}'><button>Delete</button></form></li>" for f in files])}</ul>
    <h4>📊 Download Logs</h4>
    <ul>{''.join([f"<li>{l[1]} downloaded by {l[0]} at {l[2]}</li>" for l in logs])}</ul>
    <br><a href='/'>Back to Home</a>
    """

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if session.get('user') != 'admin':
        return "⛔ Access denied."
    uname = request.form['username']
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (uname,))
        c.execute("DELETE FROM files WHERE username=?", (uname,))
        c.execute("DELETE FROM downloads WHERE username=?", (uname,))
        conn.commit()
    return redirect('/admin')

@app.route('/admin/delete_file', methods=['POST'])
def admin_delete_file():
    if session.get('user') != 'admin':
        return "⛔ Access denied."
    fname = request.form['filename']
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE filename=?", (fname,))
        c.execute("DELETE FROM downloads WHERE filename=?", (fname,))
        conn.commit()
    path = os.path.join(UPLOAD_FOLDER, fname)
    if os.path.exists(path):
        os.remove(path)
    return redirect('/admin')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
