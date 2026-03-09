USE cooking_db;

SET NAMES utf8mb4;
SET sql_safe_updates = 0;

/* ✅ 0) local_infile 관련
   - Workbench에서 권한 없으면 SET GLOBAL에서 에러날 수 있어.
   - 에러나면 이 줄은 주석 처리하고,
     터미널에서 mysql --local-infile=1 로 실행하는 게 제일 확실함.
*/
-- SET GLOBAL local_infile = 1;

/* =========================================================
   1) recipes에 external_id 컬럼 + UNIQUE 인덱스 (구버전 호환)
========================================================= */
SET @db := DATABASE();

-- 컬럼 존재 여부 체크 후 추가
SELECT COUNT(*) INTO @col_exists
FROM information_schema.columns
WHERE table_schema = @db
  AND table_name = 'recipes'
  AND column_name = 'external_id';

SET @sql := IF(
  @col_exists = 0,
  'ALTER TABLE recipes ADD COLUMN external_id VARCHAR(32) NULL',
  'SELECT ''external_id already exists'' AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 인덱스 존재 여부 체크 후 추가
SELECT COUNT(*) INTO @idx_exists
FROM information_schema.statistics
WHERE table_schema = @db
  AND table_name = 'recipes'
  AND index_name = 'uq_recipes_external_id';

SET @sql := IF(
  @idx_exists = 0,
  'ALTER TABLE recipes ADD UNIQUE KEY uq_recipes_external_id (external_id)',
  'SELECT ''uq_recipes_external_id already exists'' AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

/* =========================================================
   2) staging 테이블 생성
========================================================= */
DROP TABLE IF EXISTS stg_recipe_steps;
CREATE TABLE stg_recipe_steps (
  recipe_external_id VARCHAR(32) NOT NULL,
  title VARCHAR(255) NULL,
  step_no INT NOT NULL,
  content TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS stg_recipe_ingredients;
CREATE TABLE stg_recipe_ingredients (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipe_external_id VARCHAR(32) NOT NULL,
  ingredient_name_norm VARCHAR(200) NOT NULL,
  quantity DECIMAL(10,3) NULL,
  unit_code VARCHAR(50) NULL,
  base_quantity DECIMAL(10,3) NULL,
  note VARCHAR(255) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

/* =========================================================
   3) CSV → staging LOAD
   ✅ 윈도우 CSV면 보통 \r\n 이라 이걸 기본값으로 둠
   - 만약 행이 뭉개지면 '\n' 으로 바꿔서 다시 실행해.
========================================================= */

-- (A) steps CSV
LOAD DATA LOCAL INFILE 'C:/Users/alstj/Desktop/GP/Baekrecipestep.csv'
INTO TABLE stg_recipe_steps
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(recipe_external_id, title, step_no, content);

-- (B) ingredients CSV
LOAD DATA LOCAL INFILE 'C:/Users/alstj/Desktop/GP/Baekingredient.csv'
INTO TABLE stg_recipe_ingredients
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(recipe_external_id, ingredient_name_norm, quantity, unit_code, base_quantity, note);

/* =========================================================
   4) recipes 채우기 (external_id 기준 upsert)
========================================================= */
INSERT INTO recipes (external_id, title)
SELECT s.recipe_external_id,
       COALESCE(NULLIF(TRIM(s.title), ''), '제목미상')
FROM (
  SELECT recipe_external_id, MAX(title) AS title
  FROM stg_recipe_steps
  GROUP BY recipe_external_id
) s
ON DUPLICATE KEY UPDATE
  title = VALUES(title),
  updated_at = CURRENT_TIMESTAMP;

/* =========================================================
   5) recipe_steps 채우기 (recipe_id 매핑해서 insert/update)
========================================================= */
INSERT INTO recipe_steps (recipe_id, step_no, content, image_url)
SELECT r.id, s.step_no, s.content, NULL
FROM stg_recipe_steps s
JOIN recipes r ON r.external_id = s.recipe_external_id
ON DUPLICATE KEY UPDATE
  content = VALUES(content);

/* =========================================================
   6) ingredients 마스터 채우기 (없으면 생성)
========================================================= */
INSERT IGNORE INTO ingredients (name)
SELECT DISTINCT TRIM(ingredient_name_norm)
FROM stg_recipe_ingredients
WHERE TRIM(ingredient_name_norm) <> '';

/* =========================================================
   7) recipe_ingredients 채우기
   - 누적 방지: 이번 배치에 해당하는 레시피만 기존 재료 삭제 후 재삽입
   - ✅ ROW_NUMBER() 대신 MySQL 변수로 sort_order 생성 (5.7 호환)
========================================================= */
DELETE ri
FROM recipe_ingredients ri
JOIN recipes r ON r.id = ri.recipe_id
JOIN (SELECT DISTINCT recipe_external_id FROM stg_recipe_ingredients) x
  ON x.recipe_external_id = r.external_id;

-- 변수 초기화
SET @cur_recipe := 0;
SET @rn := 0;

INSERT INTO recipe_ingredients
(recipe_id, name, amount, ingredient_id, unit_id, sort_order)
SELECT
  t.recipe_id,
  t.name,
  t.amount,
  t.ingredient_id,
  t.unit_id,
  t.sort_order
FROM (
  SELECT
    r.id AS recipe_id,
    s.ingredient_name_norm AS name,

    -- amount: "2 큰술 (다진)" 같은 표시용 문자열
    NULLIF(TRIM(
      CONCAT(
        CASE
          WHEN s.quantity IS NULL THEN ''
          WHEN s.quantity = FLOOR(s.quantity) THEN CAST(FLOOR(s.quantity) AS CHAR)
          ELSE CAST(s.quantity AS CHAR)
        END,
        CASE
          WHEN s.quantity IS NULL THEN ''
          WHEN u.display_name IS NOT NULL THEN CONCAT(' ', u.display_name)
          WHEN s.unit_code IS NOT NULL AND TRIM(s.unit_code) <> '' THEN CONCAT(' ', s.unit_code)
          ELSE ''
        END,
        CASE
          WHEN s.note IS NOT NULL AND TRIM(s.note) <> '' THEN CONCAT(' (', TRIM(s.note), ')')
          ELSE ''
        END
      )
    ), '') AS amount,

    ing.id AS ingredient_id,
    u.id AS unit_id,

    -- ✅ recipe별로 1부터 증가
    (@rn := IF(@cur_recipe = r.id, @rn + 1, 1)) AS sort_order,
    (@cur_recipe := r.id) AS _set_cur

  FROM stg_recipe_ingredients s
  JOIN recipes r ON r.external_id = s.recipe_external_id
  LEFT JOIN ingredients ing ON ing.name = TRIM(s.ingredient_name_norm)
  LEFT JOIN units u ON u.code = TRIM(s.unit_code)
  ORDER BY r.id, s.id
) t;

/* =========================================================
   8) 결과 확인
========================================================= */
SELECT COUNT(*) AS recipes_loaded
FROM recipes
WHERE external_id IS NOT NULL;

SELECT COUNT(*) AS steps_loaded
FROM recipe_steps rs
JOIN recipes r ON r.id = rs.recipe_id
WHERE r.external_id IS NOT NULL;

SELECT COUNT(*) AS ingredients_loaded
FROM recipe_ingredients ri
JOIN recipes r ON r.id = ri.recipe_id
WHERE r.external_id IS NOT NULL;
