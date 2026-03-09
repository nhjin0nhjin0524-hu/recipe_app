"""
piece 단위 계산 오류 수정
문제: recipe_ingredients에서 unit=piece인데,
      ingredients.avg_price가 100g 기준인 재료들이 있어서 가격이 뻥튀기됨

해결:
  1. ingredient_packaging_conversions 테이블에 재료별 1개당 무게(base_g) 입력
  2. 가격 계산 로직 수정: piece 단위지만 avg_price가 100g 기준이면 → 무게 환산해서 계산
"""

import mysql.connector
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fix_piece.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}

# ──────────────────────────────────────────────────────────────
# 재료별 1개(piece)당 무게 (g 기준)
# 한국 요리 기준 일반적인 크기
# ──────────────────────────────────────────────────────────────
PIECE_WEIGHT_G = {
    # 채소류
    "청양고추":     8,    # 청양고추 1개 ~8g
    "홍고추":      12,    # 홍고추 1개 ~12g
    "붉은고추":    12,
    "풋고추":      15,
    "오이고추":    20,
    "꽈리고추":     6,    # 꽈리고추 1개 ~6g
    "고추":         8,
    "건고추":       4,    # 건고추 1개 ~4g
    "건 고추":      4,
    "건홍고추":     4,

    "마늘":         5,    # 마늘 1쪽 ~5g
    "통마늘":       5,
    "깐마늘":       5,
    "다진마늘":     5,

    "양파":       200,    # 양파 1개 ~200g
    "다진 양파":  200,
    "감자":       150,    # 감자 1개 ~150g
    "고구마":     200,    # 고구마 1개 ~200g
    "당근":       150,    # 당근 1개 ~150g
    "애호박":     250,    # 애호박 1개 ~250g
    "오이":       200,    # 오이 1개 ~200g
    "가지":       150,    # 가지 1개 ~150g
    "토마토":     150,    # 토마토 1개 ~150g
    "방울토마토":  15,    # 방울토마토 1개 ~15g
    "대파":       100,    # 대파 1대 ~100g
    "무":         600,    # 무 1/4토막 기준 ~600g (레시피상 1개는 보통 1/4)
    "배추":      2000,    # 배추 1포기 ~2000g

    # 버섯류
    "표고버섯":    20,    # 표고버섯 1개 ~20g
    "느타리버섯":  50,    # 느타리버섯 한 줌 ~50g
    "팽이버섯":   100,    # 팽이버섯 1봉 ~100g
    "새송이":     100,    # 새송이버섯 1개 ~100g
    "새송이버섯": 100,
    "양송이버섯":  20,    # 양송이버섯 1개 ~20g

    # 해산물
    "오징어":     200,    # 오징어 1마리 ~200g
    "손질오징어": 200,
    "조개":       300,    # 조개 1봉 ~300g
    "바지락":     300,
    "홍합":        15,    # 홍합 1개 ~15g
    "홍합살":      10,
    "꽃게":       300,    # 꽃게 1마리 ~300g
    "전복":        80,    # 전복 1개 ~80g

    # 라면/면류
    "라면":       120,    # 라면 1봉 ~120g
    "진라면":     120,
    "너구리":     120,
    "곱창라면":   120,
    "짜파게티":   140,

    # 두부/가공품
    "두부":       300,    # 두부 1모 ~300g
    "순두부":     300,
    "게맛살":      20,    # 게맛살 1개 ~20g
    "소시지":      50,    # 소시지 1개 ~50g
    "빽소시지":    50,
    "어묵":        50,    # 어묵 1장 ~50g
    "사각어묵":    50,

    # 계란류 (이미 개당 가격이지만 혹시 모르니)
    # 달걀/계란은 API에서 piece 가격으로 받아옴 → 그대로 사용
    "깐 메추리알": 10,   # 메추리알 1개 ~10g

    # 과일
    "레몬":       150,    # 레몬 1개 ~150g
    "귤":         100,    # 귤 1개 ~100g
    "사과":       250,    # 사과 1개 ~250g
    "배":         400,    # 배 1개 ~400g

    # 향신료 (소량)
    "페퍼론치노":   1,    # 페퍼론치노 1개 ~1g
    "사천고추":     2,
    "시나몬 스틱":  3,

    # 기타
    "김":           2,    # 김 1장 ~2g
    "조미김":       2,
}

def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        log.info("DB 연결 성공")
    except Exception as e:
        log.error(f"DB 연결 실패: {e}")
        return

    # ── 1. ingredient_packaging_conversions 채우기 ──
    log.info("ingredient_packaging_conversions 입력 시작")
    conv_count = 0

    for name, weight_g in PIECE_WEIGHT_G.items():
        cur.execute("SELECT id, default_unit FROM ingredients WHERE name = %s", (name,))
        ing = cur.fetchone()
        if not ing:
            continue

        # piece 가격이 아닌 재료만 (default_unit = 'g' or NULL이면서 avg_price가 100g 기준인 것)
        ing_id = ing['id']

        # 기존 데이터 있으면 업데이트, 없으면 삽입
        cur.execute("""
            SELECT id FROM ingredient_packaging_conversions
            WHERE ingredient_id = %s AND pkg_unit_text = 'piece'
        """, (ing_id,))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE ingredient_packaging_conversions
                SET base_g = %s WHERE id = %s
            """, (weight_g, existing['id']))
        else:
            cur.execute("""
                INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
                VALUES (%s, 'piece', %s)
            """, (ing_id, weight_g))
        conv_count += 1

    conn.commit()
    log.info(f"ingredient_packaging_conversions {conv_count}개 입력 완료")

    # ── 2. 가격 재계산 (piece 단위 오류 수정 포함) ──
    log.info("레시피 비용 재계산 시작 (piece 수정 포함)")

    cur.execute("SELECT id, code, to_base, base_code FROM units")
    units = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT id, name, avg_price, default_unit FROM ingredients WHERE avg_price IS NOT NULL")
    ingredients = {r['id']: r for r in cur.fetchall()}

    # ingredient_id → piece당 무게 매핑
    cur.execute("""
        SELECT ingredient_id, base_g, base_ml
        FROM ingredient_packaging_conversions
        WHERE pkg_unit_text = 'piece'
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
        has = False

        for item in items:
            ing = ingredients.get(item['ingredient_id'])
            unit = units.get(item['unit_id'])
            if not ing or not unit or not item['amount'] or not item['unit_id']:
                continue

            try:
                amount = float(item['amount'])
                to_base = float(unit['to_base'])
                base_code = str(unit['base_code'])
                avg_price = float(ing['avg_price'])
                default_unit = ing['default_unit']
                base_amount = amount * to_base

                if base_code in ('g', 'ml'):
                    # 일반 케이스: g/ml 단위 → 100당 가격 기준
                    cost = (avg_price / 100.0) * base_amount

                elif base_code == 'piece':
                    # piece 단위일 때
                    if default_unit == 'piece':
                        # avg_price가 이미 개당 가격 (계란, 갈치 등)
                        cost = avg_price * base_amount
                    else:
                        # avg_price가 100g 기준인데 piece로 사용 중
                        # → ingredient_packaging_conversions에서 1개 무게 가져와서 환산
                        pw = piece_weights.get(item['ingredient_id'])
                        if pw and pw['base_g']:
                            grams = base_amount * float(pw['base_g'])
                            cost = (avg_price / 100.0) * grams
                        else:
                            # 변환 정보 없으면 합리적 기본값 (1개 = 50g으로 가정)
                            cost = (avg_price / 100.0) * base_amount * 50
                else:
                    continue

                total += cost
                has = True

            except Exception as e:
                continue

        if has and total > 0:
            cur.execute("UPDATE recipes SET estimated_cost = %s WHERE id = %s",
                        (round(total, 2), rid))
            updated += 1
        else:
            skipped += 1

    conn.commit()
    log.info(f"레시피 비용 계산: {updated}개 완료 / {skipped}개 스킵")

    # 결과 확인
    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL
        ORDER BY estimated_cost ASC LIMIT 10
    """)
    log.info("=== 비용 낮은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s}  {r['estimated_cost']:>10,.0f}원")

    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL
        ORDER BY estimated_cost DESC LIMIT 10
    """)
    log.info("=== 비용 높은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:42]:42s}  {r['estimated_cost']:>10,.0f}원")

    # 수정 전후 비교 (닭볶음)
    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE title LIKE '%마늘듬뿍%꽈리고추%닭볶음%'
    """)
    r = cur.fetchone()
    if r:
        log.info(f"\n닭볶음 수정 후: {r['estimated_cost']:,.0f}원 (수정 전: 108,460원)")

    cur.close()
    conn.close()
    log.info("완료")


if __name__ == "__main__":
    main()
