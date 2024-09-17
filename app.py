import eventlet
eventlet.monkey_patch()
import os
import re
import uuid
import logging
import unicodedata
from threading import Lock
from flask import Flask, render_template, request, send_file, jsonify, abort
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
from flask_socketio import SocketIO
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
logging.basicConfig(filename='logs/app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s')

app.config['SESSION_COOKIE_SECURE'] = False  # Use only in development environment
app.config['SESSION_COOKIE_HTTPONLY'] = True

socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()

UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
PROCESSED_FOLDER = app.config['PROCESSED_FOLDER']
ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
MAX_CHARS = app.config['MAX_CHARS']

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

LANGUAGES = {
    'ko': 'Korean',
    'en': 'English',
    'ja': 'Japanese',
    'zh-cn': 'Chinese (Simplified)',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish'
}

def sanitize_filename(filename):
    # Separate file extension
    name, ext = os.path.splitext(filename)

    # Unicode normalization (e.g., handling accent characters)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')

    # Replace spaces with underscores
    name = re.sub(r'\s+', '_', name)

    # Remove disallowed characters (including those problematic for Windows, macOS, Linux)
    name = re.sub(r'[\\/*?:"<>|\'`~!@#$%^&()+={}[\],;]', "", name)

    # Remove consecutive underscores
    name = re.sub(r'_+', '_', name)

    # Remove leading and trailing underscores
    name = name.strip('_')

    # Set default name if empty or all characters were removed
    if not name:
        name = "unnamed_file"

    # Recombine filename and extension
    return name + ext

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    allowed_extensions = ','.join(['.' + ext for ext in app.config['ALLOWED_EXTENSIONS']])
    return render_template('index.html', languages=LANGUAGES, allowed_extensions=allowed_extensions)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No file was sent.'}), 400
    files = request.files.getlist('files[]')
    uploaded_files = []
    for file in files:
        if file.filename == '':
            continue
        if file and allowed_file(file.filename):
            filename = sanitize_filename(file.filename)
            file_id = str(uuid.uuid4())
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
            file.save(filepath)
            uploaded_files.append({'id': file_id, 'name': filename})
        else:
            return jsonify({'error': f'Disallowed file type: {file.filename}'}), 400
    if not uploaded_files:
        return jsonify({'error': 'No valid files were uploaded.'}), 400
    return jsonify({'files': uploaded_files}), 200

@app.route('/delete_file/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    try:
        deleted_files = []
        for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
            for filename in os.listdir(folder):
                if filename.startswith(file_id) or f"_{file_id}_" in filename:
                    file_path = os.path.join(folder, filename)
                    os.remove(file_path)
                    deleted_files.append(filename)

        if deleted_files:
            logging.info(f"Deleted files: {', '.join(deleted_files)}")
            return jsonify({'success': True, 'message': f'Files successfully deleted: {", ".join(deleted_files)}'}), 200
        else:
            # If no files were found, log all files for debugging
            for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
                logging.info(f"Files in {folder}: {', '.join(os.listdir(folder))}")
            return jsonify({'success': False, 'error': 'File not found.'}), 404
    except Exception as e:
        logging.error(f"File deletion error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/start_translation', methods=['POST'])
def start_translation():
    data = request.json
    files = data.get('files')
    target_language = data.get('target_language')

    if not files or not target_language:
        return jsonify({'error': 'Files or target language missing.'}), 400

    # Check if the language is supported
    if target_language not in LANGUAGES:
        return jsonify({'error': 'Unsupported target language.'}), 400

    for file in files:
        file_id = file['id']
        filename = file['name']
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        if not os.path.exists(filepath):
            return jsonify({'error': f'File not found: {filename}'}), 404

    for file in files:
        file_id = file['id']
        filename = file['name']
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        socketio.start_background_task(target=process_file, filepath=filepath, filename=filename, target_language=target_language, file_id=file_id)

    return jsonify({'message': 'Translation started.'}), 200

def split_text(text, max_length):
    parts = []
    current_part = ""

    for paragraph in text.split('\n\n'):
        if len(current_part) + len(paragraph) + 2 < max_length:
            current_part += paragraph + '\n\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = paragraph + '\n\n'

    if current_part:
        parts.append(current_part.strip())

    return parts

def process_file(filepath, filename, target_language, file_id):
    split_filenames = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        text_parts = split_text(text, MAX_CHARS)
        total_parts = len(text_parts)

        socketio.emit('file_progress', {'file_id': file_id, 'percentage': 10, 'status': 'Splitting file...'})
        eventlet.sleep(0)

        base_filename = os.path.splitext(filename)[0]
        original_extension = os.path.splitext(filename)[1]
        split_filenames = []

        for i, part in enumerate(text_parts, 1):
            split_filename = f'{base_filename}_part{i}.txt'
            split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)

            with open(split_filepath, 'w', encoding='utf-8') as f:
                f.write(part)

            split_filenames.append(split_filename)

            progress = int((i / total_parts) * 30) + 10  # 10% ~ 40%
            socketio.emit('file_progress', {'file_id': file_id, 'percentage': progress, 'status': f'Saving part {i}/{total_parts}...'})
            eventlet.sleep(0)

        socketio.emit('file_progress', {'file_id': file_id, 'percentage': 40, 'status': 'Starting translation...'})
        eventlet.sleep(0)

        translator = GoogleTranslator(source='auto', target=target_language)
        all_translated_text = []

        for i, split_filename in enumerate(split_filenames, 1):
            split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)
            with open(split_filepath, 'r', encoding='utf-8') as f:
                part_text = f.read()

            translated_text = translator.translate(part_text)
            all_translated_text.append(translated_text)

            progress = int((i / total_parts) * 50) + 40  # 40% ~ 90%
            socketio.emit('file_progress', {'file_id': file_id, 'percentage': progress, 'status': f'Translating part {i}/{total_parts}...'})
            eventlet.sleep(0)

        # Include file_id in the filename here
        translated_filename = sanitize_filename(f'{base_filename}_{file_id}_{target_language}{original_extension}')
        translated_filepath = os.path.join(PROCESSED_FOLDER, translated_filename)

        with open(translated_filepath, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(all_translated_text))

        logging.info(f"Translated file saved: {translated_filepath}")

        socketio.emit('file_progress', {
            'file_id': file_id,
            'percentage': 100,
            'status': 'Translation complete!',
            'download_filename': translated_filename
        })

    except Exception as e:
        logging.error(f"File processing error ({filename}): {e}")
        socketio.emit('file_progress', {'file_id': file_id, 'percentage': 0, 'status': f'Error occurred: {str(e)}'})
    finally:
        # Delete split files
        for split_filename in split_filenames:
            try:
                os.remove(os.path.join(PROCESSED_FOLDER, split_filename))
            except Exception as e:
                logging.error(f"Error deleting split file ({split_filename}): {e}")

@app.route('/download/<filename>')
def download_file(filename):
    try:
        secure_name = secure_filename(filename)
        file_path = os.path.join(PROCESSED_FOLDER, secure_name)

        logging.info(f"Requested file path: {file_path}")

        # Additional check to prevent path manipulation
        if not os.path.abspath(file_path).startswith(os.path.abspath(PROCESSED_FOLDER)) or '..' in filename:
            logging.warning(f"Attempted invalid file path access: {file_path}")
            abort(404)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            logging.info(f"Starting file download: {file_path}")
            return send_file(file_path, as_attachment=True, download_name=secure_name)
        else:
            logging.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found.'}), 404
    except Exception as e:
        logging.error(f"Download error: {e}")
        return jsonify({'error': 'An error occurred while downloading the file.'}), 500

if __name__ == "__main__":
    socketio.run(app, debug=True)
