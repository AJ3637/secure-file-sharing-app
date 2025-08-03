from flask import Flask, request, redirect, session, send_file, render_template, flash, url_for
import os, sqlite3, qrcode
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.permanent_session_lifetime = timedelta(minutes=30)

UPLOAD_FOLDER = 'files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= ENCRYPTION KEY =================
if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as f:
        f.write(Fernet.generate_key())
with open("secret.key", "rb") as f:
    key = f.read()
fernet = Fernet(key)

# ================= DB INIT =================
with sqlite3.connect("app.db") as conn:
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS files (username TEXT, filename TEXT, token TEXT, expiry TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS downloads (username TEXT, filename TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS logins (username TEXT, status TEXT, timestamp TEXT)")
    conn.commit()

# ================= HOME =================
@app.route('/')
def home():
    user = session.get('user')

    if not user:
        return render_template("home.html", files=[], session={})

    if user == 'admin':
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT username FROM users WHERE username != 'admin'")
            users = [row[0] for row in c.fetchall()]

            c.execute("SELECT username, filename, token FROM files")
            files = c.fetchall()

            c.execute("SELECT username, filename, timestamp FROM downloads")
            downloads = c.fetchall()

        return render_template("admin.html", users=users, files=files, downloads=downloads, session=session)

    else:
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT filename, token FROM files WHERE username=?", (user,))
            files = c.fetchall()
        return render_template("home.html", files=files, session=session)

# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = generate_password_hash(request.form['password'])
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users VALUES (?, ?)", (uname, pwd))
                conn.commit()
                flash("✅ Registered successfully. Please login.", "success")
                return redirect('/login')
            except:
                flash("⚠️ Username already exists.", "warning")
    return render_template("register.html")

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM users WHERE username=?", (uname,))
            result = c.fetchone()
            if result and check_password_hash(result[0], pwd):
                session.permanent = True
                session['user'] = uname
                c.execute("INSERT INTO logins VALUES (?, ?, ?)", (uname, 'success', datetime.now().isoformat()))
                return redirect('/')
            else:
                c.execute("INSERT INTO logins VALUES (?, ?, ?)", (uname, 'fail', datetime.now().isoformat()))
                flash("❌ Invalid credentials", "danger")
    return render_template("login.html")

# ================= RESET PASSWORD =================
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password != confirm_password:
            flash("⚠️ Passwords do not match.", "warning")
            return redirect('/reset_password')
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            if not c.fetchone():
                flash("❌ User not found.", "danger")
                return redirect('/reset_password')
            hashed = generate_password_hash(new_password)
            c.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
            conn.commit()
            flash("✅ Password updated. Please login.", "success")
            return redirect('/login')
    return render_template("reset_password.html")

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    flash("✅ Logged out.", "info")
    return redirect('/')

# ================= FILE UPLOAD =================
@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/')
    file = request.files.get('file')
    if not file or file.filename == '':
        flash("⚠️ Invalid file.", "warning")
        return redirect('/')
    filename = file.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    with open(path, 'rb') as f:
        encrypted = fernet.encrypt(f.read())
    with open(path, 'wb') as f:
        f.write(encrypted)

    token = Fernet.generate_key().decode()[:16]
    expiry = None
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("INSERT INTO files VALUES (?, ?, ?, ?)", (session['user'], filename, token, expiry))
        conn.commit()

    flash(f"✅ File uploaded! Token: {token}", "success")
    return redirect('/')

# ================= TOKEN DOWNLOAD =================
@app.route('/download', methods=['POST'])
def download():
    token = request.form.get('token')
    return handle_token_download(token)

@app.route('/download/<token>')
def download_by_token(token):
    return handle_token_download(token)

def handle_token_download(token):
    try:
        with sqlite3.connect("app.db") as conn:
            c = conn.cursor()
            c.execute("SELECT filename FROM files WHERE token=?", (token,))
            row = c.fetchone()
            if not row:
                flash("❌ Invalid token", "danger")
                return redirect('/')
            filename = row[0]
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'rb') as f:
                decrypted_data = fernet.decrypt(f.read())
            username = session.get("user", "guest")
            c.execute("INSERT INTO downloads VALUES (?, ?, ?)", (username, filename, datetime.now().isoformat()))
            conn.commit()
            return send_file(BytesIO(decrypted_data), download_name=filename, as_attachment=True)
    except Exception as e:
        return f"<h3>❌ Internal Server Error</h3><pre>{str(e)}</pre>"

# ================= QR CODE =================
@app.route('/qr/<token>')
def generate_qr(token):
    qr_url = url_for('download_by_token', token=token, _external=True)
    img = qrcode.make(qr_url)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# ================= ADMIN DELETE USER =================
@app.route('/admin/delete_user/<username>', methods=['POST'])
def delete_user(username):
    if session.get("user") != "admin":
        return redirect('/')
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        c.execute("DELETE FROM files WHERE username=?", (username,))
        c.execute("DELETE FROM downloads WHERE username=?", (username,))
        c.execute("DELETE FROM logins WHERE username=?", (username,))
        conn.commit()
    flash(f"🗑️ Deleted user: {username}", "info")
    return redirect('/admin')

# ================= ADMIN DELETE FILE =================
@app.route('/admin/delete_file/<username>/<filename>', methods=['POST'])
def delete_file(username, filename):
    if session.get("user") != "admin":
        return redirect('/')
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    with sqlite3.connect("app.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE username=? AND filename=?", (username, filename))
        c.execute("DELETE FROM downloads WHERE filename=?", (filename,))
        conn.commit()
    flash(f"🗑️ Deleted file: {filename}", "info")
    return redirect('/admin')

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)
