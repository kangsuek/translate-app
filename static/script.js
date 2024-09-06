// Socket.IO 연결 설정
const socket = io();

// DOM 요소 선택
const progressContainer = document.getElementById('progressContainer');
const progressBar = document.getElementById('progressBar');
const progressPercentage = document.getElementById('progressPercentage');
const statusMessage = document.getElementById('statusMessage');
const translationStatus = document.getElementById('translationStatus');
const downloadLinks = document.getElementById('downloadLinks');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const startTranslationBtn = document.getElementById('startTranslationBtn');
const targetLanguageSelect = document.getElementById('targetLanguage');
const uploadProgress = document.getElementById('uploadProgress');

// 파일 정보 저장 변수
let originalExtension = '';
let uploadedFilename = '';

// 파일 선택 버튼 클릭 이벤트 처리
uploadBtn.addEventListener('click', () => fileInput.click());

// 파일 선택 시 이벤트 처리
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileName.textContent = e.target.files[0].name;
        uploadFile();
    } else {
        fileName.textContent = 'Please upload a file to translate.';
    }
});

// 파일 업로드 함수
function uploadFile() {
    const file = fileInput.files[0];
    if (!file) {
        statusMessage.textContent = 'Please upload a file to translate.';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    originalExtension = file.name.split('.').pop();
    uploadedFilename = file.name;

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    
    // 업로드 진행 상황 표시
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            uploadProgress.textContent = `${percentComplete}%`;
            uploadProgress.style.display = 'block';
        }
    };

    // 업로드 완료 처리
    xhr.onload = function() {
        if (xhr.status === 200) {
            statusMessage.textContent = 'File upload completed. Click "Start Translation" to begin.';
            startTranslationBtn.disabled = false;
        } else {
            statusMessage.textContent = 'File upload failed. Please check the file extension.';
        }
        uploadProgress.style.display = 'none';
    };

    // 업로드 오류 처리
    xhr.onerror = function() {
        console.error('Error:', xhr.statusText);
        statusMessage.textContent = 'An error occurred while uploading the file.';
        uploadProgress.style.display = 'none';
    };

    xhr.send(formData);
}

// 번역 시작 버튼 클릭 이벤트 처리
startTranslationBtn.addEventListener('click', () => {
    if (!uploadedFilename) {
        statusMessage.textContent = 'Please upload a file first.';
        return;
    }

    const targetLanguage = targetLanguageSelect.value;
    
    // 번역 시작 요청
    fetch('/start_translation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            filename: uploadedFilename,
            target_language: targetLanguage
        })
    }).then(response => {
        if (response.ok) {
            progressContainer.style.display = 'block';
            statusMessage.textContent = 'Translation started...';
            progressBar.style.width = '0%';
            progressPercentage.textContent = '0%';
            translationStatus.textContent = 'Starting file processing...';
        } else {
            statusMessage.textContent = 'Failed to start translation. Please try again.';
        }
    }).catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = 'An error occurred while starting the translation.';
    });
});

// Socket.IO를 통한 진행 상황 업데이트 처리
socket.on('progress', (data) => {
    statusMessage.textContent = data.data;
    progressBar.style.width = `${data.percentage}%`;
    progressPercentage.textContent = `${data.percentage}%`;
    
    // 번역 단계별 상태 메시지 업데이트
    if (data.percentage < 50) {
        translationStatus.textContent = 'Splitting file and preparing for translation...';
    } else if (data.percentage < 100) {
        translationStatus.textContent = 'Translating file parts...';
    } else {
        translationStatus.textContent = 'Translation completed. Preparing download link...';
    }

    // 번역 완료 시 다운로드 링크 생성
    if (data.filenames) {
        setTimeout(() => {
            downloadLinks.innerHTML = '';
            data.filenames.forEach((filename) => {
                const link = document.createElement('a');
                link.href = `/download/${filename}`;
                link.download = filename;
                link.textContent = `Download translated file (${filename})`;
                link.className = 'download-btn';
                downloadLinks.appendChild(link);
            });
            translationStatus.textContent = 'Translation is complete. Download link is ready.';
        }, 1000); // 1초 지연
    }
});