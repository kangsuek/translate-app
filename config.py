import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'txt,srt').split(','))
    MAX_CHARS = int(os.getenv('MAX_CHARS', 4000))
    
    # 현재 스크립트의 디렉토리를 기준으로 절대 경로 설정
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    PROCESSED_FOLDER = os.path.join(BASE_DIR, 'processed')
    