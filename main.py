from flask import Flask, request, render_template_string, send_from_directory, redirect, url_for
import os
from encryption import generate_key, encrypt_file, decrypt_file
from encryption import generate_key
generate_key()


app = Flask(__name__)
UPLOAD_FOLDER = "files"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure files folder and encryption key exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
generate_key()

# HTML UI
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
        .message {
            margin-top: 20px;
            color: green;
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    encrypt_file(filepath)
    return f"File '{file.filename}' uploaded and encrypted successfully!"

@app.route('/download')
def download():
    filename = request.args.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        decrypt_file(filepath)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        return "File not found"

@app.route('/delete', methods=['POST'])
def delete():
    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return f"File '{filename}' deleted successfully."
    else:
        return "File not found."

@app.route('/files')
def list_files():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    file_links = ''
    for f in files:
        file_links += f"<li>{f} – <a href='/download?filename={f}'>Download</a> | " \
                      f"<form action='/delete' method='POST' style='display:inline;'> " \
                      f"<input type='hidden' name='filename' value='{f}'>" \
                      f"<input type='submit' value='Delete'></form></li>"
    return f"<h2>Uploaded Files</h2><ul>{file_links}</ul><br><a href='/'>Back to Home</a>"




if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

