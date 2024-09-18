const socket = io();

const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const startTranslationBtn = document.getElementById("startTranslationBtn");
const targetLanguageSelect = document.getElementById("targetLanguage");
const uploadProgress = document.getElementById("uploadProgress");
const fileList = document.getElementById("fileList");
const statusMessage = document.getElementById("statusMessage");

let uploadedFiles = [];

uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (e) => {
  const files = Array.from(e.target.files);
  const invalidFiles = files.filter(file => {
    const extension = '.' + file.name.split('.').pop().toLowerCase();
    return !allowedExtensions.includes(extension);
  });

  if (invalidFiles.length > 0) {
    alert('The following files are not allowed: ' + invalidFiles.map(f => f.name).join(', '));
    e.target.value = '';  // 파일 선택 초기화
  } else {
    handleFileUpload(e);
  }
});

function handleFileUpload(event) {
  if (event.target.files.length > 0) {
    uploadFiles(event.target.files);
  }
}

function uploadFiles(files) {
  const formData = new FormData();
  let duplicateFiles = [];
  let newFiles = [];

  for (let i = 0; i < files.length; i++) {
    if (
      uploadedFiles.some((uploadedFile) => uploadedFile.name === files[i].name)
    ) {
      duplicateFiles.push(files[i].name);
    } else {
      formData.append("files[]", files[i]);
      newFiles.push(files[i].name);
    }
  }

  statusMessage.textContent = "";
  if (duplicateFiles.length > 0) {
    statusMessage.textContent = `Skipping already uploaded files: ${duplicateFiles.join(", ")}`;
  }

  if (newFiles.length === 0) {
    statusMessage.textContent += " No new files to upload.";
    return;
  }

  newFiles.forEach((fileName) => {
    const fileItem = document.createElement("div");
    fileItem.className = "file-item";
    fileItem.setAttribute("data-file-id", "");
    fileItem.innerHTML = `<span>${fileName}</span>
                              <span class='progress-text'>0%</span>
                              <button class='delete-btn' data-file-id=''>Delete</button>`;
    fileList.appendChild(fileItem);
  });

  fetch("/upload", {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      statusMessage.textContent = "";
      if (data.files) {
        uploadedFiles = [...uploadedFiles, ...data.files];
        updateFileList();
        startTranslationBtn.disabled = false;
        fileInput.value = "";
        statusMessage.textContent = `Successfully uploaded: ${newFiles.join(", ")}`;
      } else {
        statusMessage.textContent = data.error || "Upload failed.";
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      statusMessage.textContent = "";
      statusMessage.textContent = "An error occurred while uploading files.";
    });
}

function updateFileList() {
  fileList.innerHTML = "";
  uploadedFiles.forEach((file) => {
    const fileItem = document.createElement("div");
    fileItem.className = "file-item";
    fileItem.setAttribute("data-file-id", file.id);
    fileItem.innerHTML = `
            <div class="file-info">
                <span class="file-name" title="${file.name}">${file.name}</span>
                <span class='progress-text'>0%</span>
            </div>
            <div class="file-actions">
                <button class='delete-btn' data-file-id='${file.id}'>Delete</button>
            </div>`;
    fileList.appendChild(fileItem);
  });

  const deleteButtons = document.querySelectorAll(".delete-btn");
  deleteButtons.forEach((button) => {
    button.addEventListener("click", (e) => {
      const fileId = e.target.getAttribute("data-file-id");
      deleteFile(fileId);
    });
  });
}

function deleteFile(fileId) {
  fetch(`/delete_file/${fileId}`, {
    method: "DELETE",
  })
    .then((response) => response.json())
    .then((data) => {
      statusMessage.textContent = "";
      if (data.success) {
        // Remove deleted file item from UI
        const fileItem = document.querySelector(`[data-file-id="${fileId}"]`);
        if (fileItem) {
          fileItem.remove();
        }
        // Remove file from uploadedFiles array
        uploadedFiles = uploadedFiles.filter((file) => file.id !== fileId);
        if (uploadedFiles.length === 0) {
          startTranslationBtn.disabled = true;
        }
        statusMessage.textContent = data.message;
      } else {
        statusMessage.textContent = data.error || "Failed to delete file.";
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      statusMessage.textContent = "";
      statusMessage.textContent = "An error occurred while deleting the file.";
    });
}

startTranslationBtn.addEventListener("click", () => {
  if (uploadedFiles.length === 0) {
    statusMessage.textContent = "";
    statusMessage.textContent = "Please upload files first.";
    return;
  }

  const targetLanguage = targetLanguageSelect.value;

  fetch("/start_translation", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      files: uploadedFiles,
      target_language: targetLanguage,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      statusMessage.textContent = "";
      if (data.message) {
        statusMessage.textContent = data.message;
      } else {
        statusMessage.textContent =
          data.error || "Failed to start translation.";
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      statusMessage.textContent = "";
      statusMessage.textContent =
        "An error occurred while starting the translation.";
    });
});

socket.on("file_progress", (data) => {
  const fileItem = Array.from(fileList.children).find(
    (item) => item.getAttribute("data-file-id") === data.file_id,
  );
  if (fileItem) {
    const progressText = fileItem.querySelector(".progress-text");
    progressText.textContent = `${data.percentage}% - ${data.status}`;

    if (data.download_filename) {
      let downloadLink = fileItem.querySelector(".download-btn");
      if (!downloadLink) {
        downloadLink = document.createElement("a");
        downloadLink.href = `/download/${encodeURIComponent(data.download_filename)}`;
        downloadLink.download = data.download_filename.split('_').slice(0, -1).join('_') + '_' + data.download_filename.split('_').pop();
        downloadLink.textContent = "Download";
        downloadLink.className = "download-btn";
        downloadLink.addEventListener("click", (e) => {
          e.preventDefault();
          window.location.href = downloadLink.href;
        });
        fileItem.querySelector(".file-actions").appendChild(downloadLink);
      } else {
        downloadLink.href = `/download/${encodeURIComponent(data.download_filename)}`;
        downloadLink.download = data.download_filename.split('_').slice(0, -1).join('_') + '_' + data.download_filename.split('_').pop();
      }
    }
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const fileInput = document.getElementById("fileInput");
  if (fileInput && typeof allowedExtensions !== "undefined") {
    fileInput.accept = allowedExtensions;
  }
});

// 언어 선택 옵션을 동적으로 생성
Object.entries(LANGUAGES).forEach(([code, name]) => {
  const option = document.createElement('option');
  option.value = code;
  option.textContent = name;
  targetLanguageSelect.appendChild(option);
});
