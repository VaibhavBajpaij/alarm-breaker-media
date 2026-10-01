#!/usr/bin/env python3
import os
import sys
import json
import hashlib
import subprocess
import datetime
import re
import argparse

def get_video_info(path):
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout:
        return None
    data = json.loads(res.stdout)
    vstream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), {})
    duration = float(data.get('format', {}).get('duration', 0))
    width = int(vstream.get('width', 0))
    height = int(vstream.get('height', 0))
    return {
        'duration': duration,
        'width': width,
        'height': height,
        'codec': vstream.get('codec_name', ''),
    }

def optimize_video(src_path, dst_path):
    cmd = [
        'ffmpeg', '-y', '-i', src_path,
        '-vf', 'scale=480:854:force_original_aspect_ratio=decrease,pad=480:854:(ow-iw)/2:(oh-ih)/2,setsar=1',
        '-c:v', 'libx264', '-crf', '28', '-preset', 'medium',
        '-c:a', 'aac', '-b:a', '96k',
        '-movflags', '+faststart',
        dst_path
    ]
    subprocess.run(cmd, check=True)

def generate_thumbnail(video_path, thumb_path):
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    cmd = [
        'ffmpeg', '-y', '-ss', '00:00:01', '-i', video_path,
        '-vf', 'scale=240:-1',
        '-q:v', '6',
        '-vframes', '1',
        thumb_path
    ]
    subprocess.run(cmd, check=True)

def sha256_checksum(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def optimize_all_media(base_dir):
    videos_dir = os.path.join(base_dir, 'videos')
    thumbs_dir = os.path.join(base_dir, 'thumbs')

    if not os.path.exists(videos_dir):
        print('No videos directory found.')
        return

    for category in sorted(os.listdir(videos_dir)):
        cat_dir = os.path.join(videos_dir, category)
        if not os.path.isdir(cat_dir):
            continue
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith('.mp4'):
                continue
            
            stem = fname[:-4]
            video_path = os.path.join(cat_dir, fname)
            thumb_path = os.path.join(thumbs_dir, category, f'{stem}.jpg')
            
            size_bytes = os.path.getsize(video_path)
            info = get_video_info(video_path)
            needs_reencode = False
            
            if size_bytes > 1.5 * 1024 * 1024:
                needs_reencode = True
            elif info and (info['width'] != 480 or info['height'] != 854):
                needs_reencode = True

            if needs_reencode:
                print(f'Re-encoding {category}/{fname} ({size_bytes/1024/1024:.2f} MB)...')
                temp_dst = video_path + '.tmp.mp4'
                try:
                    optimize_video(video_path, temp_dst)
                    os.replace(temp_dst, video_path)
                except Exception as e:
                    print(f'Error re-encoding {fname}: {e}')
                    if os.path.exists(temp_dst):
                        os.remove(temp_dst)

            if not os.path.exists(thumb_path):
                print(f'Generating thumbnail for {category}/{fname}...')
                try:
                    generate_thumbnail(video_path, thumb_path)
                except Exception as e:
                    print(f'Error generating thumbnail for {fname}: {e}')

def generate_catalog_json(base_dir, explicit_commit_sha=None):
    videos_dir = os.path.join(base_dir, 'videos')
    thumbs_dir = os.path.join(base_dir, 'thumbs')
    catalog_path = os.path.join(base_dir, 'catalog.json')

    existing_catalog = {'version': 0, 'videos': []}
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                existing_catalog = json.load(f)
        except Exception as e:
            print(f'Warning reading catalog: {e}')

    existing_map = {item['id']: item for item in existing_catalog.get('videos', [])}
    next_version = existing_catalog.get('version', 0) + 1

    active_items = []
    seen_ids = set()

    for category in sorted(os.listdir(videos_dir)):
        cat_dir = os.path.join(videos_dir, category)
        if not os.path.isdir(cat_dir):
            continue
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith('.mp4'):
                continue
            
            stem = fname[:-4]
            video_id = f'{category}_{stem}'
            seen_ids.add(video_id)

            video_path = os.path.join(cat_dir, fname)
            thumb_path = os.path.join(thumbs_dir, category, f'{stem}.jpg')
            
            size_bytes = os.path.getsize(video_path)
            info = get_video_info(video_path)

            lang = 'hi' if stem.endswith('_hi') else 'en'
            title_stem = stem[:-3] if stem.endswith('_hi') else stem
            title = ' '.join(word.capitalize() for word in title_stem.split('_'))

            sha256 = sha256_checksum(video_path)
            duration_s = round(info['duration'], 2) if info else 0.0

            raw_words = re.findall(r'[a-zA-Z0-9]+', f'{category} {title_stem}')
            tags = sorted(list(set(w.lower() for w in raw_words if w.lower() not in ['mp4', 'hi'])))

            active_items.append({
                'id': video_id,
                'category': category,
                'title': title,
                'lang': lang,
                'file': f'videos/{category}/{fname}',
                'thumb': f'thumbs/{category}/{stem}.jpg',
                'duration_s': duration_s,
                'size_bytes': size_bytes,
                'sha256': sha256,
                'tags': tags,
                'removed': False
            })

    all_videos = list(active_items)
    for old_id, old_item in existing_map.items():
        if old_id not in seen_ids:
            rem = dict(old_item)
            rem['removed'] = True
            all_videos.append(rem)

    all_videos.sort(key=lambda x: (x.get('category', ''), x.get('title', '')))

    # Determine commit SHA
    commit_sha = explicit_commit_sha or os.environ.get('GITHUB_SHA', 'main')
    if not explicit_commit_sha and commit_sha == 'main':
        try:
            res = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=base_dir, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                commit_sha = res.stdout.strip()
        except Exception:
            pass

    catalog_data = {
        'version': next_version,
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'commit': commit_sha,
        'videos': all_videos
    }

    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(catalog_data, f, indent=2)

    print(f'catalog.json generated successfully. Version: {next_version}, Commit: {commit_sha}, Count: {len(all_videos)}')

def main():
    parser = argparse.ArgumentParser(description='Build Video Catalog and Optimize Media')
    parser.add_argument('--optimize-only', action='store_true', help='Only optimize videos and generate thumbnails')
    parser.add_argument('--catalog-only', action='store_true', help='Only generate catalog.json')
    parser.add_argument('--commit-sha', type=str, default=None, help='Explicit commit SHA to embed in catalog.json')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.optimize_only:
        optimize_all_media(base_dir)
    elif args.catalog_only:
        generate_catalog_json(base_dir, explicit_commit_sha=args.commit_sha)
    else:
        optimize_all_media(base_dir)
        generate_catalog_json(base_dir, explicit_commit_sha=args.commit_sha)

if __name__ == '__main__':
    main()
