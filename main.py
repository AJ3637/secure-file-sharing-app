from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
import os
from encryption import encrypt_file, decrypt_file
import json
import secrets

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'files'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# HTML Interface
html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Secure File Sharing</title>
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
</body>
</html>
'''

@app.route('/')
def home():
    return html

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        encrypt_file(filepath)
        os.remove(filepath)  # remove original

        # Generate secure random token
        token = secrets.token_urlsafe(8)

        # Save token
        if os.path.exists("tokens.json"):
            with open("tokens.json", "r") as f:
                tokens = json.load(f)
        else:
            tokens = {}

        tokens[filename] = token

        with open("tokens.json", "w") as f:
            json.dump(tokens, f)

        return f"✅ File '{filename}' uploaded and encrypted.<br><b>Your token: {token}</b><br>Share this token securely with the downloader.<br><a href='/'>Back to Home</a>"

@app.route('/download')
def download():
    filename = request.args.get('filename')
    token_input = request.args.get('token')

    # Load token list
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
    else:
        tokens = {}

    if filename not in tokens:
        return "❌ File not found or token not set."

    if tokens[filename] != token_input:
        return "🔐 Invalid token. Access denied."

    encrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    decrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"decrypted_{filename}")
    decrypt_file(encrypted_file_path, decrypted_file_path)

    return send_file(decrypted_file_path, as_attachment=True)

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

        return f"🗑️ File '{filename}' deleted successfully.<br><a href='/'>Back</a>"
    else:
        return "❌ File not found."

@app.route('/files')
def list_files():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    files = [f for f in files if f != '.gitkeep']

    if not files:
        return "<h2>No uploaded files.</h2><a href='/'>Back to Home</a>"

    file_links = ''
    for f in files:
        file_links += f"<li>{f} – <a href='/download?filename={f}'>Download</a> | " \
                      f"<form action='/delete' method='POST' style='display:inline;'> " \
                      f"<input type='hidden' name='filename' value='{f}'>" \
                      f"<input type='submit' value='Delete'></form></li>"
    return f"<h2>Uploaded Files</h2><ul>{file_links}</ul><br><a href='/'>Back to Home</a>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
