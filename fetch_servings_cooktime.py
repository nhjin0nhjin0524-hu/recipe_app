"""
YouTube API로 영상 설명에서 servings(인분), cook_time_min(조리시간), thumbnail_url 추출
"""

import re
import time
import mysql.connector
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fetch_servings.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}
API_KEY = "AIzaSyCTBxexae6DsYs0yClBJe3_m2zwFlgpgW8"

# ── 인분 추출 패턴 ──
SERVING_PATTERNS = [
    r'(\d+)\s*인분',                      # 2인분
    r'(\d+)\s*명\s*분',                   # 2명분
    r'serving[s]?\s*[:\-]?\s*(\d+)',      # servings: 2
    r'(\d+)\s*people',
    r'for\s*(\d+)',
]

# ── 조리시간 추출 패턴 ──
# 우선순위: 명시적 "조리시간" 레이블 > "완성/컷" 표현 > 제목 기반
COOKTIME_PATTERNS = [
    # 레이블 명시 (가장 신뢰도 높음)
    r'조리\s*시간\s*[:\-]?\s*(\d+)\s*시간\s*(\d+)\s*분',  # 조리시간: 1시간 30분
    r'조리\s*시간\s*[:\-]?\s*(\d+)\s*시간',               # 조리시간: 1시간
    r'조리\s*시간\s*[:\-]?\s*(\d+)\s*분',                 # 조리시간: 30분
    r'요리\s*시간\s*[:\-]?\s*(\d+)\s*시간\s*(\d+)\s*분',
    r'요리\s*시간\s*[:\-]?\s*(\d+)\s*분',
    r'총\s*조리\s*시간\s*[:\-]?\s*(\d+)\s*분',
    r'소요\s*시간\s*[:\-]?\s*(\d+)\s*시간\s*(\d+)\s*분',
    r'소요\s*시간\s*[:\-]?\s*(\d+)\s*분',
    r'cooking\s*time\s*[:\-]?\s*(\d+)\s*min',
    r'prep\s*(?:time\s*)?[:\-]?\s*(\d+)\s*min',
    r'total\s*time\s*[:\-]?\s*(\d+)\s*min',
    # "N분 완성/만에/컷" 표현
    r'(\d+)\s*시간\s*(\d+)\s*분\s*(?:완성|소요|만에|컷)',  # 1시간 30분 완성
    r'(\d+)\s*시간\s*(?:완성|소요|만에)',                   # 1시간 완성
    r'(\d+)\s*분\s*(?:완성|만에|컷|이면|이내|요리)',         # 30분 완성, 30분 컷
    # "총/약 N분 소요/걸림"
    r'(?:총|약)\s*(\d+)\s*분\s*(?:소요|걸립|이면|정도)',
    # 초 단위 (N초 → 분 변환은 parse_cooktime에서 처리)
    r'(\d+)\s*초\s*(?:완성|만에|컷)',                       # 90초 완성
    # 영상 설명 첫줄 재료/시간 테이블 형식
    r'시간\s*[:\|]\s*(\d+)\s*분',
    r'time\s*[:\|]\s*(\d+)',
]


def parse_servings(text: str):
    for pat in SERVING_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 20:  # 비상식적인 값 제외
                return val
    return None


TITLE_COOKTIME_PATTERNS = [
    r'(\d+)\s*시간\s*(\d+)\s*분',       # 1시간 30분
    r'(\d+)\s*시간',                    # 1시간
    r'(\d+)\s*분',                      # 30분 (제목에 단독 등장)
    r'(\d+)\s*초',                      # 90초
]

def parse_cooktime_from_title(title: str):
    """제목에서 조리시간 추출 (패턴이 단독으로 쓰인 경우만)"""
    # "N분" 이 제목에 있으면서 요리 관련 키워드와 함께 있는 경우
    if re.search(r'(\d+)\s*분\s*(라볶이|요리|반찬|국|찌개|볶음|무침|완성|컷|만에|이면|으로)', title):
        m = re.search(r'(\d+)\s*분', title)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 120:
                return val
    if re.search(r'(\d+)\s*초\s*(완성|만에|컷)', title):
        m = re.search(r'(\d+)\s*초', title)
        if m:
            val = round(int(m.group(1)) / 60)
            return max(val, 1)
    if re.search(r'(\d+)\s*시간\s*(\d+)\s*분', title):
        m = re.search(r'(\d+)\s*시간\s*(\d+)\s*분', title)
        if m:
            total = int(m.group(1)) * 60 + int(m.group(2))
            if 1 <= total <= 360:
                return total
    return None


def parse_cooktime(text: str):
    for pat in COOKTIME_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g is not None]
            matched_str = m.group(0)

            # 초 단위 패턴 (90초 완성 등)
            if '초' in matched_str:
                total = round(int(groups[0]) / 60)
                total = max(total, 1)
            # 시간 단위만 (1시간 완성)
            elif len(groups) == 1 and ('시간' in matched_str and '분' not in matched_str):
                total = int(groups[0]) * 60
            # 시간 + 분 (1시간 30분)
            elif len(groups) == 2:
                total = int(groups[0]) * 60 + int(groups[1])
            else:
                total = int(groups[0])

            if 1 <= total <= 360:  # 1분~6시간 범위
                return total
    return None


def fetch_video_details(api_key: str, video_ids: list) -> dict:
    """YouTube API로 batch 요청 (50개씩)"""
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", developerKey=api_key)
    except Exception as e:
        log.error(f"YouTube API 빌드 실패: {e}")
        return {}

    results = {}
    for i in range(0, len(video_ids), 50):
        batch = [vid for vid in video_ids[i:i+50] if vid and vid != '#NAME?']
        if not batch:
            continue
        try:
            resp = yt.videos().list(
                part="snippet",
                id=",".join(batch),
                maxResults=50
            ).execute()
            for item in resp.get("items", []):
                vid = item["id"]
                snippet = item["snippet"]
                results[vid] = {
                    "description": snippet.get("description", ""),
                    "thumbnail": (
                        snippet.get("thumbnails", {}).get("maxres", {}).get("url") or
                        snippet.get("thumbnails", {}).get("high", {}).get("url") or
                        snippet.get("thumbnails", {}).get("medium", {}).get("url") or
                        snippet.get("thumbnails", {}).get("default", {}).get("url")
                    )
                }
            log.info(f"  {i}~{i+len(batch)}번째 배치: {len(resp.get('items',[]))}개 수신")
            time.sleep(0.2)
        except Exception as e:
            log.warning(f"  배치 {i} 실패: {e}")
    return results


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        log.info("DB 연결 성공")
    except Exception as e:
        log.error(f"DB 연결 실패: {e}")
        return

    # video_id 목록 로드
    cur.execute("SELECT id, title, external_id FROM recipes WHERE external_id IS NOT NULL AND external_id != '#NAME?'")
    recipes = cur.fetchall()
    log.info(f"처리 대상 레시피: {len(recipes)}개")

    video_ids = [r['external_id'] for r in recipes]
    id_to_recipe = {r['external_id']: r for r in recipes}

    # YouTube API 호출
    log.info("YouTube API 호출 중...")
    details = fetch_video_details(API_KEY, video_ids)
    log.info(f"YouTube 응답: {len(details)}개")

    # 파싱 및 업데이트
    serving_ok = 0
    cooktime_ok = 0
    thumb_ok = 0
    both_fail = 0

    for vid, data in details.items():
        recipe = id_to_recipe.get(vid)
        if not recipe:
            continue

        desc = data.get("description", "")
        thumb = data.get("thumbnail")
        title = recipe['title']

        servings  = parse_servings(desc) or parse_servings(title)
        cook_time = parse_cooktime(desc) or parse_cooktime(title) or parse_cooktime_from_title(title)

        updates = []
        params  = []

        if servings:
            updates.append("servings = %s")
            params.append(servings)
            serving_ok += 1

        if cook_time:
            updates.append("cook_time_min = %s")
            params.append(cook_time)
            cooktime_ok += 1

        if thumb:
            updates.append("thumbnail_url = %s")
            params.append(thumb)
            thumb_ok += 1

        if updates:
            params.append(recipe['id'])
            sql = f"UPDATE recipes SET {', '.join(updates)} WHERE id = %s"
            cur.execute(sql, params)
        else:
            both_fail += 1

    conn.commit()

    log.info(f"\n=== 결과 ===")
    log.info(f"servings 추출: {serving_ok}개")
    log.info(f"cook_time_min 추출: {cooktime_ok}개")
    log.info(f"thumbnail_url 추출: {thumb_ok}개")
    log.info(f"아무것도 못 뽑은 레시피: {both_fail}개")

    # 샘플 확인
    cur.execute("""
        SELECT title, servings, cook_time_min, thumbnail_url IS NOT NULL as has_thumb
        FROM recipes
        WHERE servings IS NOT NULL OR cook_time_min IS NOT NULL
        LIMIT 20
    """)
    log.info("\n=== 추출된 샘플 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:35]:35s}  {str(r['servings']):4}인분  {str(r['cook_time_min']):4}분  thumb={r['has_thumb']}")

    # servings 분포
    cur.execute("SELECT servings, COUNT(*) as c FROM recipes WHERE servings IS NOT NULL GROUP BY servings ORDER BY servings")
    log.info("\n=== servings 분포 ===")
    for r in cur.fetchall():
        log.info(f"  {r['servings']}인분: {r['c']}개")

    cur.close()
    conn.close()
    log.info("완료")


if __name__ == "__main__":
    main()
