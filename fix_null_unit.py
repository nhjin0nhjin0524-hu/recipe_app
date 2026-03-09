"""
unit_id NULL 문제 해결
- amount는 있지만 unit_id가 NULL인 1,255개 처리
- 재료 특성에 따라 piece(개수) 또는 tbsp(큰술) 단위 자동 배정
- amount + unit_id 모두 NULL인 658개는 처리 불가 → 스킵
"""

import mysql.connector
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fix_null_unit.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}

# ── 개수(piece)로 세는 재료 키워드 ──
PIECE_KEYWORDS = [
    # 채소
    "양파", "대파", "당근", "감자", "고구마", "애호박", "오이", "가지",
    "무", "배추", "양배추", "깻잎", "상추", "브로콜리", "연근", "우엉",
    "도라지", "청경채", "파프리카", "피망", "토마토", "방울토마토", "옥수수",
    "시금치", "부추", "쑥갓", "미나리", "냉이", "달래", "쪽파",
    # 버섯
    "표고버섯", "느타리버섯", "팽이버섯", "새송이버섯", "양송이버섯", "새송이",
    # 고기/생선
    "닭", "오징어", "갈치", "고등어", "꽁치", "전복", "두부", "순두부",
    # 가공식품
    "라면", "어묵", "사각어묵", "소시지", "스팸", "햄", "베이컨",
    "런천미트", "프랑크소시지", "게맛살", "식빵", "만두",
    # 계란
    "달걀", "계란", "메추리알",
    # 과일
    "귤", "레몬", "사과", "배", "수박",
    # 해산물
    "조개", "바지락", "홍합",
    # 김/해조
    "김",
    # 밥
    "밥", "주먹밥",
]

# ── 큰술(tbsp)로 재는 재료 키워드 ──
TBSP_KEYWORDS = [
    # 액체 조미료
    "간장", "식초", "참기름", "들기름", "식용유", "올리브오일", "올리브유",
    "굴소스", "케첩", "케찹", "마요네즈", "마요", "미림", "청주", "막걸리",
    "소주", "와인", "맛술", "액젓", "멸치액젓", "새우젓", "노두유",
    "우스터", "스리라차", "타바스코", "핫소스",
    # 가루/고체 조미료
    "설탕", "소금", "꽃소금", "맛소금", "천일염", "황설탕", "흑설탕",
    "고춧가루", "후춧가루", "후추", "계피가루", "시나몬", "카레가루",
    "쿠민", "큐민", "파슬리가루", "파슬리 가루",
    "밀가루", "부침가루", "튀김가루", "전분가루", "빵가루", "쌀가루",
    "베이킹파우더", "이스트",
    # 페이스트류
    "고추장", "된장", "쌈장", "춘장",
    # 다진 것
    "다진마늘", "간마늘", "다진 마늘", "간 마늘", "다진생강", "다진 생강",
    "깨소금", "참깨", "들깨", "들깻가루",
    # 기름/버터
    "버터", "마가린",
    # 달콤한 것
    "물엿", "올리고당", "꿀", "연유", "잼",
    # 우유/크림
    "우유", "생크림",
]

def classify_unit(name: str, default_unit: str) -> str | None:
    """재료명과 default_unit으로 적절한 단위 반환 ('piece' or 'tbsp')"""

    # default_unit이 명확한 경우
    if default_unit == "piece":
        return "piece"
    if default_unit == "ml":
        return "tbsp"  # 액체는 큰술

    # 이름 기반 분류
    for kw in PIECE_KEYWORDS:
        if kw in name:
            return "piece"
    for kw in TBSP_KEYWORDS:
        if kw in name:
            return "tbsp"

    # default_unit = 'g'인데 키워드 미매칭 → piece (개수로 쓸 가능성 높음)
    if default_unit == "g":
        return "piece"

    return None  # 판단 불가


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        log.info("DB 연결 성공")
    except Exception as e:
        log.error(f"DB 연결 실패: {e}")
        return

    # units ID 로드
    cur.execute("SELECT id, code, base_code FROM units")
    units_by_code = {r['code']: r['id'] for r in cur.fetchall()}
    piece_id = units_by_code['piece']   # 8
    tbsp_id  = units_by_code['tbsp']    # 6
    log.info(f"piece unit_id={piece_id}, tbsp unit_id={tbsp_id}")

    # 처리 가능한 항목 로드 (amount 있고 unit_id NULL)
    cur.execute("""
        SELECT ri.id as ri_id, ri.name, ri.amount, i.name as ing_name, i.default_unit
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.unit_id IS NULL
          AND ri.amount IS NOT NULL AND ri.amount != ''
    """)
    rows = cur.fetchall()
    log.info(f"처리 대상: {len(rows)}개")

    piece_count = 0
    tbsp_count  = 0
    skip_count  = 0

    for row in rows:
        assigned = classify_unit(row['ing_name'], row['default_unit'])

        if assigned == "piece":
            cur.execute("UPDATE recipe_ingredients SET unit_id = %s WHERE id = %s",
                        (piece_id, row['ri_id']))
            piece_count += 1
        elif assigned == "tbsp":
            cur.execute("UPDATE recipe_ingredients SET unit_id = %s WHERE id = %s",
                        (tbsp_id, row['ri_id']))
            tbsp_count += 1
        else:
            skip_count += 1

    conn.commit()
    log.info(f"piece 배정: {piece_count}개 / tbsp 배정: {tbsp_count}개 / 판단 불가: {skip_count}개")

    # ── 레시피 비용 재계산 ──
    log.info("레시피 비용 재계산 시작...")

    cur.execute("SELECT id, code, to_base, base_code FROM units")
    units = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT id, name, avg_price, default_unit FROM ingredients WHERE avg_price IS NOT NULL")
    ingredients = {r['id']: r for r in cur.fetchall()}

    cur.execute("""
        SELECT ingredient_id, base_g, base_ml
        FROM ingredient_packaging_conversions WHERE pkg_unit_text = 'piece'
    """)
    piece_weights = {r['ingredient_id']: r for r in cur.fetchall()}

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
        has   = False

        for item in items:
            ing  = ingredients.get(item['ingredient_id'])
            unit = units.get(item['unit_id'])
            if not ing or not unit or not item['amount'] or not item['unit_id']:
                continue
            try:
                amount       = float(item['amount'])
                to_base      = float(unit['to_base'])
                base_code    = str(unit['base_code'])
                avg_price    = float(ing['avg_price'])
                default_unit = ing['default_unit']
                base_amount  = amount * to_base

                if base_code in ('g', 'ml'):
                    cost = (avg_price / 100.0) * base_amount
                elif base_code == 'piece':
                    if default_unit == 'piece':
                        cost = avg_price * base_amount
                    else:
                        pw = piece_weights.get(item['ingredient_id'])
                        if pw and pw['base_g']:
                            cost = (avg_price / 100.0) * base_amount * float(pw['base_g'])
                        else:
                            cost = (avg_price / 100.0) * base_amount * 50
                else:
                    continue

                total += cost
                has    = True
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

    # ── 최종 현황 ──
    cur.execute("SELECT COUNT(*) as c FROM recipe_ingredients WHERE unit_id IS NULL AND ingredient_id IS NOT NULL")
    remaining = cur.fetchone()['c']
    log.info(f"남은 unit_id NULL: {remaining}개 (amount NULL 포함)")

    cur.execute("SELECT COUNT(*) as c FROM recipes WHERE estimated_cost IS NOT NULL")
    log.info(f"estimated_cost 있는 레시피: {cur.fetchone()['c']}개 / 333개")

    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL ORDER BY estimated_cost ASC LIMIT 10
    """)
    log.info("=== 비용 낮은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s}  {r['estimated_cost']:>10,.0f}원")

    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL ORDER BY estimated_cost DESC LIMIT 10
    """)
    log.info("=== 비용 높은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s}  {r['estimated_cost']:>10,.0f}원")

    cur.close()
    conn.close()
    log.info("완료")


if __name__ == "__main__":
    main()
