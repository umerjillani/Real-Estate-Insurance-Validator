import os
import subprocess
import sys
from flask import Flask, request, jsonify, render_template

from OCR_EC import process_EC
from OCR_Application import process_application
import Scripts.compare_2 as compare_2

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('JSONs', exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload_ec', methods=['POST'])
def upload_ec():
    file = request.files.get('ec_file')
    if not file or file.filename == '':
        return jsonify({'error': 'No EC file uploaded'}), 400
    path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(path)
    result_path = process_EC(path, output_dir='JSONs')
    return jsonify({'json_path': result_path})

@app.route('/upload_application', methods=['POST'])
def upload_application_route():
    file = request.files.get('application_file')
    if not file or file.filename == '':
        return jsonify({'error': 'No application file uploaded'}), 400
    path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(path)
    result = process_application(path, output_dir='JSONs')
    return jsonify({'json_path': result['json_path']})


@app.route('/upload_photos', methods=['POST'])
def upload_photos():
    files = request.files.getlist('photos')
    if not files:
        return jsonify({'error': 'No photo files uploaded'}), 400
    saved_paths = []
    for f in files:
        if f and allowed_file(f.filename):
            p = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
            f.save(p)
            saved_paths.append(p)
    if not saved_paths:
        return jsonify({'error': 'No valid photos uploaded'}), 400
    result = compare_2.analyze_image(saved_paths, ["Validate photographs"])
    return jsonify({'result': result})


@app.route('/process', methods=['POST'])
def process_all():
    """Run all comparison rules using compare.py."""
    try:
        completed = subprocess.run([
            sys.executable,
            'compare.py'
        ], capture_output=True, text=True, check=True) 
        return jsonify({'output': completed.stdout})
    except subprocess.CalledProcessError as e:
        return jsonify({'error': e.stderr or str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)