"""
재료 가격 매칭 보완 스크립트 v2
접근 방식:
  1. 잘못된 매핑(기존 스크립트가 틀리게 넣은 것) 초기화
  2. API에 없는 재료에 실제 시장 단가 직접 입력
  3. 진짜 동급 재료만 KEYWORD_MAP 사용 (이름만 다르고 같은 재료인 것)
  4. 물/얼음/육수 등 원가가 거의 0인 것 → NULL 유지 (계산 제외)
"""

import mysql.connector
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fix_matching.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}

# ──────────────────────────────────────────────────────────────
# 1. 실제 시장 단가 (API에 없어서 직접 입력)
#    단위: avg_price 컬럼 = g/ml 기준 100당 가격, piece는 1개 가격
#    참고: 2025년 대형마트 기준 대략적 단가
# ──────────────────────────────────────────────────────────────
DIRECT_PRICES = {
    # ── 향신료/가루류 (100g 기준) ──
    "후추":             ("g",  700),   # 흑후추 분말 ~700원/100g
    "통후추":           ("g",  700),
    "통후추가루":        ("g",  700),
    "후춧가루":         ("g",  700),
    "흰후추":           ("g",  700),
    "계피가루":         ("g",  600),   # 시나몬 ~600원/100g
    "계핏가루":         ("g",  600),
    "시나몬가루":        ("g",  600),
    "시나몬파우더":      ("g",  600),
    "시나몬 가루":       ("g",  600),
    "시나몬 스틱":       ("piece", 300),
    "카레가루":         ("g",  350),   # 카레 가루 ~350원/100g
    "고형 카레":        ("g",  350),
    "고형카레":         ("g",  350),
    "쿠민가루":         ("g",  800),   # 쿠민 ~800원/100g
    "큐민가루":         ("g",  800),
    "고추냉이":         ("g",  900),
    "연겨자":           ("g",  700),
    "연와사비":         ("g",  900),
    "와사비":           ("g",  900),

    # ── 참깨/들깨/견과류 (100g 기준) ──
    "참깨":             ("g",  800),   # 참깨 ~800원/100g
    "깨":               ("g",  800),
    "간 깨":            ("g",  800),
    "통깨":             ("g",  800),
    "들깨":             ("g",  600),   # 들깨 ~600원/100g
    "들깻가루":         ("g",  600),
    "탈피들깨가루":      ("g",  600),
    "껍질 있는 들깨가루": ("g", 550),
    "땅콩":             ("g",  500),   # 땅콩 ~500원/100g
    "땅콩 분태":        ("g",  500),
    "땅콩버터":         ("g",  600),
    "잣":               ("g", 3000),   # 잣 ~3000원/100g (비쌈)

    # ── 전분류 (100g 기준) ──
    "전분가루":         ("g",  180),   # 전분 ~180원/100g
    "감자전분":         ("g",  180),
    "옥수수전분":        ("g",  180),
    "옥수수전분가루":    ("g",  180),
    "전분물":           ("g",   50),   # 물에 탄 것이라 희석됨

    # ── 오트밀/시리얼 (100g 기준) ──
    "오트밀":           ("g",  150),   # 오트밀 ~150원/100g

    # ── 생강류 (100g 기준) ──
    "생강":             ("g",  300),   # 생강 ~300원/100g
    "다진생강":         ("g",  300),
    "생강가루":         ("g",  500),

    # ── 해조류 - 건조 (100g 기준) ──
    "다시마":           ("g",  800),   # 건다시마 ~800원/10g → 8000원/100g 하지만 물에 불리면 많아짐
    "건 다시마":        ("g",  800),
    "불린 다시마 채":   ("g",  200),   # 불린 후 가격 비례 낮음
    "절단 다시마":      ("g",  800),
    "절단다시마":       ("g",  800),
    "조각 다시마":      ("g",  800),
    "건미역":           ("g", 1000),   # 건미역 ~1000원/10g → 10000원/100g
    "건 미역":          ("g", 1000),
    "미역":             ("g",  500),   # 생미역/불린미역 기준
    "불린미역":         ("g",  200),
    "불린 미역":        ("g",  200),
    "자른미역":         ("g",  200),
    "절단 불린 미역":   ("g",  200),

    # ── 레몬/시트러스 (개당) ──
    "레몬":             ("piece", 600), # 레몬 1개 ~600원
    "레몬즙":           ("ml",  600),   # 레몬즙 ~600원/100ml
    "레몬쥬스":         ("ml",  300),

    # ── 과일류 ──
    "수박":             ("g",   150),  # ~150원/100g
    "사과":             ("piece", 1500),
    "배":               ("piece", 2000),
    "갈아만든 배":      ("piece", 2000),
    "딸기":             ("g",  400),
    "딸기잼":           ("g",  300),
    "블루베리":         ("g",  600),
    "블랙올리브":       ("g",  500),
    "올리브":           ("g",  500),

    # ── 버섯류 (100g 기준) ──
    "느타리버섯":       ("g",  180),
    "표고버섯":         ("g",  300),
    "팽이버섯":         ("g",  130),
    "새송이버섯":       ("g",  200),
    "양송이버섯":       ("g",  250),
    "목이버섯":         ("g",  400),
    "건 목이버섯":      ("g", 1500),   # 건조 목이버섯 비쌈

    # ── 채소류 (100g 기준) ──
    "가지":             ("g",  200),   # 가지 ~200원/100g
    "시금치":           ("g",  200),
    "브로콜리":         ("g",  250),
    "연근":             ("g",  250),
    "우엉":             ("g",  200),
    "도라지":           ("g",  350),
    "냉이":             ("g",  400),
    "달래":             ("g",  400),
    "부추":             ("g",  200),
    "쑥갓":             ("g",  250),
    "미나리":           ("g",  250),
    "참나물":           ("g",  300),
    "청경채":           ("g",  200),
    "열무":             ("g",  150),

    # ── 고기/밤 ──
    "생밤":             ("g",  400),
    "깐 밤":            ("g",  400),
    "밤":               ("g",  400),
    "전복":             ("piece", 5000),
    "데친 전복":        ("piece", 5000),
    "전복 손질":        ("piece", 5000),
    "전복구이":         ("piece", 5000),

    # ── 가공식품류 ──
    "단무지":           ("g",  100),   # ~100원/100g
    "원형단무지":       ("g",  100),
    "통 단무지":        ("g",  100),
    "통단무지":         ("g",  100),
    "치자 단무지":      ("g",  100),
    "반달 단무지":      ("g",  100),
    "도토리묵":         ("g",  150),
    "순대":             ("g",  400),
    "초콜릿":           ("g",  700),
    "베이크드빈스":     ("g",  250),
    "마요네즈":         ("g",  500),
    "마요소스":         ("g",  500),

    # ── 유제품/버터 ──
    "버터":             ("g",  800),
    "스틱버터":         ("g",  800),
    "마가린":           ("g",  500),
    "생크림":           ("ml", 600),

    # ── 알코올류 (100ml 기준) ──
    "막걸리":           ("ml", 200),
    "소주":             ("ml", 420),
    "청주":             ("ml", 400),
    "미림":             ("ml", 400),
    "미린":             ("ml", 400),
    "화이트와인":       ("ml", 1000),
    "화이트 와인":      ("ml", 1000),
    "레드와인":         ("ml", 1000),
    "레드와인 병":      ("ml", 1000),
    "레드 와인":        ("ml", 1000),
    "와인":             ("ml", 1000),

    # ── 기타 양념 ──
    "연겨자":           ("g",  700),
    "고추냉이":         ("g",  900),
    "조미김":           ("g", 3000),   # 조미김 ~3000원/100g
    "파슬리":           ("g",  500),
    "파슬리 가루":      ("g",  500),
    "파슬리가루":       ("g",  500),
    "바질":             ("g",  500),
    "페퍼론치노":       ("g",  800),
    "사천고추":         ("g",  700),
    "베트남 고추":      ("g",  700),

    # ── 누룩/이스트 ──
    "누룩":             ("g",  500),
    "효모":             ("g",  500),
    "이스트":           ("g",  500),
    "드라이 이스트":    ("g",  500),
    "베이킹파우더":     ("g",  300),
}

# ──────────────────────────────────────────────────────────────
# 2. KEYWORD_MAP: 진짜 동급 재료 (이름만 다른 것)
#    → 기준 재료의 avg_price를 그대로 사용해도 되는 것들만
# ──────────────────────────────────────────────────────────────
KEYWORD_MAP = {
    # 계란류
    "달걀": "계란", "메추리알": "계란", "달걀노른자": "계란", "달걀흰자": "계란",
    "달걀 노른자": "계란", "달걀 흰자": "계란", "달걀물": "계란", "달걀지단": "계란",
    "달걀프라이": "계란", "삶은 달걀": "계란", "삶은달걀": "계란",
    "깐 메추리알": "계란", "지단": "계란",

    # 돼지고기류
    "삼겹살": "돼지고기", "대패삼겹살": "돼지고기", "대패 삼겹살": "돼지고기",
    "냉동삼겹살": "돼지고기", "돼지 목살": "돼지고기", "돼지갈비": "돼지고기",
    "돼지고기 목살": "돼지고기", "돼지고기 등심": "돼지고기",
    "돼지고기 앞다리살": "돼지고기", "돼지고기 뒷다리살": "돼지고기",
    "돼지등갈비": "돼지고기", "등갈비": "돼지고기", "항정살": "돼지고기",
    "다진 돼지고기": "돼지고기", "뒷다리살": "돼지고기",
    "돼지지방": "돼지고기", "편육": "돼지고기", "족발": "돼지고기",
    "햄": "돼지고기", "소시지": "돼지고기", "베이컨": "돼지고기",
    "스팸": "돼지고기", "통조림 햄": "돼지고기", "통조림햄": "돼지고기",

    # 소고기류
    "LA갈비": "소고기(국산)", "갈비": "소고기(국산)",
    "소고기 불고기용": "소고기(국산)", "차돌박이": "소고기(국산)",
    "소 양지": "소고기(국산)", "소양지": "소고기(국산)",
    "불고기": "소고기(국산)", "간소고기": "소고기(국산)",
    "다진소고기": "소고기(국산)", "스테이크": "소고기(국산)",
    "찹스테이크": "소고기(국산)", "찹 스테이크": "소고기(국산)",
    "육전": "소고기(국산)", "초벌소곱창": "소고기(국산)",
    "초벌소깐양": "소고기(국산)",

    # 닭고기류
    "닭가슴살": "닭고기", "닭 다리살": "닭고기", "닭다리살": "닭고기",
    "닭봉": "닭고기", "토막닭": "닭고기", "삶은 닭": "닭고기",
    "버팔로윙": "닭고기", "치킨": "닭고기",

    # 마늘류
    "마늘": "깐마늘", "다진마늘": "깐마늘", "통마늘": "깐마늘",
    "마늘쫑": "깐마늘",

    # 고추류
    "풋고추": "청양고추", "오이고추": "청양고추",
    "홍고추": "붉은고추", "건고추": "붉은고추",
    "건홍고추": "붉은고추",
    "불린 고춧가루": "고춧가루", "고운 고춧가루": "고춧가루",
    "굵은 고춧가루": "고춧가루",

    # 파류
    "쪽파": "대파", "파채": "대파",
    "대파 흰 부분": "대파", "대파 흰부분": "대파",

    # 버섯류 (DIRECT_PRICES에 없는 경우 fallback)
    "새송이": "새송이버섯", "양송이": "양송이버섯",

    # 쌀/면류
    "소면": "국수", "칼국수면": "국수", "메밀면": "국수",
    "중면": "국수", "쫄면": "국수", "우동면": "국수",
    "스파게티면": "국수", "파스타면": "국수", "중화면": "국수",
    "당면": "국수", "잡채": "국수",
    "쌀가루": "쌀", "찹쌀가루": "쌀", "쌀떡": "쌀",
    "가래떡": "쌀", "떡국떡": "쌀", "밥": "쌀",

    # 배추/무류
    "알배추": "배추", "알배기 배추": "배추", "절인배추": "배추",
    "김치": "배추", "신 김치": "배추",
    "무우": "무", "무절임": "무", "무말랭이": "무", "깍두기": "무",
    "단무지": "무",  # 이미 DIRECT_PRICES에 있지만 혹시 없을 경우 fallback

    # 두부류
    "순두부": "두부", "부침용 두부": "두부",
    "어묵": "두부", "사각어묵": "두부",
    "유부": "두부",

    # 호박류
    "돼지호박": "애호박", "주키니호박": "애호박",

    # 멸치류
    "국멸치": "마른멸치", "국물용 멸치": "마른멸치",
    "멸치가루": "마른멸치", "멸치 액젓": "마른멸치",
    "멸치액젓": "마른멸치", "가다랑어": "마른멸치",
    "디포리": "마른멸치",

    # 생선류
    "황태채": "명태", "북어채": "명태", "동태": "명태",
    "고등어 통조림": "고등어", "고등어통조림": "고등어",
    "참치": "고등어", "통조림참치": "고등어",
    "진미채": "오징어", "오징어채": "오징어",

    # 조개/해산물
    "바지락": "조개", "홍합": "조개", "홍합살": "조개",
    "새우젓": "건새우",

    # 설탕류
    "황설탕": "설탕", "흑설탕": "설탕",
    "올리고당": "설탕", "물엿": "설탕",

    # 식초류
    "양조식초": "식초", "사과식초": "식초",

    # 밀가루류
    "빵가루": "밀가루", "튀김가루": "밀가루",
    "부침가루": "밀가루", "중력분": "밀가루", "강력분": "밀가루",
    "수제비 반죽": "밀가루",

    # 우유/유제품
    "흰우유": "우유", "슬라이스치즈": "우유",
    "피자치즈": "우유", "모짜렐라": "우유",

    # 라면류
    "진라면": "라면", "너구리": "라면", "곱창라면": "라면",
    "라면수프": "라면", "분말스프": "라면",

    # 소스/간장류
    "굴소스": "간장", "노두유": "간장", "액젓": "간장",
    "꽃소금": "간장", "맛소금": "간장", "천일염": "간장",
    "황설탕": "설탕",

    # 된장류
    "재래식 된장": "된장", "청국장": "된장",

    # 기타
    "공심채": "상추", "상추 채": "상추", "양상추": "상추",
    "로메인": "상추", "어린잎채소": "상추",
    "숙주": "콩나물",
}

# ──────────────────────────────────────────────────────────────
# 3. 원가 계산에서 제외할 항목 (물, 얼음 등)
# ──────────────────────────────────────────────────────────────
SKIP_ITEMS = {
    "물", "정수물", "찬물", "소금물", "소면삶는물", "쌀뜨물",
    "얼음", "각얼음", "각 얼음", "사각얼음",
    "육수", "사골국물", "면수", "육수건더기",
    "사이다", "탄산수", "생수", "스프라이트",
    "홍차티백",  # 소량 향용
}


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        log.info("DB 연결 성공")
    except Exception as e:
        log.error(f"DB 연결 실패: {e}")
        return

    # ── 기존 priced 재료 로드 (API에서 받은 원본 데이터 기준) ──
    cur.execute("SELECT id, name, avg_price FROM ingredients WHERE avg_price IS NOT NULL")
    priced = {r['name']: float(r['avg_price']) for r in cur.fetchall()}
    log.info(f"기존 가격 있는 재료: {len(priced)}개")

    # ── 원본 API 재료 (이게 믿을 수 있는 가격 기준) ──
    # 기존 스크립트가 덮어쓴 잘못된 가격들을 NULL로 초기화하고 재처리
    # 판단 기준: DIRECT_PRICES 또는 SKIP_ITEMS에 있는 재료들은 초기화 후 재설정
    reset_count = 0
    for name in list(DIRECT_PRICES.keys()) + list(SKIP_ITEMS):
        cur.execute("SELECT id FROM ingredients WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE ingredients SET avg_price = NULL WHERE name = %s", (name,))
            reset_count += cur.rowcount
    conn.commit()
    log.info(f"잘못된 가격 초기화: {reset_count}개")

    # ── DIRECT_PRICES 직접 입력 ──
    direct_count = 0
    for name, (unit, price) in DIRECT_PRICES.items():
        cur.execute("SELECT id, default_unit FROM ingredients WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE ingredients SET avg_price = %s, default_unit = %s WHERE name = %s",
                        (price, unit, name))
            direct_count += cur.rowcount
        else:
            # ingredients 테이블에 없으면 추가
            cur.execute("INSERT INTO ingredients (name, avg_price, default_unit) VALUES (%s, %s, %s)",
                        (name, price, unit))
            direct_count += 1
    conn.commit()
    log.info(f"직접 가격 입력: {direct_count}개")

    # ── KEYWORD_MAP으로 동급 재료 가격 연결 ──
    # 최신 priced 다시 로드
    cur.execute("SELECT id, name, avg_price FROM ingredients WHERE avg_price IS NOT NULL")
    priced = {r['name']: float(r['avg_price']) for r in cur.fetchall()}

    keyword_count = 0
    keyword_fail = []
    for src_name, target_name in KEYWORD_MAP.items():
        target_price = priced.get(target_name)
        if not target_price:
            keyword_fail.append(f"{src_name} → {target_name} (기준 재료 가격 없음)")
            continue
        cur.execute("SELECT id FROM ingredients WHERE name = %s", (src_name,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE ingredients SET avg_price = %s WHERE name = %s AND avg_price IS NULL",
                        (target_price, src_name))
            keyword_count += cur.rowcount
        else:
            cur.execute("INSERT IGNORE INTO ingredients (name, avg_price) VALUES (%s, %s)",
                        (src_name, target_price))
            if cur.rowcount > 0:
                keyword_count += 1
    conn.commit()
    log.info(f"키워드 매핑: {keyword_count}개")
    for f in keyword_fail:
        log.warning(f"  매핑 실패: {f}")

    # ── 최종 통계 ──
    cur.execute("""
        SELECT
            COUNT(*) as 전체,
            SUM(CASE WHEN avg_price IS NOT NULL THEN 1 ELSE 0 END) as 가격있음
        FROM ingredients
        WHERE id IN (SELECT DISTINCT ingredient_id FROM recipe_ingredients WHERE ingredient_id IS NOT NULL)
    """)
    stat = cur.fetchone()
    log.info(f"\n=== 최종 재료 상태 ===")
    log.info(f"레시피에 사용된 재료: {stat['전체']}개")
    log.info(f"가격 있음: {stat['가격있음']}개")
    log.info(f"가격 없음: {stat['전체'] - stat['가격있음']}개")

    # ── 레시피 비용 재계산 ──
    log.info("\n레시피 비용 재계산 중...")
    cur.execute("SELECT id, code, to_base, base_code FROM units")
    units = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT id, name, avg_price, default_unit FROM ingredients WHERE avg_price IS NOT NULL")
    ingredients = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT id, title FROM recipes")
    recipes = cur.fetchall()

    updated = 0
    skipped = 0

    for recipe in recipes:
        rid = recipe['id']
        cur.execute("""
            SELECT ri.ingredient_id, ri.amount, ri.unit_id
            FROM recipe_ingredients ri
            WHERE ri.recipe_id = %s AND ri.ingredient_id IS NOT NULL
        """, (rid,))
        items = cur.fetchall()

        total = 0.0
        has = False

        for item in items:
            ing = ingredients.get(item['ingredient_id'])
            unit = units.get(item['unit_id'])
            if not ing or not unit or not item['amount'] or not item['unit_id']:
                continue
            try:
                base_amount = float(item['amount']) * float(unit['to_base'])
                bc = str(unit['base_code'])
                p = float(ing['avg_price'])
                if bc in ('g', 'ml'):
                    cost = (p / 100.0) * base_amount
                elif bc == 'piece':
                    cost = p * base_amount
                else:
                    continue
                total += cost
                has = True
            except:
                continue

        if has and total > 0:
            cur.execute("UPDATE recipes SET estimated_cost = %s WHERE id = %s",
                        (round(total, 2), rid))
            updated += 1
        else:
            skipped += 1

    conn.commit()
    log.info(f"레시피 비용 계산: {updated}개 완료 / {skipped}개 스킵")

    # 결과 샘플
    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL
        ORDER BY estimated_cost ASC LIMIT 15
    """)
    log.info("=== 비용 낮은 레시피 TOP 15 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s} {r['estimated_cost']:>10,.0f}원")

    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL
        ORDER BY estimated_cost DESC LIMIT 10
    """)
    log.info("=== 비용 높은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s} {r['estimated_cost']:>10,.0f}원")

    cur.close()
    conn.close()
    log.info("\n완료")


if __name__ == "__main__":
    main()
