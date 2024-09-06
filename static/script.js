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

    fetch('/upload', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (response.ok) {
            progressContainer.style.display = 'block';
            statusMessage.textContent = 'File upload completed, waiting for translation...';
            progressBar.style.width = '10%';
            progressPercentage.textContent = '10%';
            translationStatus.textContent = 'Starting file processing...';
        } else {
            statusMessage.textContent = 'File upload failed. Please check the file extension.';
        }
    }).catch(error => {
        console.error('Error:', error);
        statusMessage.textContent = 'An error occurred while uploading the file.';
    });
}

socket.on('progress', (data) => {
    statusMessage.textContent = data.data;
    progressBar.style.width = `${data.percentage}%`;
    progressPercentage.textContent = `${data.percentage}%`;
    
    if (data.percentage < 50) {
        translationStatus.textContent = 'Splitting file and preparing for translation...';
    } else if (data.percentage < 100) {
        translationStatus.textContent = 'Translating file parts...';
    } else {
        translationStatus.textContent = 'Translation completed. Preparing download links...';
    }

    if (data.filenames) {
        downloadLinks.innerHTML = '';
        data.filenames.forEach((filename) => {
            if (filename.includes('_all')) {
                const newFilename = `translated_all.${originalExtension}`;
                const link = document.createElement('a');
                link.href = `/download/${filename}`;
                link.download = newFilename;
                link.textContent = `Download translated text (.${originalExtension})`;
                link.className = 'download-btn';
                downloadLinks.appendChild(link);
            }
        });
        translationStatus.textContent = 'Translation is complete. Download links are ready.';
    }
});