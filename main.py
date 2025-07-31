from flask import Flask, request, render_template_string, send_from_directory, session, redirect, url_for
import os
import json
import secrets
from datetime import datetime
from encryption import generate_key, encrypt_file, decrypt_file
from auth import init_db, register_user, validate_user

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = "files"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
generate_key()
init_db()

# Ensure download log exists
if not os.path.exists("downloads.json"):
    with open("downloads.json", "w") as f:
        json.dump([], f)

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

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user'] != 'admin':
        return "⛔ Access denied."

    logs = []
    if os.path.exists("downloads.json"):
        with open("downloads.json", "r") as f:
            logs = json.load(f)

    users = []
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            users = list(json.load(f).keys())

    all_files = []
    if os.path.exists("user_files.json"):
        with open("user_files.json", "r") as f:
            all_files_data = json.load(f)
            for user, files in all_files_data.items():
                for filename, token in files.items():
                    all_files.append({"user": user, "file": filename, "token": token})

    # Generate HTML content
    file_html = ""
    for f in all_files:
        file_html += f"""
        <li>
            <b>{f['file']}</b> (by <i>{f['user']}</i>) — Token: <code>{f['token']}</code><br>
            <a href="/download?filename={f['file']}&token={f['token']}">🔽 Download</a> |
            <form action="/delete" method="POST" style="display:inline;">
                <input type="hidden" name="filename" value="{f['file']}">
                <input type="submit" value="🗑 Delete">
            </form>
        </li>
        """

    user_html = "".join([f"<li>👤 {u}</li>" for u in users])
    log_html = "".join([f"<li>📄 <b>{l['filename']}</b> downloaded by <i>{l['user']}</i> at {l['timestamp']}</li>" for l in logs])

    return f"""
    <h2>⚙️ Admin Dashboard</h2>
    <h3>📁 All Uploaded Files</h3><ul>{file_html}</ul>
    <h3>👥 Registered Users</h3><ul>{user_html}</ul>
    <h3>📊 Download Logs</h3><ul>{log_html}</ul>
    <br><a href='/'>🏠 Back to Home</a>
    """

# Keep all your existing routes unchanged here...


@app.route('/')
def home():
    return render_template_string(html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if register_user(uname, pwd):
            return redirect('/login')
        else:
            return "❌ Username already exists. <a href='/register'>Try again</a>"
    return '''<h2>Register</h2>
    <form method="POST">
        Username: <input name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Register">
    </form>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if validate_user(uname, pwd):
            session['user'] = uname
            return redirect('/')
        else:
            return "❌ Invalid login. <a href='/login'>Try again</a>"
    return '''<h2>Login</h2>
    <form method="POST">
        Username: <input name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>'''

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/login')

    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    encrypt_file(filepath)

    # Load user_files
    user_files = {}
    if os.path.exists("user_files.json"):
        with open("user_files.json", "r") as f:
            user_files = json.load(f)

    username = session['user']
    token = secrets.token_urlsafe(8)

    if username not in user_files:
        user_files[username] = {}
    user_files[username][filename] = token

    with open("user_files.json", "w") as f:
        json.dump(user_files, f)

    return f"✅ File '{filename}' uploaded and encrypted.<br><b>Your token:</b> {token}<br><a href='/'>Back to Home</a>"

@app.route('/download')
def download():
    if 'user' not in session:
        return redirect('/login')

    filename = request.args.get('filename')
    token_input = request.args.get('token')

    if not filename or not token_input:
        return "❌ Missing filename or token."

    # Load user_files.json
    with open("user_files.json", "r") as f:
        user_files = json.load(f)

    # 🔍 Search through all users for this file + token
    for user_data in user_files.values():
        if filename in user_data and user_data[filename] == token_input:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                decrypt_file(filepath)
                return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
            else:
                return "❌ Encrypted file missing."

    return "❌ File not found or token is invalid."


@app.route('/delete', methods=['POST'])
def delete():
    if 'user' not in session:
        return redirect('/login')

    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    with open("user_files.json", "r") as f:
        user_files = json.load(f)

    username = session['user']
    if filename in user_files.get(username, {}):
        if os.path.exists(filepath):
            os.remove(filepath)
        del user_files[username][filename]
        with open("user_files.json", "w") as f:
            json.dump(user_files, f)
        return f"🗑️ File '{filename}' deleted.<br><a href='/'>Back</a>"
    else:
        return "❌ File not found or not yours."

@app.route('/files')
def list_files():
    if 'user' not in session:
        return redirect('/login')

    with open("user_files.json", "r") as f:
        user_files = json.load(f)

    username = session['user']
    user_data = user_files.get(username, {})

    if not user_data:
        return "<h2>No uploaded files.</h2><a href='/'>Back</a>"

    file_links = ''
    for f, token in user_data.items():
        file_links += f"<li><b>{f}</b><br>🔑 Token: <code>{token}</code><br>" \
                      f"<a href='/download?filename={f}'>Download</a> | " \
                      f"<form action='/delete' method='POST' style='display:inline;'> " \
                      f"<input type='hidden' name='filename' value='{f}'>" \
                      f"<input type='submit' value='Delete'></form></li><br>"

    return f"<h2>Your Uploaded Files</h2><ul>{file_links}</ul><br><a href='/'>Back</a>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
