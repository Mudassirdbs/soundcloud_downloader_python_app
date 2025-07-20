from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import yt_dlp
import os
import uuid
import requests
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Store download status and cleanup old files
download_status = {}
file_cleanup_interval = 3600  # 1 hour

def cleanup_old_files():
    """Remove files older than 1 hour"""
    while True:
        try:
            current_time = datetime.now()
            for filename in os.listdir(DOWNLOAD_DIR):
                file_path = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if current_time - file_time > timedelta(hours=1):
                        os.remove(file_path)
                        print(f"Cleaned up old file: {filename}")
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        time.sleep(file_cleanup_interval)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def download_soundcloud_track(url, track_id):
    """Download SoundCloud track using yt-dlp"""
    try:
        t0 = time.time()
        audio_out = os.path.join(DOWNLOAD_DIR, f"{track_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': audio_out,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # Lowered from 192 for faster conversion
            }],
            'quiet': True,
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        t1 = time.time()
        print(f"Audio download/conversion took {t1 - t0:.2f} seconds")
        
        # Get track info
        title = info.get('title', 'Unknown Track')
        thumbnail_url = info.get('thumbnail')
        
        # Download cover image if available
        cover_path = None
        cover_ext = None
        if thumbnail_url:
            try:
                img_ext = thumbnail_url.split('.')[-1].split('?')[0]
                if img_ext.lower() in ['jpg', 'jpeg', 'png', 'webp']:
                    cover_ext = img_ext
                else:
                    cover_ext = 'jpg'
                
                cover_path = os.path.join(DOWNLOAD_DIR, f"{track_id}_cover.{cover_ext}")
                response = requests.get(thumbnail_url, timeout=5)  # Lowered timeout from 30 to 5 seconds
                response.raise_for_status()
                
                with open(cover_path, 'wb') as f:
                    f.write(response.content)
            except Exception as e:
                print(f"Error downloading cover: {e}")
                cover_path = None
                cover_ext = None
        t2 = time.time()
        print(f"Cover download took {t2 - t1:.2f} seconds")
        
        mp3_path = os.path.join(DOWNLOAD_DIR, f"{track_id}.mp3")
        
        return {
            'success': True,
            'title': title,
            'mp3_path': mp3_path,
            'cover_path': cover_path,
            'cover_ext': cover_ext,
            'thumbnail_url': thumbnail_url
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/')
def index():
    """Serve the frontend HTML"""
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SoundCloud MP3 Downloader</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #fff;
            min-height: 100vh;
            margin: 0;
            padding: 0;
        }
        .main-container {
            max-width: 900px;
            margin: 40px auto;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.08);
            padding: 40px 30px 30px 30px;
            text-align: center;
        }
        .title {
            font-size: 2.8rem;
            font-weight: 700;
            color: #222;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #444;
            font-size: 1.2rem;
            margin-bottom: 30px;
        }
        .input-row {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0;
            margin-bottom: 30px;
            position: relative;
        }
        .spinner {
            display: none;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 28px;
            height: 28px;
            border: 3px solid #ffb199;
            border-top: 3px solid #ff3c00;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            z-index: 2;
        }
        @keyframes spin {
            0% { transform: translate(-50%, -50%) rotate(0deg); }
            100% { transform: translate(-50%, -50%) rotate(360deg); }
        }
        .url-input {
            flex: 1;
            padding: 16px 18px;
            font-size: 1.1rem;
            border: 1.5px solid #ddd;
            border-radius: 8px 0 0 8px;
            outline: none;
        }
        .copy-btn {
            background: #fff;
            border: 1.5px solid #ddd;
            border-left: none;
            padding: 0 16px;
            font-size: 1.2rem;
            cursor: pointer;
            border-radius: 0;
            height: 48px;
        }
        .download-btn {
            background: #ff3c00;
            color: #fff;
            border: none;
            padding: 0 32px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 0 8px 8px 0;
            cursor: pointer;
            height: 48px;
            transition: background 0.2s;
        }
        .download-btn:disabled {
            background: #ffb199;
            cursor: not-allowed;
        }
        .song-info-box {
            display: none;
            margin: 40px auto 0 auto;
            background: #f7fbfa;
            border-radius: 16px;
            padding: 40px 30px 10px 30px;
            max-width: 90%;
            box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        }
        .song-info-centered {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 30px;
        }
        .song-cover {
            width: 180px;
            height: 180px;
            border-radius: 16px;
            object-fit: cover;
            box-shadow: 0 4px 16px rgba(0,0,0,0.10);
            margin-bottom: 18px;
        }
        .song-title {
            font-size: 1.3rem;
            font-weight: 600;
            color: #222;
            margin-bottom: 6px;
            text-align: center;
        }
        .song-meta {
            color: #666;
            font-size: 1rem;
            text-align: center;
        }
        .song-list-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 0 18px 0;
            border-top: 1px solid #eee;
            border-bottom: 1px solid #eee;
            margin-top: 18px;
        }
        .song-list-index {
            color: #ff3c00;
            font-weight: 700;
            font-size: 1.1rem;
            margin-right: 10px;
        }
        .song-list-title {
            color: #ff3c00;
            font-size: 1.1rem;
            font-weight: 500;
            flex: 1;
            text-align: left;
        }
        .song-list-meta {
            color: #888;
            font-size: 1rem;
            margin-left: 10px;
        }
        .song-list-download-btn {
            background: #ff3c00;
            color: #fff;
            border: none;
            padding: 10px 32px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .song-list-download-btn:disabled {
            background: #ffb199;
            cursor: not-allowed;
        }
        .progress-section {
            display: none;
            margin-top: 30px;
        }
        .progress-bar {
            width: 100%;
            background: #eee;
            border-radius: 8px;
            overflow: hidden;
            height: 18px;
            margin-bottom: 10px;
        }
        .progress-inner {
            height: 100%;
            background: linear-gradient(90deg, #ff3c00 60%, #ffb199 100%);
            width: 0%;
            transition: width 0.4s;
        }
        .progress-label {
            color: #444;
            font-size: 1rem;
        }
        .final-buttons {
            display: none;
            flex-direction: column;
            gap: 18px;
            margin-top: 30px;
        }
        .final-btn {
            background: #ff3c00;
            color: #fff;
            border: none;
            padding: 18px 0;
            font-size: 1.2rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        }
        .final-btn:hover {
            background: #d12e00;
        }
        .error {
            background: #ff6b6b;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }
        .fetch-progress-bar {
            width: 60%;
            margin: 24px auto 0 auto;
            background: #e8f1ef;
            border-radius: 8px;
            height: 14px;
            overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03);
            display: none;
        }
        .fetch-progress-inner {
            height: 100%;
            background: linear-gradient(90deg, #ff3c00 60%, #ffb199 100%);
            width: 1%;
            transition: width 0.3s;
        }
        @media (max-width: 600px) {
            .main-container {
                padding: 18px 4px 18px 4px;
            }
            .song-info-centered {
                flex-direction: column;
                gap: 12px;
            }
            .song-cover {
                width: 100px;
                height: 100px;
            }
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div id="mainState">
            <div class="title">SoundCloud MP3 Downloader</div>
            <div class="subtitle">Download SoundCloud to MP3 Online for Free - Works on All Devices</div>
            <div class="input-row">
                <input type="text" class="url-input" id="urlInput" placeholder="Paste SoundCloud URL" autocomplete="off">
                <button class="copy-btn" onclick="copyUrl()" title="Copy" id="copyBtn"><span>📋</span></button>
                <button class="download-btn" id="fetchBtn" onclick="fetchSong()">Download</button>
                <div class="spinner" id="fetchSpinner"></div>
            </div>
        </div>
        <div class="song-info-box" id="songInfoBox">
            <div class="song-info-centered">
                <img src="" alt="Cover" class="song-cover" id="songCover" style="display:none;">
                <div class="song-title" id="songTitle"></div>
                <div class="song-meta" id="songMeta"></div>
                <div class="fetch-progress-bar" id="fetchProgressBar">
                    <div class="fetch-progress-inner" id="fetchProgressInner"></div>
                </div>
            </div>
            <div class="song-list-row">
                <span class="song-list-index">1:</span>
                <span class="song-list-title" id="songListTitle"></span>
                <span class="song-list-meta" id="songListMeta"></span>
                <button class="song-list-download-btn" id="songListDownloadBtn" onclick="startDownload()">Download</button>
            </div>
        </div>
        <div class="progress-section" id="progressSection">
            <div class="progress-bar">
                <div class="progress-inner" id="progressInner"></div>
            </div>
            <div class="progress-label" id="progressLabel">Downloading...</div>
        </div>
        <div class="final-buttons" id="finalButtons">
            <button class="final-btn" id="mp3Btn">Download Mp3</button>
            <button class="final-btn" id="coverBtn">Download Cover [HD]</button>
            <button class="final-btn" id="anotherBtn">Download Another Song</button>
        </div>
        <div class="error" id="error"></div>
    </div>
    <script>
        let songData = null;
        let fetchProgressInterval = null;
        function copyUrl() {
            const urlInput = document.getElementById('urlInput');
            urlInput.select();
            document.execCommand('copy');
        }
        function showError(msg) {
            const err = document.getElementById('error');
            err.textContent = msg;
            err.style.display = 'block';
        }
        function hideError() {
            document.getElementById('error').style.display = 'none';
        }
        function setFetchingState(isFetching) {
            document.getElementById('urlInput').disabled = isFetching;
            document.getElementById('fetchBtn').disabled = isFetching;
            document.getElementById('copyBtn').disabled = isFetching;
            document.getElementById('fetchSpinner').style.display = isFetching ? 'block' : 'none';
        }
        function resetUI() {
            document.getElementById('mainState').style.display = '';
            document.getElementById('songInfoBox').style.display = 'none';
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('finalButtons').style.display = 'none';
            setFetchingState(false);
            stopFetchProgressBar();
            hideError();
            document.getElementById('urlInput').value = '';
        }
        function animateFetchProgressBar() {
            const bar = document.getElementById('fetchProgressBar');
            const inner = document.getElementById('fetchProgressInner');
            bar.style.display = 'block';
            let progress = 1;
            inner.style.width = progress + '%';
            if (fetchProgressInterval) clearInterval(fetchProgressInterval);
            fetchProgressInterval = setInterval(() => {
                // Increase progress, slow down as it approaches 95%
                if (progress < 80) {
                    progress += Math.random() * 8 + 2;
                } else if (progress < 95) {
                    progress += Math.random() * 2 + 0.5;
                } else {
                    progress += Math.random() * 0.5;
                }
                if (progress > 99) progress = 99;
                inner.style.width = progress + '%';
            }, 180);
        }
        function stopFetchProgressBar() {
            const bar = document.getElementById('fetchProgressBar');
            const inner = document.getElementById('fetchProgressInner');
            if (fetchProgressInterval) clearInterval(fetchProgressInterval);
            inner.style.width = '100%';
            setTimeout(() => {
                bar.style.display = 'none';
                inner.style.width = '1%';
            }, 400);
        }
        function fetchSong() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url) {
                showError('Please enter a SoundCloud URL');
                return;
            }
            if (!url.includes('soundcloud.com')) {
                showError('Please enter a valid SoundCloud URL');
                return;
            }
            hideError();
            setFetchingState(true);
            document.getElementById('mainState').style.display = 'none';
            document.getElementById('songInfoBox').style.display = 'block';
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('finalButtons').style.display = 'none';
            // Hide cover and meta, show only fetching text
            document.getElementById('songCover').style.display = 'none';
            document.getElementById('songTitle').textContent = 'Fetching track info...';
            document.getElementById('songTitle').style.display = 'block';
            document.getElementById('songMeta').textContent = '';
            document.getElementById('songMeta').style.display = 'none';
            document.getElementById('songListTitle').textContent = '';
            document.getElementById('songListMeta').textContent = '';
            document.getElementById('songListDownloadBtn').disabled = true;
            animateFetchProgressBar();
            fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            })
            .then(res => res.json())
            .then(data => {
                setFetchingState(false);
                stopFetchProgressBar();
                if (data.success) {
                    songData = data;
                    // Show cover, title, meta
                    if (data.cover_url) {
                        document.getElementById('songCover').src = data.cover_url;
                        document.getElementById('songCover').style.display = '';
                    } else {
                        document.getElementById('songCover').style.display = 'none';
                    }
                    document.getElementById('songTitle').textContent = data.title;
                    document.getElementById('songTitle').style.display = 'block';
                    document.getElementById('songMeta').textContent = '';
                    document.getElementById('songMeta').style.display = 'block';
                    document.getElementById('songListTitle').textContent = data.title;
                    document.getElementById('songListMeta').textContent = '';
                    document.getElementById('songListDownloadBtn').disabled = false;
                } else {
                    showError(data.error || 'Failed to fetch track');
                    resetUI();
                }
            })
            .catch(() => {
                setFetchingState(false);
                stopFetchProgressBar();
                showError('Network error. Please try again.');
                resetUI();
            });
        }
        function startDownload() {
            if (!songData) return;
            document.getElementById('songInfoBox').style.display = 'none';
            document.getElementById('progressSection').style.display = 'block';
            document.getElementById('finalButtons').style.display = 'none';
            document.getElementById('progressInner').style.width = '0%';
            document.getElementById('progressLabel').textContent = 'Downloading...';
            // Simulate progress (since real progress is not available)
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 20 + 10;
                if (progress > 100) progress = 100;
                document.getElementById('progressInner').style.width = progress + '%';
                if (progress >= 100) {
                    clearInterval(interval);
                    setTimeout(showFinalButtons, 400);
                }
            }, 400);
        }
        function showFinalButtons() {
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('finalButtons').style.display = 'flex';
        }
        document.getElementById('mp3Btn').onclick = function() {
            if (songData) {
                window.location.href = `/download_file/${songData.track_id}.mp3`;
            }
        };
        document.getElementById('coverBtn').onclick = function() {
            if (songData && songData.cover_ext) {
                window.location.href = `/download_file/${songData.track_id}_cover.${songData.cover_ext}`;
            }
        };
        document.getElementById('anotherBtn').onclick = function() {
            songData = null;
            resetUI();
        };
        document.getElementById('urlInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                fetchSong();
            }
        });
        // Autofocus
        document.getElementById('urlInput').focus();
        // On load, reset UI
        resetUI();
    </script>
</body>
</html>'''
    return render_template_string(html_content)

@app.route('/download', methods=['POST'])
def download():
    """Handle download requests"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'error': 'URL is required'})
        
        if 'soundcloud.com' not in url:
            return jsonify({'success': False, 'error': 'Please provide a valid SoundCloud URL'})
        
        # Generate unique track ID
        track_id = str(uuid.uuid4())[:8]
        
        # Download the track
        result = download_soundcloud_track(url, track_id)
        
        if result['success']:
            response_data = {
                'success': True,
                'track_id': track_id,
                'title': result['title'],
                'cover_url': result['thumbnail_url'],
                'cover_ext': result['cover_ext']
            }
            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'error': result['error']})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/download_file/<filename>')
def download_file(filename):
    """Serve downloaded files"""
    try:
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("🎵 SoundCloud Downloader Server Starting...")
    print(f"📁 Downloads will be saved to: {os.path.abspath(DOWNLOAD_DIR)}")
    print("🌐 Server will be available at: http://localhost:5000")
    print("🧹 File cleanup: Files older than 1 hour will be automatically deleted")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
            