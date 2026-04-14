from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import uuid
import shutil
from urllib.parse import urlparse, quote

# Serve frontend files from same directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

# Downloads folder
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

def get_platform(url):
    """Detect platform from URL"""
    domain = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return 'youtube'
    elif 'facebook.com' in domain or 'fb.watch' in domain:
        return 'facebook'
    elif 'instagram.com' in domain:
        # Support: /p/, /reel/, /reels/, /tv/
        if '/p/' in path or '/reel' in path or '/tv/' in path:
            return 'instagram'
        return 'instagram'  # Default to instagram for any instagram.com URL
    elif 'tiktok.com' in domain or 'vm.tiktok.com' in domain:
        return 'tiktok'
    elif 'twitter.com' in domain or 'x.com' in domain:
        return 'twitter'
    elif 'pinterest.' in domain or 'pin.it' in domain:
        return 'pinterest'
    elif 'reddit.com' in domain or 'redd.it' in domain:
        return 'reddit'
    # Dailymotion removed
    elif 'vimeo.com' in domain or 'player.vimeo.com' in domain:
        return 'vimeo'
    elif 'twitch.tv' in domain or 'clips.twitch.tv' in domain:
        # Support videos, clips, and highlights
        return 'twitch'
    return None

@app.route('/api/info', methods=['POST'])
def get_video_info():
    """Get video information"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
        
        platform = get_platform(url)
        if not platform:
            return jsonify({'error': 'Unsupported platform'}), 400
        
        # Configure yt-dlp with platform-specific options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        # Platform-specific options
        if platform == 'reddit':
            # Reddit needs proper user-agent and network settings
            ydl_opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ydl_opts['retries'] = 3
            ydl_opts['fragment_retries'] = 3
            ydl_opts['extractor_retries'] = 3
            # Reddit often has limited formats, use best available
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
        elif platform == 'twitch':
            ydl_opts['extractor_args'] = {'twitch': {'skip_ads': 'True'}}
        elif platform == 'vimeo':
            ydl_opts['referer'] = 'https://vimeo.com/'
        elif platform == 'pinterest':
            # Pinterest needs special handling - use best format only
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
        # Dailymotion removed
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get available formats with proper quality labels
            formats = []
            for f in info.get('formats', []):
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                height = f.get('height')

                if not vcodec or vcodec == 'none' or not f.get('url'):
                    continue

                quality_label = f.get('quality_label')
                if not quality_label and height:
                    quality_label = f'{height}p'
                elif not quality_label:
                    quality_label = f.get('format_note', 'unknown')

                formats.append({
                    'format_id': f.get('format_id'),
                    'quality': quality_label,
                    'height': height or 0,
                    'ext': f.get('ext', 'mp4'),
                    'filesize': f.get('filesize') or f.get('filesize_approx', 0),
                    'has_audio': acodec != 'none'
                })
            
            # Sort by height (highest first), then prefer audio-enabled formats
            formats.sort(key=lambda x: (x.get('height', 0), x.get('has_audio', False)), reverse=True)
            
            # Get unique qualities (keep highest-quality/audio-enabled first)
            seen = set()
            unique_formats = []
            for f in formats:
                quality = f.get('quality', '')
                if quality and quality not in seen:
                    seen.add(quality)
                    unique_formats.append(f)
            
            # If no formats found, add a 'best' option
            if not unique_formats:
                unique_formats = [{'format_id': 'best', 'quality': 'Best', 'ext': 'mp4', 'has_audio': True}]
            
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'platform': platform,
                'formats': unique_formats[:6]  # Top 6 qualities
            })
            
    except Exception as e:
        print(f"Error in /api/info: {str(e)}")
        print(f"URL: {data.get('url', 'N/A')}")
        print(f"Platform: {platform if 'platform' in locals() else 'N/A'}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to fetch video info: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Get direct video URL and redirect - NO server storage, instant download"""
    try:
        data = request.get_json()
        url = data.get('url')
        format_id = data.get('format_id', 'best')
        has_audio = data.get('has_audio', True)
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
        
        print(f"Downloading video for: {url} | format: {format_id} | has_audio: {has_audio}")
        
        # Detect platform
        platform = get_platform(url)
        has_ffmpeg = shutil.which('ffmpeg') is not None

        # Build format spec for the chosen quality
        if not format_id or format_id == 'best':
            format_spec = 'best'
        elif format_id.isdigit() and len(format_id) <= 4:
            format_spec = format_id
        else:
            # If user selected a named quality like '1080p', use the matching height selector
            try:
                height = int(format_id.replace('p', ''))
                format_spec = f'bestvideo[height<={height}]+bestaudio/best' if has_ffmpeg else f'bestvideo[height<={height}]'
            except:
                format_spec = 'best'

        # Platform-specific download options
        ydl_opts = {
            'format': format_spec,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        if platform == 'reddit':
            # Reddit needs proper user-agent and network settings
            ydl_opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ydl_opts['retries'] = 3
            ydl_opts['fragment_retries'] = 3
            ydl_opts['extractor_retries'] = 3
            if not format_id or format_id == 'best':
                ydl_opts['format'] = 'best'
        elif platform == 'twitch':
            ydl_opts['extractor_args'] = {'twitch': {'skip_ads': 'True'}}
        elif platform == 'vimeo':
            ydl_opts['referer'] = 'https://vimeo.com/'
        elif platform == 'pinterest':
            if not format_id or format_id == 'best':
                ydl_opts['format'] = 'best'
        # Dailymotion removed
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            direct_url = None

            if info.get('url'):
                direct_url = info['url']
            elif info.get('formats'):
                # Try to match the requested format first
                for f in info['formats']:
                    if f.get('format_id') == format_id and f.get('url'):
                        direct_url = f['url']
                        break

                # fallback: choose first usable format
                if not direct_url:
                    for f in info['formats']:
                        if f.get('url') and f.get('vcodec', 'none') != 'none' and (has_audio or f.get('acodec', 'none') != 'none'):
                            direct_url = f['url']
                            break

        if not direct_url:
            return jsonify({'error': 'Could not get direct video URL'}), 500

        safe_title = title[:60].replace('/', '_').replace('\\', '_')
        return jsonify({
            'direct_url': direct_url,
            'title': safe_title,
            'filename': f'{safe_title}.mp4'
        })
        
    except Exception as e:
        print(f"Error in /api/download: {str(e)}")
        print(f"URL: {data.get('url', 'N/A')}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/download/file/<path:filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    """Get supported platforms"""
    return jsonify({
        'platforms': ['youtube', 'facebook', 'instagram', 'tiktok', 'twitter', 'pinterest', 'reddit', 'vimeo', 'twitch']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False') == 'True'
    
    print("🚀 Video Downloader Server Starting...")
    print("📁 Downloads folder:", os.path.abspath(DOWNLOAD_FOLDER))
    print(f"🌐 Open: http://localhost:{port}")
    print(f"🔧 Debug mode: {debug}")
    print("\n⚠️  Make sure you have Python and yt-dlp installed:")
    print("   pip install flask flask-cors yt-dlp")
    print()
    app.run(host='0.0.0.0', port=port, debug=debug)
