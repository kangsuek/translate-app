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
const startTranslationBtn = document.getElementById('startTranslationBtn');
const targetLanguageSelect = document.getElementById('targetLanguage');

let originalExtension = '';
let uploadedFilename = '';

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileName.textContent = e.target.files[0].name;
        uploadFile();
    } else {
        fileName.textContent = 'Please upload a file to translate.';
    }
});

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

    fetch('/upload', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.ok) {
            statusMessage.textContent = 'File upload completed. Click "Start Translation" to begin.';
            startTranslationBtn.disabled = false;
        } else {
            statusMessage.textContent = 'File upload failed. Please check the file extension.';
        }
    }).catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = 'An error occurred while uploading the file.';
    });
}

startTranslationBtn.addEventListener('click', () => {
    if (!uploadedFilename) {
        statusMessage.textContent = 'Please upload a file first.';
        return;
    }

    const targetLanguage = targetLanguageSelect.value;
    
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

socket.on('progress', (data) => {
    statusMessage.textContent = data.data;
    progressBar.style.width = `${data.percentage}%`;
    progressPercentage.textContent = `${data.percentage}%`;
    
    if (data.percentage < 50) {
        translationStatus.textContent = 'Splitting file and preparing for translation...';
    } else if (data.percentage < 100) {
        translationStatus.textContent = 'Translating file parts...';
    } else {
        translationStatus.textContent = 'Translation completed. Preparing download link...';
    }

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
        }, 1000); // 1 second delay
    }
});