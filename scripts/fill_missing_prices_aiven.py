"""
Aiven avg_price NULL 재료 중 유사 재료 가격으로 채우기
1. 기본 재료 가격 직접 설정
2. suffix 변형들에 가격 전파
"""
import sys
import re
import pymysql

sys.stdout.reconfigure(encoding='utf-8')

AIVEN = dict(
    host='mysql-2657d414-nhjin0nhjin0524-f196.d.aivencloud.com',
    port=21782, user='avnadmin', password='AVNS_X0ag18_z-mAK5vkZG9P',
    db='cooking_db', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
    ssl={'use_ssl': True}
)

# (이름, avg_price, default_unit) — 기존 재료와 동일하게 설정
BASE_PRICES = [
    ('황설탕', 228.0, 'g'),
    ('뉴슈가', 228.0, 'g'),
    ('진간장', 400.0, 'ml'),
    ('국간장', 400.0, 'ml'),
    ('조선간장', 400.0, 'ml'),
    ('고운고추가루', 4800.0, 'g'),
    ('굵은고추가루', 4800.0, 'g'),
    ('고운고춧가루', 4800.0, 'g'),
    ('굵은고춧가루', 4800.0, 'g'),
    ('소금', 100.0, 'g'),
    ('꽃소금', 150.0, 'g'),
    ('정수물', 1.0, 'ml'),
    ('정수 물', 1.0, 'ml'),
    ('찬물', 1.0, 'ml'),
    ('뜨거운물', 1.0, 'ml'),
    ('큰 볼에 물', 1.0, 'ml'),
    ('면수', 1.0, 'ml'),
    ('소금물', 50.0, 'ml'),
    ('올리브유', 360.0, 'ml'),
    ('간마늘', 1493.0, 'g'),
    ('간 마늘', 1493.0, 'g'),
    ('다진 마늘', 1493.0, 'g'),
    ('다진마늘', 1493.0, 'g'),
    ('깨소금', 800.0, 'g'),
    ('통후춧가루', 400.0, 'g'),
    ('후추가루', 400.0, 'g'),
    ('후추 소량', 400.0, 'g'),
    ('참깨 소량', 800.0, 'g'),
    ('간깨', 800.0, 'g'),
    ('갈은 깨', 800.0, 'g'),
    ('간 생강', 400.0, 'g'),
    ('간생강', 400.0, 'g'),
    ('멸치 액젓', 400.0, 'ml'),
    ('모짜렐라치즈', 800.0, 'g'),
    ('모차렐라 치즈', 800.0, 'g'),
    ('모차렐라치즈', 800.0, 'g'),
    ('파르메산치즈가루', 1200.0, 'g'),
    ('파르미자노 치즈', 1200.0, 'g'),
    ('파마산 치즈', 1200.0, 'g'),
    ('파마산 치즈가루', 1200.0, 'g'),
    ('파스리가루', 500.0, 'g'),
    ('파슬리 가루', 500.0, 'g'),
    ('시나몬 가루', 800.0, 'g'),
    ('화이트 와인', 1200.0, 'ml'),
    ('요구르트', 200.0, 'ml'),
    ('통조림 햄', 2500.0, 'piece'),
    ('런천미트', 2500.0, 'piece'),
    ('비엔나소시지', 3000.0, 'piece'),
    ('분홍소시지', 2000.0, 'piece'),
    ('프랑크소시지', 3000.0, 'piece'),
    ('사이다 캔', 1200.0, 'piece'),
    ('스프라이트 캔', 1200.0, 'piece'),
    ('소면삶는물', 1.0, 'ml'),
]

# suffix 패턴 (오른쪽 끝에서 제거)
SUFFIX_PATTERNS = [
    r'\s+약\s*[와과]\s*$',
    r'\s+약\s*$',
    r'\s+[와과]\s*$',
    r'\s+가득\s*$',
    r'\s+소량\s*$',
    r'\s+mL\s*$',
    r'\s+g\s*$',
]

def strip_suffix(name):
    original = name
    for pat in SUFFIX_PATTERNS:
        name = re.sub(pat, '', name).strip()
    # 끝이 숫자/조각수로 끝나는 경우: "황설탕 4" → "황설탕"
    name = re.sub(r'\s+\d+$', '', name).strip()
    return name


def main():
    conn = pymysql.connect(**AIVEN)

    with conn.cursor() as cur:
        cur.execute('SELECT id, name, avg_price, default_unit FROM ingredients')
        all_ings = {r['name']: r for r in cur.fetchall()}

    # ── 1. 기본 재료 가격 직접 설정 ──
    updated_base = 0
    with conn.cursor() as cur:
        for name, price, unit in BASE_PRICES:
            ing = all_ings.get(name)
            if ing and ing['avg_price'] is None:
                cur.execute(
                    'UPDATE ingredients SET avg_price=%s, default_unit=%s WHERE name=%s',
                    (price, unit, name)
                )
                all_ings[name]['avg_price'] = price
                all_ings[name]['default_unit'] = unit
                updated_base += 1
    conn.commit()
    print(f'기본 가격 설정: {updated_base}개')

    # ── 2. suffix 변형들에 가격 전파 ──
    # NULL인 재료들 재조회
    with conn.cursor() as cur:
        cur.execute('SELECT id, name FROM ingredients WHERE avg_price IS NULL')
        null_ings = cur.fetchall()

    # avg_price 있는 재료만 (기준 맵)
    price_map = {
        name: (r['avg_price'], r['default_unit'])
        for name, r in all_ings.items()
        if r['avg_price'] is not None
    }

    propagated = 0
    skipped = 0
    with conn.cursor() as cur:
        for ing in null_ings:
            name = ing['name']
            stripped = strip_suffix(name)
            if stripped == name:
                skipped += 1
                continue
            match = price_map.get(stripped)
            if match:
                cur.execute(
                    'UPDATE ingredients SET avg_price=%s, default_unit=%s WHERE id=%s',
                    (match[0], match[1], ing['id'])
                )
                propagated += 1
            else:
                skipped += 1

    conn.commit()
    print(f'suffix 전파: {propagated}개 / 미매칭: {skipped}개')

    # ── 결과 ──
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) as c FROM ingredients WHERE avg_price IS NULL')
        print(f'남은 avg_price NULL: {cur.fetchone()["c"]}개')

    conn.close()
    print('완료')


if __name__ == '__main__':
    main()
