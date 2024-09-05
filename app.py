import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
import os
from threading import Lock
import math

# Flask 앱 및 SocketIO 초기화
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()  # 스레드 안전성을 위한 락 객체 생성

# 파일 업로드 및 처리를 위한 디렉토리 설정
UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'
ALLOWED_EXTENSIONS = {'txt', 'srt'}  # 허용된 파일 확장자
MAX_CHARS = 4000  # 번역기의 최대 글자 수 제한

# 필요한 디렉토리 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# 파일 확장자 검사 함수
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 메인 페이지 라우트
@app.route('/')
def index():
    return render_template('index.html')

# 파일 업로드 처리 라우트
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    
    file = request.files['file']
    
    if file.filename == '':
        return 'No selected file', 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # 백그라운드에서 파일 처리 시작
        socketio.start_background_task(target=process_file, filepath=filepath, filename=filename)
        
        return 'File uploaded successfully!', 200
    else:
        return 'File type not allowed', 400

# 텍스트를 주어진 최대 길이로 분할하는 함수
# MAX_CHARS보다 글자 수가 작고 '\n\n'이 있는 부분에서 분할
# 텍스트를 단락('\n\n'으로 구분)으로 나누고, 
# 각 단락을 가능한 한 MAX_CHARS 내에서 유지하면서 분할합니다.
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

# 파일 처리 함수 (분할 및 번역)
def process_file(filepath, filename):
    with thread_lock:  # 스레드 안전성 보장
        try:
            # 파일 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            # 텍스트를 분할
            text_parts = split_text(text, MAX_CHARS)
            total_parts = len(text_parts)

            socketio.emit('progress', {'data': f'Splitting file into {total_parts} parts...', 'percentage': 10})
            eventlet.sleep(0)  # 이벤트 루프가 업데이트를 처리할 수 있도록 잠시 대기

            # 분할된 텍스트를 개별 파일로 저장
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
                socketio.emit('progress', {'data': f'Saved part {i} of {total_parts}', 'percentage': progress})
                eventlet.sleep(0)  # 이벤트 루프가 업데이트를 처리할 수 있도록 잠시 대기

            socketio.emit('progress', {'data': 'File splitting completed. Starting translation...', 'percentage': 50})
            eventlet.sleep(0)  # 이벤트 루프가 업데이트를 처리할 수 있도록 잠시 대기

            # Google Translator를 사용하여 번역
            translator = GoogleTranslator(source='auto', target='ko')
            translated_filenames = []

            for i, split_filename in enumerate(split_filenames, 1):
                split_filepath = os.path.join(PROCESSED_FOLDER, split_filename)
                with open(split_filepath, 'r', encoding='utf-8') as f:
                    part_text = f.read()

                translated_text = translator.translate(part_text)

                translated_filename = f'{base_filename}_korean_part{i}.txt'
                translated_filepath = os.path.join(PROCESSED_FOLDER, translated_filename)

                with open(translated_filepath, 'w', encoding='utf-8') as f:
                    f.write(translated_text)

                translated_filenames.append(translated_filename)

                progress = int((i / total_parts) * 40) + 50
                socketio.emit('progress', {'data': f'Translated part {i} of {total_parts}', 'percentage': progress})
                eventlet.sleep(0)  # 이벤트 루프가 업데이트를 처리할 수 있도록 잠시 대기

            # 모든 번역된 텍스트를 하나의 파일로 합치기
            all_filename = f'{base_filename}_korean_all{original_extension}'
            all_filepath = os.path.join(PROCESSED_FOLDER, all_filename)

            with open(all_filepath, 'w', encoding='utf-8') as f:
                for translated_filename in translated_filenames:
                    with open(os.path.join(PROCESSED_FOLDER, translated_filename), 'r', encoding='utf-8') as part_file:
                        f.write(part_file.read() + "\n\n")

            # 분할된 파일들 삭제
            for filename in split_filenames + translated_filenames:
                os.remove(os.path.join(PROCESSED_FOLDER, filename))

            socketio.emit('progress', {
                'data': 'Translation Completed! All part files have been deleted.',
                'filenames': [all_filename],
                'percentage': 100
            })
        except Exception as e:
            socketio.emit('progress', {'data': f'Error: {str(e)}', 'percentage': 0})
        finally:
            # 원본 업로드 파일 삭제
            os.remove(filepath)
            
# 번역된 파일 다운로드 라우트
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(PROCESSED_FOLDER, filename), as_attachment=True)

# 번역된 파일 목록 제공 라우트
@app.route('/files')
def list_files():
    files = [f for f in os.listdir(PROCESSED_FOLDER) if os.path.isfile(os.path.join(PROCESSED_FOLDER, f))]
    return jsonify(files)

# 메인 실행 부분
if __name__ == "__main__":
    socketio.run(app, debug=True)