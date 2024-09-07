const socket = io();

const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const startTranslationBtn = document.getElementById('startTranslationBtn');
const targetLanguageSelect = document.getElementById('targetLanguage');
const uploadProgress = document.getElementById('uploadProgress');
const fileList = document.getElementById('fileList');
const statusMessage = document.getElementById('statusMessage');

let uploadedFiles = [];

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        uploadFiles(e.target.files);
    }
});

function uploadFiles(files) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files[]', files[i]);
    }

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.files) {
            uploadedFiles = data.files;
            updateFileList();
            startTranslationBtn.disabled = false;
        } else {
            statusMessage.textContent = data.error || 'Upload failed';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = 'An error occurred while uploading the files.';
    });
}

function updateFileList() {
    fileList.innerHTML = '';
    uploadedFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span>${file.name}</span>
            <div class="file-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <span class="progress-text">0%</span>
            </div>
            <button class="delete-btn" data-file-id="${file.id}">삭제</button>
        `;
        fileList.appendChild(fileItem);
    });

    // 삭제 버튼에 이벤트 리스너 추가
    const deleteButtons = document.querySelectorAll('.delete-btn');
    deleteButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const fileId = e.target.getAttribute('data-file-id');
            deleteFile(fileId);
        });
    });
}

function deleteFile(fileId) {
    fetch(`/delete_file/${fileId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            uploadedFiles = uploadedFiles.filter(file => file.id !== fileId);
            updateFileList();
            if (uploadedFiles.length === 0) {
                startTranslationBtn.disabled = true;
            }
            statusMessage.textContent = '파일이 성공적으로 삭제되었습니다.';
        } else {
            statusMessage.textContent = data.error || '파일 삭제에 실패했습니다.';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = '파일 삭제 중 오류가 발생했습니다.';
    });
}

startTranslationBtn.addEventListener('click', () => {
    if (uploadedFiles.length === 0) {
        statusMessage.textContent = 'Please upload files first.';
        return;
    }

    const targetLanguage = targetLanguageSelect.value;
    
    fetch('/start_translation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            files: uploadedFiles,
            target_language: targetLanguage
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            statusMessage.textContent = data.message;
        } else {
            statusMessage.textContent = data.error || 'Failed to start translation';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = 'An error occurred while starting the translation.';
    });
});

socket.on('file_progress', (data) => {
    const fileItem = fileList.querySelector(`.file-item:nth-child(${uploadedFiles.findIndex(f => f.id === data.file_id) + 1})`);
    if (fileItem) {
        const progressBar = fileItem.querySelector('.progress-fill');
        const progressText = fileItem.querySelector('.progress-text');
        progressBar.style.width = `${data.percentage}%`;
        progressText.textContent = `${data.percentage}% - ${data.status}`;

        if (data.download_filename) {
            const downloadLink = document.createElement('a');
            downloadLink.href = `/download/${data.download_filename}`;
            downloadLink.download = data.download_filename;
            downloadLink.textContent = 'Download';
            downloadLink.className = 'download-btn';
            fileItem.appendChild(downloadLink);
        }
    }
});