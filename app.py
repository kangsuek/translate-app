# 필요한 라이브러리 및 모듈 임포트
from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
import os
from threading import Lock

# Flask 앱 및 SocketIO 초기화
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
thread_lock = Lock()  # 스레드 안전성을 위한 락 객체 생성

# 파일 업로드 및 처리를 위한 디렉토리 설정
UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'
ALLOWED_EXTENSIONS = {'txt'}  # 허용된 파일 확장자

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
        
        # 백그라운드에서 번역 처리 시작
        socketio.start_background_task(target=process_translation, filepath=filepath, filename=filename)
        
        return 'File uploaded successfully!', 200
    else:
        return 'File type not allowed', 400

# 번역 처리 함수
def process_translation(filepath, filename):
    with thread_lock:  # 스레드 안전성 보장
        try:
            # 파일 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            socketio.emit('progress', {'data': 'Translating...', 'percentage': 25})

            # Google Translator를 사용하여 번역
            translator = GoogleTranslator(source='auto', target='ko')
            translated_text = translator.translate(text)

            socketio.emit('progress', {'data': 'Translation completed. Saving file...', 'percentage': 75})

            # 번역된 텍스트를 새 파일에 저장
            new_filename = os.path.splitext(filename)[0] + '_korean.txt'
            new_filepath = os.path.join(PROCESSED_FOLDER, new_filename)

            with open(new_filepath, 'w', encoding='utf-8') as f:
                f.write(translated_text)

            socketio.emit('progress', {'data': 'Translation Completed!', 'filename': new_filename, 'percentage': 100})
        except Exception as e:
            socketio.emit('progress', {'data': f'Error: {str(e)}', 'percentage': 0})
        finally:
            # 원본 업로드 파일 삭제
            os.remove(filepath)

# 번역된 파일 다운로드 라우트
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(PROCESSED_FOLDER, filename), as_attachment=True)

# 메인 실행 부분
if __name__ == "__main__":
    socketio.run(app, debug=True)