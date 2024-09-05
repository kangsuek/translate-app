const socket = io();
const progressContainer = document.getElementById('progressContainer');
const progressBar = document.getElementById('progressBar');
const progressPercentage = document.getElementById('progressPercentage');
const statusMessage = document.getElementById('statusMessage');
const translationStatus = document.getElementById('translationStatus');
const downloadLinks = document.getElementById('downloadLinks');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');

let originalExtension = '';

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileName.textContent = e.target.files[0].name;
        uploadFile();
    } else {
        fileName.textContent = '번역할 파일을 업로드해 주세요.';
    }
});

function uploadFile() {
    const file = fileInput.files[0];
    if (!file) {
        statusMessage.textContent = '번역할 파일을 업로드해 주세요.';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    originalExtension = file.name.split('.').pop();

    fetch('/upload', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.ok) {
            progressContainer.style.display = 'block';
            statusMessage.textContent = '파일 업로드 완료, 번역 대기 중...';
            progressBar.style.width = '10%';
            progressPercentage.textContent = '10%';
            translationStatus.textContent = '파일 처리 시작 중...';
        } else {
            statusMessage.textContent = '파일 업로드 실패. 파일 확장자를 확인해주세요.';
        }
    }).catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = '파일 업로드 중 오류가 발생했습니다.';
    });
}

socket.on('progress', (data) => {
    statusMessage.textContent = data.data;
    progressBar.style.width = `${data.percentage}%`;
    progressPercentage.textContent = `${data.percentage}%`;
    
    if (data.percentage < 50) {
        translationStatus.textContent = '파일 분할 및 번역 준비 중...';
    } else if (data.percentage < 100) {
        translationStatus.textContent = '파일 부분 번역 중...';
    } else {
        translationStatus.textContent = '번역 완료. 다운로드 링크 준비 중...';
    }

    if (data.filenames) {
        downloadLinks.innerHTML = '';
        data.filenames.forEach((filename) => {
            if (filename.includes('_all')) {
                const newFilename = `translated_all.${originalExtension}`;
                const link = document.createElement('a');
                link.href = `/download/${filename}`;
                link.download = newFilename;
                link.textContent = `번역된 텍스트 다운로드 (.${originalExtension})`;
                link.className = 'download-btn';
                downloadLinks.appendChild(link);
            }
        });
        translationStatus.textContent = '번역이 완료되었습니다. 다운로드 링크가 준비되었습니다.';
    }
});