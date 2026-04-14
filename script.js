// VidSave - Social Media Video Downloader
// Supports: YouTube, Instagram, TikTok, Facebook, Twitter

// Auto-detect API URL: if opened via server use relative, else use localhost
const API_URL = window.location.protocol === 'file:'
    ? 'http://localhost:5000'
    : '';  // empty = same origin (served by Flask)

// Global state
let currentMode = 'video'; // 'video' or 'audio'
let downloadHistory = JSON.parse(localStorage.getItem('vidsave_history') || '[]');

// Platform detection
const PLATFORM_PATTERNS = {
    youtube:   /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
    facebook:  /(?:facebook\.com\/.*\/videos\/|fb\.watch\/)([0-9]+)/,
    instagram: /(?:instagram\.com\/p\/|instagram\.com\/reel\/|instagram\.com\/reels\/|instagram\.com\/tv\/)([a-zA-Z0-9_-]+)/,
    tiktok:    /(?:tiktok\.com\/@[\w.]+\/video\/|vm\.tiktok\.com\/|tiktok\.com\/t\/)([a-zA-Z0-9_-]+)/,
    twitter:   /(?:twitter\.com\/|x\.com\/)[\w]+\/status\/([0-9]+)/,
    pinterest: /(?:pinterest\.[a-z]+\/pin\/|pin\.it\/)([a-zA-Z0-9_-]+)/,
    reddit:    /(?:reddit\.com\/r\/[\w]+\/comments\/|redd\.it\/)([a-zA-Z0-9_-]+)/,
    dailymotion: /(?:dailymotion\.com\/video\/|dai\.ly\/)([a-zA-Z0-9_-]+)/,
    vimeo:     /vimeo\.com\/(\d+)/,
    twitch:    /(?:twitch\.tv\/videos\/|twitch\.tv\/[\w]+\/clip\/|clips\.twitch\.tv\/)([a-zA-Z0-9_-]+)/
};

// DOM refs
const videoUrlInput = document.getElementById('videoUrl');
const downloadBtn   = document.getElementById('downloadBtn');
const loadingDiv    = document.getElementById('loading');
const resultDiv     = document.getElementById('result');
const errorDiv      = document.getElementById('error');
const errorMsg      = document.getElementById('errorMessage');

// Enter key support
document.addEventListener('DOMContentLoaded', () => {
    videoUrlInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') processVideo();
    });
});

// Clear input
function clearInput() {
    videoUrlInput.value = '';
    videoUrlInput.focus();
    hideAll();
}

// ─── MAIN FUNCTION ─────────────────────────────────────────────────────────
async function processVideo() {
    const url = videoUrlInput.value.trim();

    if (!url) { showError('Please paste a video URL first.'); return; }

    try { new URL(url); } catch {
        showError('Invalid URL. Please paste a correct video link.'); return;
    }

    // Allow any URL - let server decide (yt-dlp supports 1000+ sites)
    showLoading();

    try {
        const res = await fetch(`${API_URL}/api/info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await res.json();

        if (!res.ok || data.error) {
            throw new Error(data.error || 'Could not fetch video info');
        }

        showResult(data, url);

    } catch (err) {
        console.error(err);
        showError(err.message || 'Server error. Make sure server is running.');
    }
}

// ─── SHOW RESULT (SSS Style) ────────────────────────────────────────────────
function showResult(data, url) {
    hideAll();
    resultDiv.classList.remove('hidden');

    // Thumbnail
    const thumb = document.getElementById('thumbnail');
    thumb.src = data.thumbnail || '';
    thumb.onerror = () => { thumb.style.display = 'none'; };

    // Title
    document.getElementById('videoTitle').textContent = data.title || 'Unknown Title';

    // Duration
    const durEl = document.getElementById('videoDuration');
    durEl.innerHTML = `<i class="fas fa-clock"></i> <span>${formatDuration(data.duration)}</span>`;

    // Platform
    const platEl = document.getElementById('videoPlatform');
    platEl.innerHTML = `<i class="fas fa-globe"></i> <span>${capitalize(data.platform || 'Unknown')}</span>`;

    const formats = data.formats && data.formats.length > 0
        ? data.formats
        : [{ format_id: 'best', quality: 'Best Quality', ext: 'mp4', has_audio: true, filesize: 0 }];

    // Store for use in download
    window._currentFormats = formats;
    window._currentUrl = url;

    const list = document.getElementById('downloadList');
    list.innerHTML = `
        <!-- Quality Selector -->
        <div class="quality-selector-wrap">
            <div class="quality-label"><i class="fas fa-sliders-h"></i> Select Quality</div>
            <div class="quality-pills" id="qualityPills"></div>
        </div>

        <!-- Selected quality info + big download button -->
        <div class="selected-download" id="selectedDownload">
            <div class="sel-info">
                <div class="sel-icon"><i class="fas fa-film"></i></div>
                <div>
                    <div class="sel-quality" id="selQualityLabel">-</div>
                    <div class="sel-meta" id="selMetaLabel">-</div>
                </div>
            </div>
            <button class="dl-btn-big" id="mainDlBtn" onclick="downloadSelected()">
                <i class="fas fa-download"></i> Download
            </button>
        </div>

        <!-- All formats list -->
        <div class="all-formats">
            <div class="all-formats-title">All Available Formats</div>
            <div id="allFormatsList"></div>
        </div>
    `;

    // Build quality pills
    const pillsDiv = document.getElementById('qualityPills');
    formats.forEach((fmt, i) => {
        const pill = document.createElement('button');
        pill.className = 'q-pill' + (i === 0 ? ' active' : '');
        pill.textContent = fmt.quality || 'Best';
        pill.onclick = () => selectQualityPill(pill, fmt, i);
        pillsDiv.appendChild(pill);
    });

    // Build all formats list
    const allList = document.getElementById('allFormatsList');
    formats.forEach((fmt, i) => {
        const size = fmt.filesize && fmt.filesize > 0
            ? `${(fmt.filesize / 1024 / 1024).toFixed(1)} MB`
            : '';
        const row = document.createElement('div');
        row.className = 'dl-item' + (i === 0 ? ' active-row' : '');
        row.id = `fmtRow_${i}`;
        row.innerHTML = `
            <div class="dl-left">
                <div class="dl-icon"><i class="fas fa-film"></i></div>
                <div class="dl-info">
                    <div class="dl-quality">${fmt.quality || 'Best'}</div>
                    <div class="dl-meta">${fmt.ext ? fmt.ext.toUpperCase() : 'MP4'}${size ? ' · ' + size : ''}${fmt.has_audio === false ? ' · video only' : ''}</div>
                </div>
            </div>
            <button class="dl-btn" onclick="startDownload(this, '${encodeURIComponent(url)}', '${fmt.format_id}', ${fmt.has_audio === false ? 'false' : 'true'})">
                <i class="fas fa-download"></i> Download
            </button>
        `;
        allList.appendChild(row);
    });

    // Select first by default
    selectQualityPill(pillsDiv.children[0], formats[0], 0);

    // Reset main button
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
}

// Select quality pill
function selectQualityPill(pill, fmt, index) {
    // Update pills
    document.querySelectorAll('.q-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');

    // Update selected row highlight
    document.querySelectorAll('.dl-item').forEach(r => r.classList.remove('active-row'));
    const row = document.getElementById(`fmtRow_${index}`);
    if (row) row.classList.add('active-row');

    // Update selected info
    const size = fmt.filesize && fmt.filesize > 0
        ? `${(fmt.filesize / 1024 / 1024).toFixed(1)} MB`
        : 'Size unknown';
    document.getElementById('selQualityLabel').textContent = fmt.quality || 'Best';
    document.getElementById('selMetaLabel').textContent =
        `${fmt.ext ? fmt.ext.toUpperCase() : 'MP4'} · ${size}`;

    // Store selected format
    window._selectedFormat = fmt;
}

// Download selected quality
function downloadSelected() {
    const fmt = window._selectedFormat;
    const url = window._currentUrl;
    if (!fmt || !url) return;
    const btn = document.getElementById('mainDlBtn');
    startDownload(btn, encodeURIComponent(url), fmt.format_id, fmt.has_audio);
}

// ─── DOWNLOAD ───────────────────────────────────────────────────────────────
async function startDownload(btn, encodedUrl, formatId, hasAudio = true) {
    const url = decodeURIComponent(encodedUrl);
    const original = btn.innerHTML;

    btn.disabled = true;
    btn.classList.add('downloading');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Getting link...';

    try {
        const res = await fetch(`${API_URL}/api/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, format_id: formatId, has_audio: hasAudio })
        });

        const data = await res.json();

        if (!res.ok || data.error) {
            throw new Error(data.error || 'Download failed');
        }

        const downloadUrl = data.file_url || data.direct_url;
        if (downloadUrl) {
            btn.innerHTML = '<i class="fas fa-check"></i> Opening...';
            
            // Create hidden anchor and click - browser handles download
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = data.filename || 'video.mp4';
            a.target = '_blank';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            btn.classList.remove('downloading');
            btn.innerHTML = '<i class="fas fa-check"></i> Done!';
            showToast('Download started!', 'success');
        } else {
            throw new Error('No download URL received');
        }

    } catch (err) {
        console.error(err);
        btn.classList.remove('downloading');
        btn.innerHTML = '<i class="fas fa-exclamation-circle"></i> Failed';
        showToast('Download failed: ' + err.message, 'error');
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = original;
        }, 3000);
    }
}

// ─── UI HELPERS ─────────────────────────────────────────────────────────────
function showLoading() {
    hideAll();
    loadingDiv.classList.remove('hidden');
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
}

function showError(msg) {
    hideAll();
    errorDiv.classList.remove('hidden');
    errorMsg.textContent = msg;
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
}

function hideAll() {
    loadingDiv.classList.add('hidden');
    resultDiv.classList.add('hidden');
    errorDiv.classList.add('hidden');
}

// Toast notification
function showToast(message, type = 'info') {
    const colors = { info: '#667eea', error: '#ef4444', success: '#10b981' };
    const toast = document.createElement('div');
    toast.style.cssText = `
        position:fixed; bottom:24px; right:24px;
        background:${colors[type] || '#667eea'}; color:white;
        padding:14px 20px; border-radius:10px;
        box-shadow:0 8px 24px rgba(0,0,0,0.2);
        z-index:9999; font-size:0.95rem; max-width:320px;
        animation: fadeInUp 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ─── UTILS ──────────────────────────────────────────────────────────────────
function formatDuration(seconds) {
    if (!seconds) return 'Unknown';
    seconds = Math.round(seconds);
    const hrs  = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) return `${hrs}:${pad(mins)}:${pad(secs)}`;
    return `${mins}:${pad(secs)}`;
}

function pad(n) { return String(n).padStart(2, '0'); }

function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
}

// Inject animation CSS
const s = document.createElement('style');
s.textContent = `@keyframes fadeInUp { from { transform:translateY(20px); opacity:0; } to { transform:translateY(0); opacity:1; } }`;
document.head.appendChild(s);

console.log('VidSave loaded ✅');

// ========== NEW FEATURES ==========

// Dark Mode Toggle
function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    document.getElementById('themeIcon').className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    localStorage.setItem('vidsave_theme', isDark ? 'dark' : 'light');
}

// Load saved theme
const savedTheme = localStorage.getItem('vidsave_theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    document.getElementById('themeIcon').className = 'fas fa-sun';
}

// Paste from Clipboard
async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        videoUrlInput.value = text;
        videoUrlInput.focus();
        showToast('Pasted from clipboard!', 'success');
    } catch (err) {
        showToast('Clipboard access denied. Use Ctrl+V.', 'error');
    }
}

// Set Mode (Video/Audio)
function setMode(mode) {
    currentMode = mode;
    document.getElementById('videoModeBtn').classList.toggle('active', mode === 'video');
    document.getElementById('audioModeBtn').classList.toggle('active', mode === 'audio');
    
    if (videoUrlInput.value.trim()) {
        processVideo(); // Re-fetch with new mode
    }
}

// Modify server API call to support audio mode
const _originalProcessVideo = processVideo;
processVideo = async function() {
    const url = videoUrlInput.value.trim();
    if (!url) { showError('Please paste a video URL first.'); return; }
    
    try { new URL(url); } catch { showError('Invalid URL.'); return; }
    
    showLoading();
    
    try {
        const res = await fetch(`${API_URL}/api/info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, mode: currentMode })
        });
        
        const data = await res.json();
        
        if (!res.ok || data.error) {
            throw new Error(data.error || 'Could not fetch video info');
        }
        
        showResult(data, url);
    } catch (err) {
        console.error(err);
        showError(err.message || 'Server error.');
    }
};

// Save to Download History
function saveToHistory(title, url, quality, platform) {
    const item = {
        id: Date.now(),
        title: title.substring(0, 80),
        url,
        quality,
        platform: capitalize(platform || 'Unknown'),
        date: new Date().toISOString()
    };
    
    downloadHistory.unshift(item);
    if (downloadHistory.length > 20) downloadHistory = downloadHistory.slice(0, 20);
    
    localStorage.setItem('vidsave_history', JSON.stringify(downloadHistory));
    renderHistory();
}

// Render Download History
function renderHistory() {
    const section = document.getElementById('historySection');
    const list = document.getElementById('historyList');
    
    if (downloadHistory.length === 0) {
        section.classList.remove('hidden');
        list.innerHTML = `
            <div class="history-empty">
                <i class="fas fa-download"></i>
                <p>No downloads yet</p>
            </div>
        `;
        return;
    }
    
    section.classList.remove('hidden');
    list.innerHTML = downloadHistory.map(item => `
        <div class="history-item">
            <div class="history-item-left">
                <div class="history-icon"><i class="fas fa-${currentMode === 'audio' ? 'music' : 'video'}"></i></div>
                <div class="history-info">
                    <div class="history-title">${escapeHtml(item.title)}</div>
                    <div class="history-meta">${item.quality} · ${item.platform} · ${timeAgo(item.date)}</div>
                </div>
            </div>
            <div class="history-actions">
                <button class="history-action-btn" onclick="copyUrl('${encodeURIComponent(item.url)}')" title="Copy URL">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="history-action-btn" onclick="downloadFromHistory('${encodeURIComponent(item.url)}', '${item.quality}')" title="Download Again">
                    <i class="fas fa-download"></i>
                </button>
            </div>
        </div>
    `).join('');
}

// Clear History
function clearHistory() {
    if (confirm('Clear all download history?')) {
        downloadHistory = [];
        localStorage.removeItem('vidsave_history');
        renderHistory();
        document.getElementById('historySection').classList.add('hidden');
    }
}

// Copy URL
function copyUrl(encodedUrl) {
    const url = decodeURIComponent(encodedUrl);
    navigator.clipboard.writeText(url).then(() => {
        showToast('URL copied!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

// Download from History
function downloadFromHistory(encodedUrl, quality) {
    const url = decodeURIComponent(encodedUrl);
    videoUrlInput.value = url;
    processVideo();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Helper: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper: Time ago
function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}

// Modify showResult to add to history
const _originalShowResult = showResult;
const originalShowResult = showResult;

// Show download history on page load
if (downloadHistory.length > 0) {
    renderHistory();
}
