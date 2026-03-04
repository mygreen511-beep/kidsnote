#!/usr/bin/env python3
"""
키즈노트 백업 크롤러
- 알림장: 글 + 사진 + 날짜
- 앨범: 제목 + 글 + 사진 + 동영상 + 날짜
"""

import argparse
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

import requests

BASE_URL = "https://www.kidsnote.com/api"
LOGIN_URL = f"{BASE_URL}/web/login"
INFO_URL = f"{BASE_URL}/v1/me/info"
ALBUMS_URL = f"{BASE_URL}/v1_2/children/{{child_id}}/albums"
REPORTS_URL = f"{BASE_URL}/v1_2/children/{{child_id}}/reports/"


def sanitize_filename(name):
    """파일/폴더명에 사용할 수 없는 문자 제거"""
    name = name.replace('\n', ' ').replace('\r', ' ')
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > 200:
        name = name[:200]
    return name or 'untitled'


def extract_extension(url):
    """URL에서 파일 확장자 추출"""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    ext = os.path.splitext(path)[1].lower()
    if ext:
        return ext
    return '.jpg'


class KidsnoteBackup:
    def __init__(self, email, password, output_dir='kidsnote_backup', on_log=None, on_progress=None):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        })
        self.email = email
        self.password = password
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._on_log = on_log
        self._on_progress = on_progress
        self.cancelled = False

    def log(self, msg):
        if self._on_log:
            self._on_log(msg)
        else:
            print(msg)

    def progress(self, current, total, label=''):
        if self._on_progress:
            self._on_progress(current, total, label)
        elif current % 10 == 0 or current == total:
            print(f"  진행: {current}/{total} {label} 처리 완료")

    def login(self):
        """키즈노트 로그인"""
        self.log(f"[로그인] {self.email} 으로 로그인 중...")
        resp = self.session.post(LOGIN_URL, json={
            'username': self.email,
            'password': self.password,
            'remember_me': True,
        })

        if resp.status_code >= 400:
            try:
                err = resp.json()
                self.log(f"[오류] 로그인 실패: {err.get('err_code', resp.text)}")
            except Exception:
                self.log(f"[오류] 로그인 실패: HTTP {resp.status_code}")
            return False

        data = resp.json()
        session_id = data.get('session_id', '')
        if session_id:
            self.session.cookies.set('session_id', session_id, domain='.kidsnote.com')
        self.session.cookies.set('current_user', self.email, domain='www.kidsnote.com')

        # Content-Type 헤더 제거 (GET 요청 시 불필요)
        self.session.headers.pop('Content-Type', None)

        self.log("[로그인] 성공!")
        return True

    def get_children(self):
        """자녀 목록 조회"""
        self.log("\n[아이 목록] 조회 중...")
        resp = self.session.get(INFO_URL)
        resp.raise_for_status()
        data = resp.json()

        children = []
        for child in data.get('children', []):
            child_id = child['id']
            name = child.get('name', f'child_{child_id}')
            enrollments = child.get('enrollment', [])

            child_info = {
                'id': child_id,
                'name': name,
                'centers': [],
            }

            for enrollment in enrollments:
                center_id = enrollment.get('center_id')
                class_id = enrollment.get('belong_to_class')
                center_name = enrollment.get('center_name', f'center_{center_id}')
                class_name = enrollment.get('class_name', f'class_{class_id}')
                child_info['centers'].append({
                    'center_id': center_id,
                    'class_id': class_id,
                    'center_name': center_name,
                    'class_name': class_name,
                })

            children.append(child_info)
            self.log(f"  - {name} (ID: {child_id})")
            for c in child_info['centers']:
                self.log(f"    어린이집: {c['center_name']} / 반: {c['class_name']}")

        return children

    def download_file(self, url, filepath, max_retries=3):
        """파일 다운로드 (재시도 포함)"""
        filepath = Path(filepath)
        if filepath.exists() and filepath.stat().st_size > 0:
            return True

        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, stream=True, timeout=60)
                if resp.status_code == 200:
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return True
                else:
                    self.log(f"    [경고] 다운로드 실패 (HTTP {resp.status_code}): {url}")
            except Exception as e:
                self.log(f"    [경고] 다운로드 오류 (시도 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)

        self.log(f"    [오류] 다운로드 최종 실패: {url}")
        return False

    def fetch_all_pages(self, url, params=None):
        """페이지네이션 처리하여 모든 결과 수집"""
        all_results = []
        if params is None:
            params = {}

        params.setdefault('tz', 'Asia/Seoul')
        params.setdefault('page_size', '9999')

        try:
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            all_results = data.get('results', [])
        except Exception as e:
            self.log(f"  [오류] API 호출 실패: {e}")

        return all_results

    def backup_reports(self, child):
        """알림장 백업"""
        child_id = child['id']
        child_name = sanitize_filename(child['name'])
        self.log(f"\n[알림장] {child['name']}의 알림장을 백업합니다...")

        url = REPORTS_URL.format(child_id=child_id)
        reports = self.fetch_all_pages(url)
        self.total_reports = len(reports)

        self.log(f"  총 {len(reports)}개 알림장 발견")

        # 날짜별로 그룹핑 (같은 날짜에 여러 개일 수 있음)
        date_counts = {}

        for i, report in enumerate(reports):
            if self.cancelled:
                self.log("\n[중지] 사용자에 의해 백업이 중지되었습니다.")
                return

            report_id = report.get('id', i)
            created = report.get('created', '')
            content = report.get('content', '')
            author = report.get('author_name', '')
            title = report.get('title', '')
            images = report.get('attached_images', [])

            # 날짜 추출 (2021-03-15T09:00:00 → 2021-03-15)
            date_str = created[:10] if created else 'unknown_date'

            # 같은 날짜 카운트
            if date_str not in date_counts:
                date_counts[date_str] = 0
            date_counts[date_str] += 1
            count = date_counts[date_str]

            # 폴더명 결정
            if count > 1:
                folder_name = f"{date_str}_{count}"
            else:
                folder_name = date_str

            report_dir = self.output_dir / child_name / '알림장' / folder_name
            report_dir.mkdir(parents=True, exist_ok=True)

            # 텍스트 저장
            txt_path = report_dir / 'report.txt'
            if not txt_path.exists():
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"날짜: {created}\n")
                    if author:
                        f.write(f"작성자: {author}\n")
                    if title:
                        f.write(f"제목: {title}\n")
                    f.write(f"\n{'='*50}\n\n")
                    f.write(content or '(내용 없음)')
                    f.write('\n')

            # 이미지 다운로드
            for idx, img in enumerate(images, 1):
                img_url = img.get('original', '')
                if not img_url:
                    continue
                ext = extract_extension(img_url)
                img_path = report_dir / f"photo_{idx:03d}{ext}"
                self.download_file(img_url, img_path)

            # 동영상 다운로드
            video = report.get('attached_video')
            if video:
                video_url = video.get('high', '')
                if video_url:
                    ext = extract_extension(video_url)
                    video_path = report_dir / f"video{ext}"
                    self.download_file(video_url, video_path)

            self.progress(i + 1, len(reports), '알림장')

    def backup_albums(self, child):
        """앨범 백업"""
        child_id = child['id']
        child_name = sanitize_filename(child['name'])
        self.log(f"\n[앨범] {child['name']}의 앨범을 백업합니다...")

        url = ALBUMS_URL.format(child_id=child_id)
        albums = self.fetch_all_pages(url)
        self.total_albums = len(albums)

        self.log(f"  총 {len(albums)}개 앨범 발견")

        for i, album in enumerate(albums):
            if self.cancelled:
                self.log("\n[중지] 사용자에 의해 백업이 중지되었습니다.")
                return

            album_id = album.get('id', i)
            created = album.get('created', '')
            title = album.get('title', '')
            content = album.get('content', '')
            images = album.get('attached_images', [])

            # 날짜 추출
            date_str = created[:10] if created else 'unknown_date'

            # 폴더명: 날짜_제목
            title_clean = sanitize_filename(title) if title else str(album_id)
            folder_name = f"{date_str}_{title_clean}"

            album_dir = self.output_dir / child_name / '앨범' / folder_name
            album_dir.mkdir(parents=True, exist_ok=True)

            # 앨범 정보 텍스트 저장
            txt_path = album_dir / 'album_info.txt'
            if not txt_path.exists():
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"날짜: {created}\n")
                    f.write(f"제목: {title}\n")
                    f.write(f"\n{'='*50}\n\n")
                    f.write(content or '(내용 없음)')
                    f.write('\n')

            # 이미지 다운로드
            for idx, img in enumerate(images, 1):
                img_url = img.get('original', '')
                if not img_url:
                    continue
                ext = extract_extension(img_url)
                img_path = album_dir / f"photo_{idx:03d}{ext}"
                self.download_file(img_url, img_path)

            # 동영상 다운로드
            video = album.get('attached_video')
            if video:
                video_url = video.get('high', '')
                if video_url:
                    ext = extract_extension(video_url)
                    original_name = video.get('original_file_name', '')
                    if original_name:
                        video_path = album_dir / sanitize_filename(original_name)
                    else:
                        video_path = album_dir / f"video{ext}"
                    self.download_file(video_url, video_path)

            self.progress(i + 1, len(albums), '앨범')

    def run(self):
        """전체 백업 실행"""
        self.cancelled = False
        self.total_reports = 0
        self.total_albums = 0

        self.log("=" * 50)
        self.log("  키즈노트 백업 크롤러")
        self.log("=" * 50)

        if not self.login():
            return False

        children = self.get_children()
        if not children:
            self.log("[오류] 등록된 자녀가 없습니다.")
            return False

        for child in children:
            if self.cancelled:
                break
            self.backup_reports(child)
            if self.cancelled:
                break
            self.backup_albums(child)

        if not self.cancelled:
            self.log(f"\n{'='*50}")
            self.log(f"  백업 완료!")
            self.log(f"  알림장: {self.total_reports}개 | 앨범: {self.total_albums}개")
            self.log(f"  저장 위치: {self.output_dir.resolve()}")
            self.log(f"{'='*50}")

        return True


def main():
    parser = argparse.ArgumentParser(description='키즈노트 백업 크롤러')
    parser.add_argument('--email', required=True, help='키즈노트 이메일')
    parser.add_argument('--password', required=True, help='키즈노트 비밀번호')
    parser.add_argument('--output', default='kidsnote_backup', help='저장 경로 (기본: kidsnote_backup)')
    args = parser.parse_args()

    backup = KidsnoteBackup(args.email, args.password, args.output)
    backup.run()


if __name__ == '__main__':
    main()
