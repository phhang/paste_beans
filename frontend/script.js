// Configuration
// Use relative paths since frontend and backend are on the same server
const API_BASE_URL = '';

// DOM Elements
const pasteArea = document.getElementById('paste-area');
const previewImage = document.getElementById('preview-image');
const accountNameInput = document.getElementById('account-name');
const generateBtn = document.getElementById('generate-btn');
const copyBtn = document.getElementById('copy-btn');
const outputTextarea = document.getElementById('output');
const statusDiv = document.getElementById('status');

let currentImageData = null;

// Initialize paste functionality
function initializePaste() {
    // Make paste area focusable
    pasteArea.setAttribute('tabindex', '0');

    // Click to focus
    pasteArea.addEventListener('click', () => {
        pasteArea.focus();
    });

    // Focus/blur styling
    pasteArea.addEventListener('focus', () => {
        pasteArea.classList.add('focused');
    });

    pasteArea.addEventListener('blur', () => {
        pasteArea.classList.remove('focused');
    });

    // Handle paste event
    pasteArea.addEventListener('paste', handlePaste);
    document.addEventListener('paste', (e) => {
        if (document.activeElement === pasteArea) {
            handlePaste(e);
        }
    });
}

// Handle paste event
function handlePaste(event) {
    event.preventDefault();

    const items = event.clipboardData.items;

    for (let item of items) {
        if (item.type.indexOf('image') !== -1) {
            const blob = item.getAsFile();
            handleImageFile(blob);
            return;
        }
    }

    showStatus('Please paste an image file', 'error');
}

// Handle image file
function handleImageFile(file) {
    const reader = new FileReader();

    reader.onload = (e) => {
        currentImageData = e.target.result;

        // Show preview
        previewImage.src = currentImageData;
        previewImage.style.display = 'block';
        document.querySelector('.paste-instructions').style.display = 'none';

        // Enable generate button
        generateBtn.disabled = false;

        showStatus('Screenshot loaded successfully!', 'success');
    };

    reader.onerror = () => {
        showStatus('Error reading image file', 'error');
    };

    reader.readAsDataURL(file);
}

// Generate Beancount entry
async function generateBeancountEntry() {
    const accountName = accountNameInput.value.trim();

    if (!accountName) {
        showStatus('Please enter an account name', 'error');
        return;
    }

    if (!currentImageData) {
        showStatus('Please paste a screenshot first', 'error');
        return;
    }

    // Disable button and show loading state
    generateBtn.disabled = true;
    generateBtn.classList.add('loading');
    generateBtn.textContent = 'Generating...';
    showStatus('Processing screenshot with Azure OpenAI...', 'info');

    try {
        // Convert base64 to blob
        const base64Data = currentImageData.split(',')[1];
        const blob = base64ToBlob(base64Data, 'image/png');

        // Create form data
        const formData = new FormData();
        formData.append('image', blob, 'screenshot.png');
        formData.append('account_name', accountName);

        // Send request
        const response = await fetch(`${API_BASE_URL}/api/generate-beancount`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to generate Beancount entry');
        }

        const data = await response.json();

        // Display result
        // Combine all beancount entries from the results array
        if (data.results && data.results.length > 0) {
            const beancountEntries = data.results
                .map(result => result.beancount_entry)
                .filter(entry => entry) // Filter out any undefined entries
                .join('\n\n');

            outputTextarea.value = beancountEntries;
            copyBtn.style.display = 'block';

            const count = data.transactions_count || data.results.length;
            showStatus(`Successfully generated ${count} Beancount ${count === 1 ? 'entry' : 'entries'}!`, 'success');
        } else {
            throw new Error('No transactions found in the response');
        }

    } catch (error) {
        console.error('Error:', error);
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.classList.remove('loading');
        generateBtn.textContent = 'Generate Beancount Entry';
    }
}

// Copy to clipboard
function copyToClipboard() {
    outputTextarea.select();
    document.execCommand('copy');

    const originalText = copyBtn.textContent;
    copyBtn.textContent = 'Copied!';

    setTimeout(() => {
        copyBtn.textContent = originalText;
    }, 2000);
}

// Show status message
function showStatus(message, type) {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
}

// Convert base64 to blob
function base64ToBlob(base64, mimeType) {
    const byteCharacters = atob(base64);
    const byteArrays = [];

    for (let offset = 0; offset < byteCharacters.length; offset += 512) {
        const slice = byteCharacters.slice(offset, offset + 512);
        const byteNumbers = new Array(slice.length);

        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }

        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }

    return new Blob(byteArrays, { type: mimeType });
}

// Event listeners
generateBtn.addEventListener('click', generateBeancountEntry);
copyBtn.addEventListener('click', copyToClipboard);

// Initialize
initializePaste();
