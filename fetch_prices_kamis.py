"""
KAMIS(농산물유통정보) API로 재료 가격 업데이트
- 소매 기준 최근 가격 수집
- ingredients.avg_price (100g/ml 기준 또는 piece 기준) 업데이트
"""

import requests
import mysql.connector
import logging
import sys
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fetch_prices_kamis.log", encoding="utf-8", mode="w")
    ]
)
log = logging.getLogger(__name__)

CERT_KEY = "228e4781-4312-4c4c-9045-897a8803a2e8"
CERT_ID  = "1"
BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

DB_CONFIG = {
    "host": "localhost", "port": 3306, "database": "cooking_db",
    "user": "root", "password": "root", "charset": "utf8mb4"
}

# ── KAMIS 품목 코드 매핑 ──
# (DB재료명: (카테고리코드, 품목코드, 품종코드, 단위타입, convert_kg_yn))
#
# 단위타입:
#   'kg_to_100g'    → p_convert_kg_yn=Y로 1kg 가격 받아서 ÷10 → 100g 기준 저장
#   'piece_1'       → 낱개 1개 가격 → piece 기준 저장
#   'piece_per_10'  → 10개 묶음 가격 → ÷10 → 개당 가격 저장
KAMIS_MAP = {
    # ── 채소류 (200) / kg_to_100g: p_convert_kg_yn=Y 사용 ──
    "배추":          (200, 211, "00", "kg_to_100g"),
    "양배추":        (200, 212, "00", "kg_to_100g"),
    "시금치":        (200, 213, "00", "kg_to_100g"),
    "상추":          (200, 214, "00", "kg_to_100g"),
    "토마토":        (200, 225, "00", "kg_to_100g"),
    "딸기":          (200, 226, "00", "kg_to_100g"),
    "당근":          (200, 232, "00", "kg_to_100g"),
    "청양고추":      (200, 242, "00", "kg_to_100g"),
    "풋고추":        (200, 242, "00", "kg_to_100g"),
    "깐마늘":        (200, 258, "00", "kg_to_100g"),
    "다진마늘":      (200, 258, "00", "kg_to_100g"),
    "양파":          (200, 245, "00", "kg_to_100g"),
    "대파":          (200, 246, "00", "kg_to_100g"),
    "고춧가루":      (200, 248, "00", "kg_to_100g"),
    "굵은 고춧가루": (200, 248, "00", "kg_to_100g"),
    "고운 고춧가루": (200, 248, "00", "kg_to_100g"),
    "깻잎":          (200, 253, "00", "kg_to_100g"),
    "파프리카":      (200, 256, "00", "kg_to_100g"),   # 200g 묶음→kg 변환
    # ── 채소류 / piece ──
    "수박":          (200, 221, "00", "piece_1"),       # 1통
    "참외":          (200, 222, "00", "piece_per_10"),  # 10개 묶음
    "오이":          (200, 223, "00", "piece_1"),
    "애호박":        (200, 224, "00", "piece_1"),
    "무":            (200, 231, "00", "piece_1"),
    "가지":          (200, 251, "00", "piece_1"),
    # ── 식량작물 (100) ──
    "감자":          (100, 152, "01", "kg_to_100g"),
    "고구마":        (100, 151, "00", "kg_to_100g"),
    "콩":            (100, 141, "00", "kg_to_100g"),
    # ── 특용작물 (300) ──
    "참깨":          (300, 312, "00", "kg_to_100g"),
    "들깨":          (300, 313, "00", "kg_to_100g"),
    "느타리버섯":    (300, 315, "00", "kg_to_100g"),
    "팽이버섯":      (300, 316, "00", "kg_to_100g"),
    "새송이버섯":    (300, 317, "00", "kg_to_100g"),
    "표고버섯":      (300, 322, "00", "kg_to_100g"),
    # ── 과일류 (400) ──
    "사과":          (400, 411, "00", "piece_per_10"),  # 10개 묶음
    "배":            (400, 412, "00", "piece_per_10"),  # 10개 묶음
    "복숭아":        (400, 413, "00", "piece_per_10"),
    "포도":          (400, 414, "00", "kg_to_100g"),
    "귤":            (400, 415, "00", "piece_per_10"),  # 10개 묶음
    "바나나":        (400, 418, "00", "kg_to_100g"),
    # ── 축산물 (500) ──
    "달걀":          (500, 516, "00", "piece_1"),
    "계란":          (500, 516, "00", "piece_1"),
    "우유":          (500, 517, "00", "kg_to_100g"),
    "닭고기":        (500, 513, "00", "kg_to_100g"),
    "돼지고기":      (500, 512, "00", "kg_to_100g"),
    "쇠고기":        (500, 511, "00", "kg_to_100g"),
    # ── 수산물 (600) ──
    "고등어":        (600, 611, "00", "piece_1"),
    "갈치":          (600, 613, "00", "piece_1"),
    "오징어":        (600, 619, "00", "piece_1"),
    "멸치":          (600, 638, "00", "kg_to_100g"),
    "미역":          (600, 642, "00", "kg_to_100g"),
    "새우":          (600, 654, "00", "kg_to_100g"),
}


def fetch_kamis_price(category_code, item_code, kind_code, unit_type):
    """KAMIS API로 최근 소매 평균가격 조회"""
    end_day = datetime.today()
    start_day = end_day - timedelta(days=25)

    # kg_to_100g는 p_convert_kg_yn=Y로 1kg 단위로 통일, piece류는 N
    convert_kg = "Y" if unit_type == "kg_to_100g" else "N"

    params = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_startday": start_day.strftime("%Y-%m-%d"),
        "p_endday": end_day.strftime("%Y-%m-%d"),
        "p_itemcategorycode": str(category_code),
        "p_itemcode": str(item_code),
        "p_kindcode": kind_code,
        "p_productrankcode": "04",
        "p_countrycode": "1101",
        "p_convert_kg_yn": convert_kg,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=10)
        data = resp.json()
        d = data.get("data", {})
        if not isinstance(d, dict) or d.get("error_code") != "000":
            return None
        prices = []
        for item in d.get("item", []):
            p = item.get("price", "")
            if p and p != "-":
                try:
                    prices.append(float(p.replace(",", "")))
                except ValueError:
                    pass
        if prices:
            return sum(prices) / len(prices)
    except Exception as e:
        log.warning(f"  API 오류: {e}")
    return None


def calc_avg_price(raw_price, unit_type):
    """
    raw_price: API 반환 가격
    unit_type → ingredients.avg_price 저장 기준값
      kg_to_100g   : 1kg 가격 ÷ 10 → 100g 기준
      piece_1      : 1개 가격 그대로 저장
      piece_per_10 : 10개 묶음 가격 ÷ 10 → 1개 가격
    """
    if unit_type == "kg_to_100g":
        return round(raw_price / 10, 2)
    elif unit_type == "piece_1":
        return round(raw_price, 2)
    elif unit_type == "piece_per_10":
        return round(raw_price / 10, 2)
    return None


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    log.info("DB 연결 성공")

    updated = 0
    failed  = 0

    for ing_name, (cat, item, kind, unit_type) in KAMIS_MAP.items():
        log.info(f"조회: {ing_name} (cat={cat}, item={item}, type={unit_type})")
        raw = fetch_kamis_price(cat, item, kind, unit_type)

        if raw is None:
            log.warning(f"  → 가격 없음")
            failed += 1
            continue

        avg_price = calc_avg_price(raw, unit_type)
        log.info(f"  → raw={raw:,.0f}원  저장={avg_price:,.1f}원 ({unit_type})")

        cur.execute(
            "UPDATE ingredients SET avg_price = %s WHERE name = %s",
            (avg_price, ing_name)
        )
        if cur.rowcount > 0:
            updated += 1
        else:
            log.warning(f"  → DB에 '{ing_name}' 없음 (스킵)")

    conn.commit()
    log.info(f"\n=== 완료: {updated}개 업데이트 / {failed}개 가격 없음 ===")

    # 업데이트된 재료 확인
    names = list(KAMIS_MAP.keys())
    placeholders = ",".join(["%s"] * len(names))
    cur.execute(
        f"SELECT name, avg_price, default_unit FROM ingredients WHERE name IN ({placeholders}) ORDER BY name",
        names
    )
    log.info("\n=== 업데이트 결과 ===")
    for r in cur.fetchall():
        log.info(f"  {r['name']:15s} ({str(r['default_unit']):6}) → {float(r['avg_price']):,.1f}원")

    # 레시피 비용 재계산
    log.info("\n레시피 비용 재계산 중...")

    cur.execute("SELECT id, code, to_base, base_code FROM units")
    units = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT id, name, avg_price, default_unit FROM ingredients WHERE avg_price IS NOT NULL")
    ingredients = {r['id']: r for r in cur.fetchall()}

    cur.execute("SELECT ingredient_id, base_g, base_ml FROM ingredient_packaging_conversions WHERE pkg_unit_text = 'piece'")
    piece_weights = {r['ingredient_id']: r for r in cur.fetchall()}

    cur.execute("SELECT id FROM recipes")
    recipe_ids = [r['id'] for r in cur.fetchall()]

    cost_updated = 0
    for rid in recipe_ids:
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
            cost_updated += 1

    conn.commit()
    log.info(f"레시피 비용 재계산: {cost_updated}개 완료")

    # 결과 샘플
    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL ORDER BY estimated_cost LIMIT 10
    """)
    log.info("\n=== 비용 낮은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:40]:40s}  {float(r['estimated_cost']):>10,.0f}원")

    cur.execute("""
        SELECT title, estimated_cost FROM recipes
        WHERE estimated_cost IS NOT NULL ORDER BY estimated_cost DESC LIMIT 10
    """)
    log.info("\n=== 비용 높은 레시피 TOP 10 ===")
    for r in cur.fetchall():
        log.info(f"  {r['title'][:40]:40s}  {float(r['estimated_cost']):>10,.0f}원")

    cur.close()
    conn.close()
    log.info("완료")


if __name__ == "__main__":
    main()
