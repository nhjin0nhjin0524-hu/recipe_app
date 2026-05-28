"""
Aiven DB의 estimated_cost NULL 레시피 가격 계산
calc_public_cost.py와 동일한 로직, Aiven 연결
"""
import sys
import pymysql

sys.stdout.reconfigure(encoding='utf-8')

AIVEN = dict(
    host='mysql-2657d414-nhjin0nhjin0524-f196.d.aivencloud.com',
    port=21782, user='avnadmin', password='AVNS_X0ag18_z-mAK5vkZG9P',
    db='cooking_db', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
    ssl={'use_ssl': True}
)

def main():
    conn = pymysql.connect(**AIVEN)

    with conn.cursor() as cur:
        cur.execute("SELECT id, code, to_base, base_code FROM units")
        units = {r['id']: r for r in cur.fetchall()}

        cur.execute("SELECT id, avg_price, default_unit FROM ingredients WHERE avg_price IS NOT NULL")
        ingredients = {r['id']: r for r in cur.fetchall()}

        cur.execute("SELECT ingredient_id, base_g, base_ml FROM ingredient_packaging_conversions WHERE pkg_unit_text='piece'")
        piece_weights = {r['ingredient_id']: r for r in cur.fetchall()}

        cur.execute("SELECT id FROM recipes")
        recipe_ids = [r['id'] for r in cur.fetchall()]

    print(f"계산 대상: {len(recipe_ids)}개")

    updated = 0
    skipped = 0

    for rid in recipe_ids:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ri.ingredient_id, ri.amount, ri.unit_id
                FROM recipe_ingredients ri
                WHERE ri.recipe_id = %s AND ri.ingredient_id IS NOT NULL AND ri.unit_id IS NOT NULL
            """, (rid,))
            items = cur.fetchall()

        total = 0.0
        has_cost = False

        for item in items:
            ing = ingredients.get(item['ingredient_id'])
            unit = units.get(item['unit_id'])
            if not ing or not unit or not item['amount']:
                continue
            try:
                amount = float(item['amount'])
                to_base = float(unit['to_base'])
                base_code = str(unit['base_code'])
                avg_price = float(ing['avg_price'])
                base_amount = amount * to_base

                if base_code in ('g', 'ml'):
                    cost = (avg_price / 100.0) * base_amount
                elif base_code == 'piece':
                    if ing['default_unit'] == 'piece':
                        cost = avg_price * base_amount
                    else:
                        pw = piece_weights.get(item['ingredient_id'])
                        base_g = float(pw['base_g']) if pw and pw.get('base_g') else 50.0
                        cost = (avg_price / 100.0) * base_amount * base_g
                else:
                    continue

                total += cost
                has_cost = True
            except Exception:
                continue

        if has_cost and total >= 300:
            with conn.cursor() as cur:
                cur.execute("UPDATE recipes SET estimated_cost=%s WHERE id=%s", (round(total, 2), rid))
            updated += 1
        else:
            skipped += 1

    conn.commit()
    print(f"계산 완료: {updated}개 / 계산불가(재료 데이터 없음): {skipped}개")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as c FROM recipes WHERE estimated_cost IS NULL")
        print(f"잔여 NULL: {cur.fetchone()['c']}개")
        cur.execute("SELECT COUNT(*) as c FROM recipes WHERE estimated_cost IS NOT NULL")
        print(f"estimated_cost 있음: {cur.fetchone()['c']}개")

    conn.close()
    print("완료")

if __name__ == '__main__':
    main()
