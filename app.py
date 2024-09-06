import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
import os
from threading import Lock

# Flask 앱과 SocketIO 초기화
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()

# 파일 업로드 및 처리를 위한 폴더 설정
UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'
ALLOWED_EXTENSIONS = {'txt', 'srt'}
MAX_CHARS = 4000

# 필요한 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# 지원하는 언어 목록 정의
LANGUAGES = {
    'ko': 'Korean',
    'en': 'English',
    'ja': 'Japanese',
    'zh-cn': 'Chinese (Simplified)',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish'
}

# 허용된 파일 확장자 체크 함수
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 메인 페이지 라우트
@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES)

# 파일 업로드 처리 라우트
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    
    file = request.files['file']
    
    if file.filename == '' or not file:
        return 'No selected file', 400
    
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return 'File uploaded successfully!', 200
    else:
        return 'File type not allowed', 400

# 번역 시작 라우트
@app.route('/start_translation', methods=['POST'])
def start_translation():
    data = request.json
    filename = data.get('filename')
    target_language = data.get('target_language')
    
    if not filename or not target_language:
        return 'Missing filename or target language', 400
    
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    if not os.path.exists(filepath):
        return 'File not found', 404
    
    # 백그라운드에서 번역 작업 시작
    socketio.start_background_task(target=process_file, filepath=filepath, filename=filename, target_language=target_language)
    return 'Translation started', 200

# 텍스트를 지정된 길이로 분할하는 함수
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

# 파일 처리 및 번역 함수
def process_file(filepath, filename, target_language):
    with thread_lock:
        try:
            # 파일 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            # 텍스트 분할
            text_parts = split_text(text, MAX_CHARS)
            total_parts = len(text_parts)

            # 진행 상황 업데이트
            socketio.emit('progress', {'data': f'Splitting file into {total_parts} parts...', 'percentage': 10})
            eventlet.sleep(0)

            base_filename = os.path.splitext(filename)[0]
            original_extension = os.path.splitext(filename)[1]
            split_filenames = []

            # 분할된 파일 저장
            for i, part in enumerate(text_parts, 1):
                split_filename = f'{base_filename}_part{i}.txt'
                split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)

                with open(split_filepath, 'w', encoding='utf-8') as f:
                    f.write(part)

                split_filenames.append(split_filename)

                # 진행 상황 업데이트
                progress = int((i / total_parts) * 40) + 10
                socketio.emit('progress', {'data': f'Saved part {i} of {total_parts}', 'percentage': progress})
                eventlet.sleep(0)

            socketio.emit('progress', {'data': 'File splitting completed. Starting translation...', 'percentage': 50})
            eventlet.sleep(0)

            # 번역 시작
            translator = GoogleTranslator(source='auto', target=target_language)
            all_translated_text = []

            for i, split_filename in enumerate(split_filenames, 1):
                split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)
                with open(split_filepath, 'r', encoding='utf-8') as f:
                    part_text = f.read()

                translated_text = translator.translate(part_text)
                all_translated_text.append(translated_text)

                # 진행 상황 업데이트
                progress = int((i / total_parts) * 40) + 50
                socketio.emit('progress', {'data': f'Translated part {i} of {total_parts}', 'percentage': progress})
                eventlet.sleep(0)

            # 번역된 전체 텍스트 저장
            all_filename = f'{base_filename}_{target_language}_all{original_extension}'
            all_filepath = os.path.join(PROCESSED_FOLDER, all_filename)

            with open(all_filepath, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(all_translated_text))

            # 임시 파일 삭제
            for filename in split_filenames:
                os.remove(os.path.join(PROCESSED_FOLDER, filename))

            # 번역 완료 메시지 전송
            socketio.emit('progress', {
                'data': 'Translation Completed! All part files have been deleted.',
                'filenames': [all_filename],
                'percentage': 100
            })
        except Exception as e:
            socketio.emit('progress', {'data': f'Error: {str(e)}', 'percentage': 0})
        finally:
            os.remove(filepath)
            
# 번역된 파일 다운로드 라우트
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(PROCESSED_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)