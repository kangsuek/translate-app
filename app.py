from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit
import os
from googletrans import Translator
from werkzeug.utils import secure_filename

app = Flask(__name__)
# 'eventlet' 모드를 명시적으로 지정
socketio = SocketIO(app, async_mode='eventlet')
translator = Translator()

UPLOAD_FOLDER = 'uploads/'
PROCESSED_FOLDER = 'processed/'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    
    file = request.files['file']
    
    if file.filename == '':
        return 'No selected file', 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        socketio.start_background_task(target=process_translation, filepath=filepath, filename=filename)
        
        return 'File uploaded successfully!', 200

def process_translation(filepath, filename):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    socketio.emit('progress', {'data': 'Translating...'})
    
    translated_text = translator.translate(text, dest='ko').text
    
    new_filename = os.path.splitext(filename)[0] + '_korean.txt'
    new_filepath = os.path.join(PROCESSED_FOLDER, new_filename)
    
    with open(new_filepath, 'w', encoding='utf-8') as f:
        f.write(translated_text)
    
    socketio.emit('progress', {'data': 'Translation Completed!', 'filename': new_filename})

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(PROCESSED_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)
