"""
amount NULL 문제 해결
케이스 1 (41개): amount=NULL, unit_id=있음
  → 같은 재료+같은 단위로 다른 레시피에서 쓴 평균값 사용
케이스 2 (658개): amount=NULL, unit_id=NULL
  → unit 배정(fix_null_unit 로직 재사용) + 재료 유형별 기본량 적용
"""

import mysql.connector
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fix_null_amount.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}

# ── 재료별 기본 양 (amount + unit) ──
# 한국 레시피에서 양이 명시 안 될 때 보통 쓰는 양
# (약간, 적당량 등으로 처리되는 경우의 기본값)
DEFAULT_AMOUNTS = {
    # 양념/조미료류 → tbsp 기준
    "후추":         (0.5, "tbsp"),  # 약간
    "후춧가루":     (0.5, "tbsp"),
    "통후추가루":   (0.5, "tbsp"),
    "소금":         (1.0, "tbsp"),
    "꽃소금":       (1.0, "tbsp"),
    "맛소금":       (1.0, "tbsp"),
    "천일염":       (1.0, "tbsp"),
    "설탕":         (1.0, "tbsp"),
    "황설탕":       (1.0, "tbsp"),
    "간장":         (2.0, "tbsp"),
    "참기름":       (1.0, "tbsp"),
    "들기름":       (1.0, "tbsp"),
    "식용유":       (2.0, "tbsp"),
    "올리브오일":   (1.0, "tbsp"),
    "고추장":       (2.0, "tbsp"),
    "된장":         (1.0, "tbsp"),
    "고춧가루":     (1.0, "tbsp"),
    "굵은 고춧가루": (1.0, "tbsp"),
    "고운 고춧가루": (1.0, "tbsp"),
    "다진마늘":     (1.0, "tbsp"),
    "간마늘":       (1.0, "tbsp"),
    "다진 마늘":    (1.0, "tbsp"),
    "간 마늘":      (1.0, "tbsp"),
    "생강":         (0.5, "tbsp"),
    "다진생강":     (0.5, "tbsp"),
    "참깨":         (1.0, "tbsp"),
    "깨소금":       (1.0, "tbsp"),
    "들깻가루":     (1.0, "tbsp"),
    "밀가루":       (2.0, "tbsp"),
    "전분가루":     (1.0, "tbsp"),
    "감자전분":     (1.0, "tbsp"),
    "튀김가루":     (3.0, "tbsp"),
    "부침가루":     (3.0, "tbsp"),
    "식초":         (1.0, "tbsp"),
    "미림":         (1.0, "tbsp"),
    "맛술":         (1.0, "tbsp"),
    "청주":         (1.0, "tbsp"),
    "굴소스":       (1.0, "tbsp"),
    "케첩":         (1.0, "tbsp"),
    "마요네즈":     (1.0, "tbsp"),
    "물엿":         (1.0, "tbsp"),
    "올리고당":     (1.0, "tbsp"),
    "꿀":           (1.0, "tbsp"),
    "파슬리가루":   (0.5, "tbsp"),
    "파슬리 가루":  (0.5, "tbsp"),
    "카레가루":     (2.0, "tbsp"),
    "계피가루":     (0.5, "tbsp"),
    "시나몬가루":   (0.5, "tbsp"),
    "고추기름":     (1.0, "tbsp"),
    "김가루":       (1.0, "tbsp"),
    "멸치액젓":     (1.0, "tbsp"),

    # 채소류 → piece 기준
    "양파":         (1.0, "piece"),
    "대파":         (1.0, "piece"),
    "당근":         (1.0, "piece"),
    "감자":         (2.0, "piece"),
    "고구마":       (1.0, "piece"),
    "애호박":       (0.5, "piece"),
    "오이":         (1.0, "piece"),
    "가지":         (1.0, "piece"),
    "청양고추":     (2.0, "piece"),
    "홍고추":       (1.0, "piece"),
    "꽈리고추":    (10.0, "piece"),
    "쪽파":         (3.0, "piece"),
    "양배추":       (0.25, "piece"),
    "깻잎":         (5.0, "piece"),
    "상추":         (5.0, "piece"),

    # 우유/크림 → cup 기준
    "우유":         (1.0, "cup"),
    "생크림":       (0.5, "cup"),
}

# fix_null_unit의 키워드 분류 재사용
PIECE_KEYWORDS = [
    "양파", "대파", "당근", "감자", "고구마", "애호박", "오이", "가지",
    "무", "배추", "양배추", "깻잎", "상추", "브로콜리", "연근", "우엉",
    "청경채", "파프리카", "피망", "토마토", "방울토마토", "옥수수",
    "시금치", "부추", "쑥갓", "미나리", "냉이", "달래", "쪽파",
    "표고버섯", "느타리버섯", "팽이버섯", "새송이버섯", "양송이버섯", "새송이",
    "닭", "오징어", "갈치", "고등어", "꽁치", "전복", "두부", "순두부",
    "라면", "어묵", "사각어묵", "소시지", "스팸", "햄", "베이컨",
    "런천미트", "프랑크소시지", "게맛살", "식빵", "만두",
    "달걀", "계란", "메추리알",
    "귤", "레몬", "사과", "배", "수박",
    "조개", "바지락", "홍합", "김", "밥",
]
TBSP_KEYWORDS = [
    "간장", "식초", "참기름", "들기름", "식용유", "올리브오일", "올리브유",
    "굴소스", "케첩", "케찹", "마요네즈", "마요", "미림", "청주", "막걸리",
    "소주", "와인", "맛술", "액젓", "멸치액젓", "새우젓", "노두유",
    "우스터", "스리라차", "타바스코",
    "설탕", "소금", "꽃소금", "맛소금", "천일염", "황설탕", "흑설탕",
    "고춧가루", "후춧가루", "후추", "계피가루", "시나몬", "카레가루",
    "쿠민", "큐민", "파슬리가루", "파슬리 가루",
    "밀가루", "부침가루", "튀김가루", "전분가루", "빵가루", "쌀가루",
    "베이킹파우더", "이스트",
    "고추장", "된장", "쌈장", "춘장",
    "다진마늘", "간마늘", "다진 마늘", "간 마늘", "다진생강", "다진 생강",
    "깨소금", "참깨", "들깨", "들깻가루",
    "버터", "마가린", "물엿", "올리고당", "꿀", "연유",
    "우유", "생크림",
]


def classify_unit(ing_name: str, default_unit: str) -> str | None:
    if default_unit == "piece": return "piece"
    if default_unit == "ml":   return "tbsp"
    for kw in PIECE_KEYWORDS:
        if kw in ing_name: return "piece"
    for kw in TBSP_KEYWORDS:
        if kw in ing_name: return "tbsp"
    if default_unit == "g":    return "piece"
    return None


def get_default_amount(ing_name: str) -> tuple[float, str] | None:
    """재료명으로 기본 amount + unit 반환"""
    # 정확한 매칭
    if ing_name in DEFAULT_AMOUNTS:
        return DEFAULT_AMOUNTS[ing_name]
    # 키워드 포함 매칭
    for key, val in DEFAULT_AMOUNTS.items():
        if key in ing_name:
            return val
    return None


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        log.info("DB 연결 성공")
    except Exception as e:
        log.error(f"DB 연결 실패: {e}")
        return

    # units 로드
    cur.execute("SELECT id, code, base_code FROM units")
    units_by_code = {r['code']: r for r in cur.fetchall()}
    units_by_id   = {r['id']:   r for r in units_by_code.values()}
    piece_id = units_by_code['piece']['id']
    tbsp_id  = units_by_code['tbsp']['id']

    # ── 케이스 1: amount=NULL, unit_id=있음 (41개) ──
    log.info("케이스 1 처리: amount=NULL, unit_id=있음")
    cur.execute("""
        SELECT ri.id as ri_id, ri.unit_id, i.id as ing_id, i.name as ing_name
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE (ri.amount IS NULL OR ri.amount = '')
          AND ri.unit_id IS NOT NULL AND ri.ingredient_id IS NOT NULL
    """)
    case1 = cur.fetchall()
    log.info(f"  대상: {len(case1)}개")

    c1_updated = 0
    c1_default = 0
    c1_skip    = 0

    for row in case1:
        unit_code = units_by_id[row['unit_id']]['code']

        # 같은 재료 + 같은 단위의 다른 레시피 평균
        cur.execute("""
            SELECT AVG(CAST(ri2.amount AS DECIMAL(10,3))) as avg_amt, COUNT(*) as cnt
            FROM recipe_ingredients ri2
            WHERE ri2.ingredient_id = %s AND ri2.unit_id = %s
              AND ri2.amount IS NOT NULL AND ri2.amount != ''
              AND ri2.id != %s
        """, (row['ing_id'], row['unit_id'], row['ri_id']))
        avg = cur.fetchone()

        if avg['avg_amt'] and float(avg['avg_amt']) > 0:
            amt = round(float(avg['avg_amt']), 2)
            cur.execute("UPDATE recipe_ingredients SET amount = %s WHERE id = %s",
                        (str(amt), row['ri_id']))
            c1_updated += 1
            log.info(f"  [타레시피 평균] {row['ing_name']:20s} → {amt} {unit_code} (n={avg['cnt']})")
        else:
            # 기본값으로 대체
            default = get_default_amount(row['ing_name'])
            if default:
                amt, _ = default
                cur.execute("UPDATE recipe_ingredients SET amount = %s WHERE id = %s",
                            (str(amt), row['ri_id']))
                c1_default += 1
                log.info(f"  [기본값] {row['ing_name']:20s} → {amt} {unit_code}")
            else:
                c1_skip += 1

    conn.commit()
    log.info(f"  타레시피 평균: {c1_updated}개 / 기본값: {c1_default}개 / 스킵: {c1_skip}개")

    # ── 케이스 2: amount=NULL, unit_id=NULL (658개) ──
    log.info("케이스 2 처리: amount=NULL, unit_id=NULL")
    cur.execute("""
        SELECT ri.id as ri_id, i.id as ing_id, i.name as ing_name, i.default_unit
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE (ri.amount IS NULL OR ri.amount = '')
          AND ri.unit_id IS NULL AND ri.ingredient_id IS NOT NULL
    """)
    case2 = cur.fetchall()
    log.info(f"  대상: {len(case2)}개")

    c2_avg     = 0
    c2_default = 0
    c2_skip    = 0

    for row in case2:
        # 먼저 unit 결정
        unit_str = classify_unit(row['ing_name'], row['default_unit'])
        if not unit_str:
            c2_skip += 1
            continue

        assigned_unit_id = piece_id if unit_str == "piece" else tbsp_id

        # 같은 재료 + 배정 단위로 다른 레시피 평균 확인
        cur.execute("""
            SELECT AVG(CAST(ri2.amount AS DECIMAL(10,3))) as avg_amt, COUNT(*) as cnt
            FROM recipe_ingredients ri2
            WHERE ri2.ingredient_id = %s AND ri2.unit_id = %s
              AND ri2.amount IS NOT NULL AND ri2.amount != ''
        """, (row['ing_id'], assigned_unit_id))
        avg = cur.fetchone()

        if avg['avg_amt'] and float(avg['avg_amt']) > 0:
            amt = round(float(avg['avg_amt']), 2)
            cur.execute("""
                UPDATE recipe_ingredients SET amount = %s, unit_id = %s WHERE id = %s
            """, (str(amt), assigned_unit_id, row['ri_id']))
            c2_avg += 1
        else:
            # DEFAULT_AMOUNTS 사용
            default = get_default_amount(row['ing_name'])
            if default:
                amt, default_unit_str = default
                uid = units_by_code.get(default_unit_str, {}).get('id', assigned_unit_id)
                cur.execute("""
                    UPDATE recipe_ingredients SET amount = %s, unit_id = %s WHERE id = %s
                """, (str(amt), uid, row['ri_id']))
                c2_default += 1
            else:
                # unit만 배정, amount는 1로 기본값
                cur.execute("""
                    UPDATE recipe_ingredients SET amount = '1', unit_id = %s WHERE id = %s
                """, (assigned_unit_id, row['ri_id']))
                c2_default += 1

    conn.commit()
    log.info(f"  타레시피 평균: {c2_avg}개 / 기본값: {c2_default}개 / 스킵: {c2_skip}개")

    # ── 레시피 비용 재계산 ──
    log.info("레시피 비용 재계산 시작...")

    cur.execute("SELECT id, code, to_base, base_code FROM units")
    all_units = {r['id']: r for r in cur.fetchall()}

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
            unit = all_units.get(item['unit_id'])
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
    cur.execute("""
        SELECT COUNT(*) as c FROM recipe_ingredients
        WHERE (amount IS NULL OR amount='') AND ingredient_id IS NOT NULL
    """)
    log.info(f"남은 amount NULL: {cur.fetchone()['c']}개")

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
