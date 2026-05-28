"""
로컬 공공데이터 레시피 → Aiven 동기화
- 없는 재료 ingredients에 추가
- recipe_ingredients 행 삽입 (external_id 기준 recipe_id 매핑)
- estimated_cost 복사
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
LOCAL = dict(
    host='localhost', port=3306, user='root', password='root',
    db='cooking_db', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
)

DRY_RUN = False


def main():
    aconn = pymysql.connect(**AIVEN)
    lconn = pymysql.connect(**LOCAL)

    with aconn.cursor() as acur, lconn.cursor() as lcur:
        # ── 1. recipe_id 매핑 (external_id 기준) ──
        lcur.execute("SELECT id, external_id, estimated_cost FROM recipes WHERE external_id LIKE %s", ('public_%',))
        local_recipes = {r['external_id']: r for r in lcur.fetchall()}

        acur.execute("SELECT id, external_id FROM recipes WHERE external_id LIKE %s", ('public_%',))
        aiven_recipes = {r['external_id']: r['id'] for r in acur.fetchall()}

        print(f"로컬 공공 레시피: {len(local_recipes)}개  Aiven: {len(aiven_recipes)}개")

        # ── 2. 재료 이름 매핑 ──
        lcur.execute("SELECT id, name, avg_price, default_unit FROM ingredients")
        local_ings = {r['id']: r for r in lcur.fetchall()}
        local_ings_by_name = {r['name']: r for r in local_ings.values()}

        acur.execute("SELECT id, name FROM ingredients")
        aiven_ings_by_name = {r['name']: r['id'] for r in acur.fetchall()}

        # ── 3. 로컬 공공 recipe_ingredients 수집 ──
        lcur.execute("""
            SELECT ri.recipe_id, ri.ingredient_id, ri.amount, ri.unit_id,
                   ri.name as ri_name, ri.sort_order, ri.note,
                   r.external_id
            FROM recipe_ingredients ri
            JOIN recipes r ON r.id = ri.recipe_id
            WHERE r.external_id LIKE %s
        """, ('public_%',))
        local_ri = lcur.fetchall()
        print(f"로컬 공공 recipe_ingredients: {len(local_ri)}개")

        # ── 4. 없는 재료 Aiven에 삽입 ──
        needed_names = set()
        for ri in local_ri:
            ing = local_ings.get(ri['ingredient_id'])
            if ing:
                needed_names.add(ing['name'])

        missing_names = needed_names - set(aiven_ings_by_name.keys())
        print(f"Aiven에 없는 재료: {len(missing_names)}개 → 삽입 예정")

        inserted_ings = 0
        for name in missing_names:
            local_ing = local_ings_by_name.get(name)
            if not local_ing:
                continue
            if not DRY_RUN:
                acur.execute(
                    "INSERT INTO ingredients (name, avg_price, default_unit) VALUES (%s, %s, %s)",
                    (name, local_ing['avg_price'], local_ing['default_unit'])
                )
                aiven_ings_by_name[name] = aconn.insert_id()
            inserted_ings += 1

        if not DRY_RUN:
            aconn.commit()
        print(f"재료 삽입 완료: {inserted_ings}개")

        # ── 5. Aiven recipe_ingredients 기존 행 삭제 (공공 레시피만) ──
        aiven_recipe_ids = list(aiven_recipes.values())
        if aiven_recipe_ids and not DRY_RUN:
            fmt = ','.join(['%s'] * len(aiven_recipe_ids))
            acur.execute(f"DELETE FROM recipe_ingredients WHERE recipe_id IN ({fmt})", aiven_recipe_ids)
            aconn.commit()
            print(f"기존 Aiven 공공 recipe_ingredients 삭제")

        # ── 6. recipe_ingredients 삽입 ──
        inserted_ri = 0
        skipped_ri = 0
        no_recipe = 0
        no_ing = 0

        for ri in local_ri:
            ext_id = ri['external_id']
            aiven_rid = aiven_recipes.get(ext_id)
            if not aiven_rid:
                no_recipe += 1
                continue

            ing = local_ings.get(ri['ingredient_id'])
            if not ing:
                skipped_ri += 1
                continue

            aiven_iid = aiven_ings_by_name.get(ing['name'])
            if not aiven_iid:
                no_ing += 1
                continue

            if not DRY_RUN:
                acur.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, name, ingredient_id, amount, unit_id, sort_order, note) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (aiven_rid, ri['ri_name'], aiven_iid, ri['amount'], ri['unit_id'], ri['sort_order'], ri['note'])
                )
            inserted_ri += 1

        if not DRY_RUN:
            aconn.commit()
        print(f"recipe_ingredients 삽입: {inserted_ri}개 / 레시피없음: {no_recipe} / 재료없음: {no_ing} / 스킵: {skipped_ri}")

        # ── 7. estimated_cost 복사 (external_id 기준) ──
        updated_cost = 0
        for ext_id, local_r in local_recipes.items():
            aiven_rid = aiven_recipes.get(ext_id)
            if not aiven_rid:
                continue
            cost = local_r['estimated_cost']
            if cost is not None and not DRY_RUN:
                acur.execute("UPDATE recipes SET estimated_cost=%s WHERE id=%s", (cost, aiven_rid))
                updated_cost += 1

        if not DRY_RUN:
            aconn.commit()
        print(f"estimated_cost 복사: {updated_cost}개")

        # ── 결과 확인 ──
        acur.execute("SELECT COUNT(*) as c FROM recipes WHERE estimated_cost IS NOT NULL")
        print(f"\nAiven estimated_cost 있음: {acur.fetchone()['c']}개")
        acur.execute("SELECT COUNT(*) as c FROM recipes WHERE estimated_cost IS NULL")
        print(f"Aiven estimated_cost NULL: {acur.fetchone()['c']}개")

    aconn.close()
    lconn.close()
    print("완료")


if __name__ == '__main__':
    main()
