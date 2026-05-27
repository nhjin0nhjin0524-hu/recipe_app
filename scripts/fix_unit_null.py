"""
unit_id NULL인 recipe_ingredients에 재료명 기반으로 unit 자동 할당 후 estimated_cost 재계산
DRY_RUN = True: 시뮬레이션만, False: 실제 DB 업데이트
"""
import sys, pymysql
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')

DRY_RUN = True

AIVEN_CFG = dict(
    host='mysql-2657d414-nhjin0nhjin0524-f196.d.aivencloud.com',
    port=21782, user='avnadmin', password='AVNS_X0ag18_z-mAK5vkZG9P',
    db='cooking_db', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor, ssl={'use_ssl': True}
)

# unit_id 매핑
UNIT = {'g': 1, 'kg': 2, 'ml': 3, 'l': 4, 'tsp': 5, 'tbsp': 6, 'cup': 7, 'piece': 8}

# 재료명 키워드 → unit 규칙 (긴 것 먼저)
RULES = [
    # ml보다 먼저 체크해야 하는 tbsp (물엿/올리고당 등 '물' 키워드에 묻힘 방지)
    (['물엿', '올리고당', '조청'], 'tbsp'),
    # 액체류 → ml
    (['물 ml', '육수 ml', '우유 ml', '탄산수', '사이다', '스프라이트', '화이트 와인', '레드와인', '와인'], 'ml'),
    (['물', '육수', '우유', '두유', '생크림', '코코넛밀크', '오렌지주스', '토마토주스', '식혜', '면수', '올리브오일'], 'ml'),
    # 가루/조미료 소량 → tsp
    (['후춧가루', '후추가루', '후추', '소금 약', '설탕 약', '참깨 약', '깨소금 약',
      '시나몬 가루', '계핏가루', '연겨자', '고추냉이', '타바스코'], 'tsp'),
    # 조미료류 → tbsp
    (['간장', '고추장', '된장', '참기름', '들기름', '식초', '맛술', '청주', '소주',
      '올리브유', '식용유', '참깨', '깨소금', '통깨', '간 깨', '간깨', '고춧가루', '고추가루',
      '소금', '설탕', '꿀', '굴소스', '굴 소스', '스리라차', '케첩', '케찹',
      '마요네즈', '머스타드', '국간장', '진간장', '액젓', '멸치액젓', '새우젓',
      '쌈장', '고추기름', '다시다', '소고기다시다', '치킨스톡',
      '간마늘', '간 마늘', '다진마늘', '다진 마늘', '간생강', '간 생강', '다진생강',
      '황설탕', '흑설탕', '올리고당', '물엿', '꽃소금', '맛소금', '조청', '천일염',
      '밀가루', '중력분', '강력분', '전분가루', '부침가루', '튀김가루', '습식쌀가루',
      '들깻가루', '멸치가루', '빵가루', '우스터소스', '땅콩버터', '만능양념장',
      '장아찌소스', '만능짜장소스', '마라소스', '고형 카레', '카레가루',
      '굵은고추가루', '고운고추가루', '굵은고춧가루',
      '탈피들깨가루', '콩비지'], 'tbsp'),
    # g 단위 고기류
    (['돈등심', '우목심', '돼지지방', '돼지등갈비'], 'g'),
    # 개수로 세는 재료 → piece
    (['양파', '대파', '쪽파', '파', '오이', '감자', '고구마', '당근', '가지',
      '호박', '애호박', '브로콜리', '콜리플라워', '레몬', '라임', '오렌지',
      '토마토', '사과', '배', '달걀', '계란', '두부', '순두부', '연두부',
      '런천미트', '햄', '소시지', '어묵', '오징어', '낙지', '주꾸미',
      '전복', '조개', '바지락', '홍합', '꽃게', '새우', '라면', '스팸',
      '홍고추', '청양고추', '피망', '파프리카', '로메인', '양상추', '치커리', '셀러리',
      '표고버섯', '새송이버섯', '새송이', '느타리버섯', '양송이', '목이버섯',
      '무', '단무지', '깻잎', '상추', '부추', '수박', '시금치', '미역',
      '스틱버터', '버터', '통마늘', '깐마늘', '깐 마늘', '마늘',
      '돼지고기', '소고기', '닭', '불고기용', '다짐육', '삼겹살', '목살',
      '순대', '만두피', '식빵', '통식빵', '또띠아',
      '포기', '신김치', '김치', '디포리', '다시마',
      '깐 밤', '캬라멜', '밤소스', '튜나샐러드', '유부조림', '땅콩 분태',
      '메추리알', '밥 공기', '도토리묵 팩', '묵 팩', '통조림', '캔', '후르츠칵테일', '밥'], 'piece'),
]

# 이름 끝에 이 단어가 포함되면 piece (줄/장/팩/캔/봉지/마리/알/타래/인분 등)
PIECE_SUFFIXES = ['줄', '장', '팩', '캔', '봉지', '마리', ' 알', '타래', '인분', '토막', '덩어리', '덩이', '조각', '과', '공기', ' 와']

# 실제 재료가 아닌 것 (스킵)
NON_INGREDIENTS = {'그릇 세팅', '접시 세팅 재료', '소스', '인분 세팅', '세팅 재료', '그릇세팅', '인분세팅'}

def guess_unit(name: str) -> str | None:
    clean = name.strip()
    # 키워드 매칭
    for keywords, unit in RULES:
        for kw in keywords:
            if kw in clean:
                return unit
    # suffix 매칭 → piece
    for suffix in PIECE_SUFFIXES:
        if suffix in clean:
            return 'piece'
    return None


def main():
    conn = pymysql.connect(**AIVEN_CFG)

    # 1. unit_id NULL이고 amount 있는 재료 전체 조회
    with conn.cursor() as cur:
        cur.execute('''
            SELECT ri.id, ri.name, ri.amount, ri.recipe_id, i.avg_price, i.default_unit
            FROM recipe_ingredients ri
            JOIN ingredients i ON ri.ingredient_id = i.id
            WHERE ri.unit_id IS NULL AND ri.amount IS NOT NULL
        ''')
        rows = cur.fetchall()

    print(f'unit_id NULL 대상: {len(rows)}개\n')

    matched, unmatched, skipped = [], [], []
    for r in rows:
        name = r['name'].strip()
        if name in NON_INGREDIENTS:
            skipped.append((r['id'], name))
            continue
        unit = guess_unit(name)
        if unit:
            matched.append((r['id'], name, r['amount'], unit))
        else:
            unmatched.append((r['id'], name, r['amount']))

    print(f'매칭 성공: {len(matched)}개')
    print(f'매칭 실패: {len(unmatched)}개')
    print(f'스킵(비재료): {len(skipped)}개\n')

    print('=== 매칭 성공 샘플 (30개) ===')
    for rid, name, amt, unit in matched[:30]:
        print(f'  ri_id={rid:6d}  {name:25s}  {amt}  →  {unit}')

    print('\n=== 매칭 실패 목록 ===')
    for rid, name, amt in unmatched:
        print(f'  ri_id={rid:6d}  {name:25s}  {amt}')

    if not DRY_RUN and matched:
        with conn.cursor() as cur:
            for ri_id, _, _, unit in matched:
                cur.execute(
                    'UPDATE recipe_ingredients SET unit_id = %s WHERE id = %s',
                    (UNIT[unit], ri_id)
                )
        conn.commit()
        print(f'\n완료: {len(matched)}개 unit_id 업데이트')

        # estimated_cost 재계산 대상 레시피
        recipe_ids = list({r[0] for r in matched})  # ri_id 아니라 recipe_id 필요
        # recipe_id 다시 가져오기
        with conn.cursor() as cur:
            cur.execute('''
                SELECT DISTINCT recipe_id FROM recipe_ingredients
                WHERE id IN ({})
            '''.format(','.join(str(r[0]) for r in matched)))
            rids = [r['recipe_id'] for r in cur.fetchall()]
        print(f'estimated_cost 재계산 필요 레시피: {len(rids)}개 — 별도 스크립트로 실행 필요')
    elif DRY_RUN:
        print('\n[DRY RUN] 실제 업데이트 없음')

    conn.close()


if __name__ == '__main__':
    main()
