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
    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Encrypt the uploaded file (overwrite same file)
    encrypt_file(filepath)

    # Generate and save a random token
    token = secrets.token_urlsafe(8)
    tokens = {}
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
    tokens[filename] = token
    with open("tokens.json", "w") as f:
        json.dump(tokens, f)

    return f"✅ File '{filename}' uploaded and encrypted.<br><b>Your token:</b> {token}<br>Share this token with the downloader.<br><a href='/'>Back to Home</a>"

@app.route('/download')
def download():
    filename = request.args.get('filename')
    token_input = request.args.get('token')

    # Load saved tokens
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
    else:
        return "❌ No tokens found."

    if filename not in tokens:
        return "❌ File not found or token not set."

    if tokens[filename] != token_input:
        return "🔐 Invalid token. Access denied."

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        decrypt_file(filepath)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        return "❌ Encrypted file not found."

@app.route('/delete', methods=['POST'])
def delete():
    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)

        # Remove token
        if os.path.exists("tokens.json"):
            with open("tokens.json", "r") as f:
                tokens = json.load(f)
            tokens.pop(filename, None)
            with open("tokens.json", "w") as f:
                json.dump(tokens, f)

        return f"🗑️ File '{filename}' deleted.<br><a href='/'>Back</a>"
    else:
        return "❌ File not found."

@app.route('/files')
def list_files():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    files = [f for f in files if not f.startswith('.')]

    # Load tokens
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
    else:
        tokens = {}

    if not files:
        return "<h2>No uploaded files.</h2><a href='/'>Back to Home</a>"

    file_links = ''
    for f in files:
        token_display = tokens.get(f, "🔒 Token not found")
        file_links += f"<li><b>{f}</b><br>🔑 Token: <code>{token_display}</code><br>" \
                      f"<a href='/download?filename={f}'>Download</a> | " \
                      f"<form action='/delete' method='POST' style='display:inline;'> " \
                      f"<input type='hidden' name='filename' value='{f}'>" \
                      f"<input type='submit' value='Delete'></form></li><br>"

    return f"<h2>Uploaded Files</h2><ul>{file_links}</ul><br><a href='/'>Back to Home</a>"


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
