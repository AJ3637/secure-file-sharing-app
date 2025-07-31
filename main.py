from flask import Flask, request, render_template_string, session, redirect, url_for
from auth import init_db, register_user, validate_user

from flask import Flask, request, render_template_string, send_from_directory
import os
import json
import secrets
from encryption import generate_key, encrypt_file, decrypt_file

# Initialize key and folder
generate_key()
app = Flask(__name__)
UPLOAD_FOLDER = "files"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# HTML Interface
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
        h1 {
            color: #2d3748;
        }
        form {
            margin: 20px auto;
            padding: 20px;
            background: white;
            width: 300px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        input[type="file"], input[type="text"] {
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
        input[type="submit"]:hover {
            background-color: #2c5282;
        }
    </style>
</head>
<body>
    <h1>🔐 Secure File Sharing App</h1>
    <p><a href="/files">📁 View Uploaded Files</a></p>

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
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(html)

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

    with open("user_files.json", "r") as f:
        user_files = json.load(f)

    username = session['user']
    user_data = user_files.get(username, {})

    if filename not in user_data:
        return "❌ File not found or not owned by you."

    if user_data[filename] != token_input:
        return "🔐 Invalid token."

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        decrypt_file(filepath)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        return "❌ Encrypted file missing."


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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if register_user(uname, pwd):
            return redirect('/login')
        else:
            return "❌ Username already exists. <a href='/register'>Try again</a>"
    return '''
    <h2>Register</h2>
    <form method="POST">
        Username: <input name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Register">
    </form>
    '''

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
    return '''
    <h2>Login</h2>
    <form method="POST">
        Username: <input name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    '''

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    init_db()  # Create user table if not exists
    app.run(host='0.0.0.0', port=port)
