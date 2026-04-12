"""
Video Downloader with Cloud Storage
Downloads videos and uploads to cloud storage
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import threading
import time
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_FOLDER = 'downloads'
CLOUD_FOLDER = 'cloud_storage'  # Simulated cloud folder
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(CLOUD_FOLDER):
    os.makedirs(CLOUD_FOLDER)

# Store download jobs
jobs = {}

def get_platform(url):
    """Detect platform from URL"""
    domain = urlparse(url).netloc.lower()
    
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return 'youtube'
    elif 'facebook.com' in domain or 'fb.watch' in domain:
        return 'facebook'
    elif 'instagram.com' in domain:
        return 'instagram'
    elif 'tiktok.com' in domain:
        return 'tiktok'
    elif 'twitter.com' in domain or 'x.com' in domain:
        return 'twitter'
    return None

def download_and_upload(job_id, url, format_id):
    """Background task: Download video and move to cloud storage"""
    try:
        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['progress'] = 10
        
        # Download video
        video_id = str(uuid.uuid4())[:8]
        temp_path = os.path.join(DOWNLOAD_FOLDER, f'temp_{video_id}.mp4')
        
        ydl_opts = {
            'format': format_id if format_id else 'best',
            'outtmpl': temp_path,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail', '')
        
        jobs[job_id]['status'] = 'uploading'
        jobs[job_id]['progress'] = 70
        jobs[job_id]['title'] = title
        
        # Move to cloud storage (simulated)
        cloud_filename = f"{job_id}_{title[:50].replace(' ', '_')}.mp4"
        cloud_path = os.path.join(CLOUD_FOLDER, cloud_filename)
        
        # In real implementation, upload to Google Drive/AWS S3 here
        # For now, just move to cloud folder
        os.rename(temp_path, cloud_path)
        
        # Generate download URL
        download_url = f"/api/cloud/download/{job_id}"
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['download_url'] = download_url
        jobs[job_id]['cloud_path'] = cloud_path
        jobs[job_id]['file_size'] = os.path.getsize(cloud_path)
        jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        print(f"✅ Job {job_id} completed: {title}")
        
    except Exception as e:
        print(f"❌ Job {job_id} failed: {str(e)}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)

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
        
        ydl_opts = {'quiet': True, 'no_warnings': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({
                        'format_id': f.get('format_id'),
                        'quality': f.get('quality_label') or f.get('height', 'unknown'),
                        'ext': f.get('ext'),
                        'filesize': f.get('filesize') or f.get('filesize_approx', 0)
                    })
            
            # Sort and get unique qualities
            formats.sort(key=lambda x: x.get('quality', ''), reverse=True)
            seen = set()
            unique_formats = []
            for f in formats:
                quality = f.get('quality', '')
                if quality and quality not in seen:
                    seen.add(quality)
                    unique_formats.append(f)
            
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'platform': platform,
                'formats': unique_formats[:5]
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cloud/download', methods=['POST'])
def start_cloud_download():
    """Start background download to cloud"""
    try:
        data = request.get_json()
        url = data.get('url')
        format_id = data.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
        
        # Create job
        job_id = str(uuid.uuid4())[:12]
        jobs[job_id] = {
            'id': job_id,
            'url': url,
            'format_id': format_id,
            'status': 'queued',
            'progress': 0,
            'created_at': datetime.now().isoformat()
        }
        
        # Start background download
        thread = threading.Thread(
            target=download_and_upload,
            args=(job_id, url, format_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': 'Download started in background'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cloud/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get download job status"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id].copy()
    
    # Convert file size to human readable
    if 'file_size' in job:
        size = job['file_size']
        if size > 1024*1024*1024:
            job['file_size_human'] = f"{size/(1024*1024*1024):.2f} GB"
        elif size > 1024*1024:
            job['file_size_human'] = f"{size/(1024*1024):.2f} MB"
        else:
            job['file_size_human'] = f"{size/1024:.2f} KB"
    
    return jsonify(job)

@app.route('/api/cloud/download/<job_id>', methods=['GET'])
def download_from_cloud(job_id):
    """Download video from cloud storage"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Download not ready'}), 400
    
    cloud_path = job.get('cloud_path')
    if not cloud_path or not os.path.exists(cloud_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        cloud_path,
        as_attachment=True,
        download_name=os.path.basename(cloud_path)
    )

@app.route('/api/cloud/jobs', methods=['GET'])
def list_jobs():
    """List all download jobs"""
    return jsonify({
        'jobs': list(jobs.values())
    })

@app.route('/api/cloud/stream/<job_id>', methods=['GET'])
def stream_video(job_id):
    """Stream video (for website-like experience)"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Video not ready'}), 400
    
    cloud_path = job.get('cloud_path')
    if not cloud_path or not os.path.exists(cloud_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Stream video (for website playback)
    return send_file(cloud_path, mimetype='video/mp4')

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    return jsonify({
        'platforms': ['youtube', 'facebook', 'instagram', 'tiktok', 'twitter']
    })

if __name__ == '__main__':
    print("☁️  Cloud Video Downloader Server")
    print("=" * 50)
    print("Features:")
    print("  • Background downloads")
    print("  • Cloud storage simulation")
    print("  • Download from cloud")
    print("  • Video streaming")
    print("=" * 50)
    print("\n🌐 Open: http://localhost:5000")
    print()
    app.run(host='0.0.0.0', port=5000, debug=True)
