import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO
from deep_translator import GoogleTranslator
import os
from threading import Lock
import uuid
import logging
import re

app = Flask(__name__)
# logging.basicConfig(filename='logs/app.log', level=logging.DEBUG)
socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()

UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'
ALLOWED_EXTENSIONS = {'txt', 'srt'}
MAX_CHARS = 4000

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
    # 파일 확장자 분리
    name, ext = os.path.splitext(filename)
    # 허용되지 않는 문자를 언더스코어로 대체
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # 파일명과 확장자 다시 결합
    return name + ext

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    files = request.files.getlist('files[]')
    uploaded_files = []
    for file in files:
        if file.filename == '':
            continue
        if file and allowed_file(file.filename):
            filename = sanitize_filename(file.filename)
            file_id = str(uuid.uuid4())
            filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
            file.save(filepath)
            uploaded_files.append({'id': file_id, 'name': filename})
    if not uploaded_files:
        return jsonify({'error': 'No valid files uploaded'}), 400
    return jsonify({'files': uploaded_files}), 200

@app.route('/delete_file/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    try:
        # 업로드 폴더에서 파일 찾기
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith(file_id):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                os.remove(file_path)
                return jsonify({'success': True, 'message': 'File deleted successfully'}), 200
        
        # 파일을 찾지 못한 경우
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/start_translation', methods=['POST'])
def start_translation():
    data = request.json
    files = data.get('files')
    target_language = data.get('target_language')
    
    if not files or not target_language:
        return jsonify({'error': 'Missing files or target language'}), 400
    
    for file in files:
        file_id = file['id']
        filename = file['name']
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        if not os.path.exists(filepath):
            return jsonify({'error': f'File not found: {filename}'}), 404
    
    socketio.start_background_task(target=process_files, files=files, target_language=target_language)
    return jsonify({'message': 'Translation started'}), 200

def split_text(text, max_length):
    parts = []
    current_part = ""
    
    for paragraph in text.split('\n\n'):
        if len(current_part) + len(paragraph) < max_length:
            current_part += paragraph + '\n\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = paragraph + '\n\n'
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

def process_files(files, target_language):
    for file in files:
        file_id = file['id']
        filename = file['name']
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        process_file(filepath, filename, target_language, file_id)

def process_file(filepath, filename, target_language, file_id):
    with thread_lock:
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

                progress = int((i / total_parts) * 40) + 10
                socketio.emit('file_progress', {'file_id': file_id, 'percentage': progress, 'status': f'Saved part {i} of {total_parts}'})
                eventlet.sleep(0)

            socketio.emit('file_progress', {'file_id': file_id, 'percentage': 50, 'status': 'Starting translation...'})
            eventlet.sleep(0)

            translator = GoogleTranslator(source='auto', target=target_language)
            all_translated_text = []

            for i, split_filename in enumerate(split_filenames, 1):
                split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)
                with open(split_filepath, 'r', encoding='utf-8') as f:
                    part_text = f.read()

                translated_text = translator.translate(part_text)
                all_translated_text.append(translated_text)

                progress = int((i / total_parts) * 40) + 50
                socketio.emit('file_progress', {'file_id': file_id, 'percentage': progress, 'status': f'Translated part {i} of {total_parts}'})
                eventlet.sleep(0)

            # Use the original filename with target language suffix
            translated_filename = f'{base_filename}_{target_language}{original_extension}'
            translated_filepath = os.path.join(PROCESSED_FOLDER, translated_filename)

            with open(translated_filepath, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(all_translated_text))

            for filename in split_filenames:
                os.remove(os.path.join(PROCESSED_FOLDER, filename))

            socketio.emit('file_progress', {
                'file_id': file_id,
                'percentage': 100,
                'status': 'Translation Completed!',
                'download_filename': translated_filename
            })

        except Exception as e:
            socketio.emit('file_progress', {'file_id': file_id, 'percentage': 0, 'status': f'Error: {str(e)}'})
        finally:
            os.remove(filepath)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(PROCESSED_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)