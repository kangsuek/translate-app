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

# Flask 애플리케이션 초기화 및 설정
app = Flask(__name__)
app.config.from_object(Config)
logging.basicConfig(filename='logs/app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s')

app.config['SESSION_COOKIE_SECURE'] = False # 개발 환경에서만 사용하는 세션 쿠키 설정
app.config['SESSION_COOKIE_HTTPONLY'] = True

# SocketIO 초기화
socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()

# 설정 값 불러오기
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
PROCESSED_FOLDER = app.config['PROCESSED_FOLDER']
ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
MAX_CHARS = app.config['MAX_CHARS']

# 필요한 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# 지원하는 언어 목록
LANGUAGES = {
    'ko': 'Korean',
    'en': 'English',
    'ja': 'Japanese',
    'zh-CN': '中文(简体)',
    'zh-TW': '中文(繁體)',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish'
}

def sanitize_filename(filename):
    # 파일 이름에서 확장자 분리
    name, ext = os.path.splitext(filename)

    # 유니코드 정규화 (예: 악센트 문자 처리)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')

    # 공백을 언더스코어로 대체
    name = re.sub(r'\s+', '_', name)

    # 허용되지 않는 문자 제거 (Windows, macOS, Linux에서 문제가 될 수 있는 문자 포함)
    name = re.sub(r'[\\/*?:"<>|\'`~!@#$%^&()+={}[\],;]', "", name)

    # 연속된 언더스코어 제거
    name = re.sub(r'_+', '_', name)

    # 앞뒤 언더스코어 제거
    name = name.strip('_')

    # 이름이 비어있거나 모든 문자가 제거된 경우 기본 이름 설정
    if not name:
        name = "unnamed_file"

    # 파일 이름과 확장자 재결합
    return name + ext

def allowed_file(filename):
    # 허용된 파일 확장자인지 확인
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    # 허용된 파일 확장자 목록 생성
    allowed_extensions = ','.join(['.' + ext for ext in app.config['ALLOWED_EXTENSIONS']])
    return render_template('index.html', languages=LANGUAGES, allowed_extensions=allowed_extensions)

@app.route('/upload', methods=['POST'])
def upload_file():
    # 파일 업로드 처리
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
    # 파일 삭제 처리
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
            # 파일을 찾지 못한 경우 디버깅을 위해 모든 파일 로깅
            for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
                logging.info(f"Files in {folder}: {', '.join(os.listdir(folder))}")
            return jsonify({'success': False, 'error': 'File not found.'}), 404
    except Exception as e:
        logging.error(f"File deletion error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/start_translation', methods=['POST'])
def start_translation():
    # 번역 시작 처리
    data = request.json
    files = data.get('files', [])
    target_language = data.get('target_language')

    if not files or not target_language:
        return jsonify({'error': 'Files or target language missing.'}), 400

    # 지원하는 언어인지 확인
    if target_language not in LANGUAGES:
        return jsonify({'error': f'Unsupported language. Please choose one of the supported languages: {", ".join(LANGUAGES.keys())}'}), 400

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
    # 텍스트를 최대 길이에 맞춰 분할
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
    # 파일 처리 및 번역
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

        # 파일 이름에 file_id 포함
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
        # 분할된 파일 삭제
        for split_filename in split_filenames:
            try:
                os.remove(os.path.join(PROCESSED_FOLDER, split_filename))
            except Exception as e:
                logging.error(f"Error deleting split file ({split_filename}): {e}")

@app.route('/download/<filename>')
def download_file(filename):
    # 파일 다운로드 처리
    try:
        secure_name = secure_filename(filename)
        file_path = os.path.join(PROCESSED_FOLDER, secure_name)

        # 경로 검증
        if not os.path.abspath(file_path).startswith(os.path.abspath(PROCESSED_FOLDER)) or '..' in filename:
            abort(404)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            logging.info(f"Starting file download: {file_path}")
            
            # 파일 이름에서 file_id 제거
            base_filename, ext = os.path.splitext(secure_name)
            parts = base_filename.rsplit('_', 2)
            if len(parts) >= 3:
                download_name = f"{parts[0]}_{parts[2]}{ext}"
            else:
                download_name = secure_name
            
            return send_file(file_path, as_attachment=True, download_name=download_name)
        else:
            logging.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found.'}), 404
    except Exception as e:
        logging.error(f"Error during file download: {e}")
        return jsonify({'error': 'An error occurred during file download.'}), 500

if __name__ == "__main__":
    socketio.run(app, debug=True)
