/* ===============================
 * 0) 💣 기존 스키마 정리 (있으면 제거)
 *    ⚠️ 데이터가 있으면 반드시 백업 후 실행!
 * =============================== */
DROP DATABASE IF EXISTS cooking_db;

/* ===============================
 * 1) DB 생성 & 선택
 * =============================== */
CREATE DATABASE cooking_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;
USE cooking_db;

/* ===============================
 * 2) 테이블 생성 (표준 스키마)
 * =============================== */

-- users
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255),
  name VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ingredients (공통 재료 마스터)
CREATE TABLE ingredients (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  default_unit VARCHAR(50),
  avg_price DECIMAL(10,2),
  shelf_life_days INT,
  UNIQUE KEY uq_ingredients_name (name)
) ENGINE=InnoDB;

-- recipe_categories (계층 가능)
CREATE TABLE recipe_categories (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  parent_id BIGINT UNSIGNED,
  CONSTRAINT fk_recipe_categories_parent
    FOREIGN KEY (parent_id) REFERENCES recipe_categories(id)
    ON DELETE SET NULL
) ENGINE=InnoDB;

-- recipes (⭐ 표준 PK: id)
CREATE TABLE recipes (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  author_id BIGINT UNSIGNED,
  category_id BIGINT UNSIGNED,
  title VARCHAR(200) NOT NULL,
  description TEXT,
  thumbnail_url TEXT,
  cook_time_min INT,
  servings INT,
  difficulty VARCHAR(50),
  estimated_cost DECIMAL(10,2),
  is_minimal TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_recipes_author
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_recipes_category
    FOREIGN KEY (category_id) REFERENCES recipe_categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;
-- recipe_tags
CREATE TABLE recipe_tags (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- recipe_tag_map (N:N)  ← 이제 recipes(id)로 안전하게 참조됨
CREATE TABLE recipe_tag_map (
  recipe_id BIGINT UNSIGNED NOT NULL,
  tag_id    BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (recipe_id, tag_id),
  CONSTRAINT fk_rtm_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  CONSTRAINT fk_rtm_tag    FOREIGN KEY (tag_id)    REFERENCES recipe_tags(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- units (단위 표준화 마스터)
CREATE TABLE units (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,      -- 'g','ml','cup','tbsp','tsp','piece' 등
  display_name VARCHAR(50) NOT NULL,     -- UI 표기: 'g','ml','컵','큰술' 등
  to_base DECIMAL(10,4) NULL,            -- 같은 계열 환산 값 (예: ml 계열이면 1컵=200)
  base_code VARCHAR(50) NULL             -- 기준 단위 코드 (예: 'ml','g','piece')
) ENGINE=InnoDB;

-- recipe_ingredients (단위 표준화 FK 포함)
CREATE TABLE recipe_ingredients (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipe_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(200) NOT NULL,            -- 원문 재료명(표시용)
  amount VARCHAR(100),                   -- 원문 수량 문자열(백업/표시용)
  ingredient_id BIGINT UNSIGNED,         -- 공통 재료 매칭 시
  unit_id BIGINT UNSIGNED,               -- 표준 단위 매칭 시
  sort_order INT DEFAULT 1,
  CONSTRAINT fk_ri_recipe     FOREIGN KEY (recipe_id)    REFERENCES recipes(id)      ON DELETE CASCADE,
  CONSTRAINT fk_ri_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE SET NULL,
  CONSTRAINT fk_ri_unit       FOREIGN KEY (unit_id)       REFERENCES units(id)        ON DELETE SET NULL
) ENGINE=InnoDB;

-- recipe_steps
CREATE TABLE recipe_steps (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipe_id BIGINT UNSIGNED NOT NULL,
  step_no INT NOT NULL,
  content TEXT NOT NULL,
  image_url TEXT,
  CONSTRAINT fk_rs_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  UNIQUE KEY uq_recipe_step (recipe_id, step_no)
) ENGINE=InnoDB;

-- favorites
CREATE TABLE favorites (
  user_id BIGINT UNSIGNED NOT NULL,
  recipe_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, recipe_id),
  CONSTRAINT fk_fav_user   FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
  CONSTRAINT fk_fav_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- recipe_nutrition (레시피별 영양정보)
CREATE TABLE recipe_nutrition (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipe_id BIGINT UNSIGNED NOT NULL,
  basis ENUM('per_serving','per_recipe','per_100g') NOT NULL DEFAULT 'per_serving',
  calories DECIMAL(10,2),
  carbs DECIMAL(10,2),
  protein DECIMAL(10,2),
  fat DECIMAL(10,2),
  sugar DECIMAL(10,2),
  sodium DECIMAL(10,2),
  fiber DECIMAL(10,2),
  extra JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_recipe_nutrition (recipe_id, basis),
  CONSTRAINT fk_rn_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ingredient_nutrition (선택: 재료 원천 영양정보)
CREATE TABLE ingredient_nutrition (
  ingredient_id BIGINT UNSIGNED PRIMARY KEY,
  basis ENUM('per_100g','per_piece') NOT NULL DEFAULT 'per_100g',
  calories DECIMAL(10,2),
  carbs DECIMAL(10,2),
  protein DECIMAL(10,2),
  fat DECIMAL(10,2),
  sugar DECIMAL(10,2),
  sodium DECIMAL(10,2),
  fiber DECIMAL(10,2),
  extra JSON,
  CONSTRAINT fk_in_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- user_pantry (유저 냉장고 보유 재료)
CREATE TABLE user_pantry (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  ingredient_id BIGINT UNSIGNED,
  custom_name VARCHAR(100),
  quantity DECIMAL(10,2),
  unit VARCHAR(50),                        -- 원문 단위(표시/백업)
  purchased_at DATE,
  expires_at DATE,
  is_finished TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_up_user       FOREIGN KEY (user_id)      REFERENCES users(id)       ON DELETE CASCADE,
  CONSTRAINT fk_up_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- user_pantry_logs (사용/폐기 기록)
CREATE TABLE user_pantry_logs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  pantry_id BIGINT UNSIGNED NOT NULL,
  action_type ENUM('use','discard','edit') NOT NULL,
  quantity DECIMAL(10,2),
  note TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_upl_pantry FOREIGN KEY (pantry_id) REFERENCES user_pantry(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- user_notifications (알림함)
CREATE TABLE user_notifications (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  type VARCHAR(50) NOT NULL,         -- 'expiry','budget', ...
  title VARCHAR(200),
  message TEXT,
  related_pantry_id BIGINT UNSIGNED,
  is_read TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_un_user   FOREIGN KEY (user_id)          REFERENCES users(id)       ON DELETE CASCADE,
  CONSTRAINT fk_un_pantry FOREIGN KEY (related_pantry_id) REFERENCES user_pantry(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- expense_categories (지출 카테고리)
CREATE TABLE expense_categories (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  sort_order INT DEFAULT 1,
  UNIQUE KEY uq_exp_cat_name (name)
) ENGINE=InnoDB;

-- user_expenses (유저 지출)
CREATE TABLE user_expenses (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  category_id BIGINT UNSIGNED,
  amount DECIMAL(10,2) NOT NULL,
  memo TEXT,
  spent_at DATE NOT NULL,
  recipe_id BIGINT UNSIGNED,   -- 특정 레시피 때문인 지출(선택)
  pantry_id BIGINT UNSIGNED,   -- 냉장고 항목과 직접 연결(선택)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ue_user     FOREIGN KEY (user_id)    REFERENCES users(id)         ON DELETE CASCADE,
  CONSTRAINT fk_ue_category FOREIGN KEY (category_id) REFERENCES expense_categories(id) ON DELETE SET NULL,
  CONSTRAINT fk_ue_recipe   FOREIGN KEY (recipe_id)  REFERENCES recipes(id)       ON DELETE SET NULL,
  CONSTRAINT fk_ue_pantry   FOREIGN KEY (pantry_id)  REFERENCES user_pantry(id)   ON DELETE SET NULL
) ENGINE=InnoDB;

-- user_monthly_budget (월별 예산)
CREATE TABLE user_monthly_budget (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  year INT NOT NULL,
  month INT NOT NULL,
  budget_amount DECIMAL(10,2) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_month_budget (user_id, year, month),
  CONSTRAINT fk_umb_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

/* ===============================
 * 3) 기본 시드 데이터
 * =============================== */

CREATE TABLE IF NOT EXISTS ingredient_prices (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ingredient_id BIGINT UNSIGNED NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'KRW',
  price_per_g DECIMAL(12,4) NULL,
  price_per_ml DECIMAL(12,4) NULL,
  price_per_piece DECIMAL(12,4) NULL,
  source VARCHAR(100),
  region VARCHAR(50),
  effective_date DATE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ing_date (ingredient_id, effective_date),
  CONSTRAINT fk_ip_ingredient
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;
-- ingredient_prices 테이블에 복합 고유 키 추가
-- 중복된 ingredient_id, effective_date, source 조합 중 
-- ID가 가장 크지 않은 (가장 최신이 아닌) 레코드를 삭제합니다.
-- 1. g당 가격 컬럼명을 100g당 가격으로 변경
ALTER TABLE ingredient_prices
RENAME COLUMN price_per_g TO price_per_100g;

-- 2. ml당 가격 컬럼명을 100ml당 가격으로 변경
ALTER TABLE ingredient_prices
RENAME COLUMN price_per_ml TO price_per_100ml;

-- 단위 표준 세트 (팀 룰: cup=200ml)
INSERT INTO units (code, display_name, to_base, base_code) VALUES
-- 질량 (base=g)
('g',     'g',       1.0000, 'g'),
('kg',    'kg',   1000.0000, 'g'),
-- 부피 (base=ml)
('ml',    'ml',      1.0000, 'ml'),
('l',     'L',    1000.0000, 'ml'),
('tsp',   '작은술',  5.0000, 'ml'),
('tbsp',  '큰술',   15.0000, 'ml'),
('cup',   '컵',    200.0000, 'ml'),
-- 개수 (base=piece)
('piece', '개',      1.0000, 'piece'),
('half',  '1/2개',   0.5000, 'piece')
ON DUPLICATE KEY UPDATE display_name=VALUES(display_name),
                        to_base=VALUES(to_base),
                        base_code=VALUES(base_code);
                        
-- 단위 테이블
/* ===============================
 * 4) 🚨 가격 정제를 위한 새 테이블 추가
 * (기존 units 테이블과 용도 다름)
 * =============================== */
USE cooking_db;

CREATE TABLE ingredient_packaging_conversions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ingredient_id BIGINT UNSIGNED NOT NULL COMMENT 'ingredients.id (FK)',
  
  pkg_unit_text VARCHAR(20) NOT NULL COMMENT '파싱된 포장 단위 (예: 단, 팩, 병, 근)',
  
  base_g DECIMAL(10, 2) NULL COMMENT 'g 환산값 (예: 250.0)',
  base_ml DECIMAL(10, 2) NULL COMMENT 'ml 환산값 (예: 1000.0)',
  
  -- (재료ID, 단위텍스트) 조합은 유일해야 함
  UNIQUE KEY uq_ing_pkg_unit (ingredient_id, pkg_unit_text),
  
  CONSTRAINT fk_ipc_ingredient
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

/* ===============================
 * 5) 🚨 (필수) 변환 기준 데이터 삽입
 * (이 데이터가 많을수록 정제 품질이 올라갑니다)
 * =============================== */
-- ❗️주의: '시금치' 등이 ingredients 테이블에 먼저 존재해야 합니다!
-- (스크립트 2단계(normalize_ingredient_names)가 실행된 후 삽입하는 것을 권장)

-- 예시 데이터 (g)
INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '단', 250.0 FROM ingredients WHERE name = '시금치' ON DUPLICATE KEY UPDATE base_g=250.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '봉', 150.0 FROM ingredients WHERE name = '시금치' ON DUPLICATE KEY UPDATE base_g=150.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '단', 300.0 FROM ingredients WHERE name = '대파' ON DUPLICATE KEY UPDATE base_g=300.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '모', 300.0 FROM ingredients WHERE name = '두부' ON DUPLICATE KEY UPDATE base_g=300.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '개', 55.0 FROM ingredients WHERE name = '달걀' ON DUPLICATE KEY UPDATE base_g=55.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '판', 1650.0 FROM ingredients WHERE name = '달걀' ON DUPLICATE KEY UPDATE base_g=1650.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_g)
SELECT id, '근', 600.0 FROM ingredients WHERE name = '돼지고기' ON DUPLICATE KEY UPDATE base_g=600.0;

-- 예시 데이터 (ml)
INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_ml)
SELECT id, '팩', 1000.0 FROM ingredients WHERE name = '우유' ON DUPLICATE KEY UPDATE base_ml=1000.0;

INSERT INTO ingredient_packaging_conversions (ingredient_id, pkg_unit_text, base_ml)
SELECT id, '병', 930.0 FROM ingredients WHERE name = '간장' ON DUPLICATE KEY UPDATE base_ml=930.0;

-- 지출 카테고리 기본값
INSERT INTO expense_categories (name, sort_order) VALUES
('식료품', 1),
('배달', 2),
('외식', 3),
('간식', 4)
ON DUPLICATE KEY UPDATE sort_order=VALUES(sort_order);
-- 재료 가격 넣기


-- 확인용 쿼리
SELECT * FROM users                LIMIT 3;
SELECT * FROM ingredients          LIMIT 300;
SELECT * FROM recipes              LIMIT 300;
SELECT * FROM recipe_categories    LIMIT 3;
SELECT * FROM recipe_tags          LIMIT 3;
SELECT * FROM recipe_tag_map       LIMIT 3;
SELECT * FROM units                LIMIT 3;
SELECT * FROM recipe_ingredients   LIMIT 3;
SELECT * FROM recipe_steps         LIMIT 100;
SELECT * FROM favorites            LIMIT 3;
SELECT * FROM recipe_nutrition     LIMIT 3;
SELECT * FROM ingredient_nutrition LIMIT 3;
SELECT * FROM user_pantry          LIMIT 3;
SELECT * FROM user_pantry_logs     LIMIT 3;
SELECT * FROM user_notifications   LIMIT 3;
SELECT * FROM expense_categories   LIMIT 3;
SELECT * FROM user_expenses        LIMIT 3;
SELECT * FROM user_monthly_budget  LIMIT 3;

SELECT *
FROM ingredient_prices
ORDER BY effective_date DESC, id DESC
LIMIT 10;

SET NAMES utf8mb4;
USE cooking_db;

SELECT COUNT(*) AS ingredients_cnt FROM ingredients;
SELECT COUNT(*) AS prices_cnt FROM ingredient_prices;

SELECT i.name, p.price_per_g, p.price_per_ml, p.effective_date
FROM ingredients i
LEFT JOIN v_latest_ingredient_price p ON p.ingredient_id = i.id
ORDER BY i.name
LIMIT 30;
USE cooking_db;
-- 재료 가격확인
SELECT 
    (SELECT COUNT(*) FROM ingredients) AS '등록된_재료_수',
    (SELECT COUNT(*) FROM ingredient_prices) AS '저장된_가격정보_수';

SELECT 
    i.name AS '재료명',
    i.default_unit AS '기준단위',
    p.price_per_100g AS '100g당_가격',
    p.price_per_100ml AS '100ml당_가격',
    p.price_per_piece AS '개당_가격',
    p.source AS '판매처(시장/마트)',
    p.region AS '지역(구)',
    p.effective_date AS '기준일자'
FROM ingredients i
JOIN ingredient_prices p ON i.id = p.ingredient_id
ORDER BY p.id DESC  -- 가장 최근에 들어간 데이터부터 보기
LIMIT 500;           -- 50개만 조회
--
SELECT 
    i.id AS 'ID',
    i.name AS '재료명',
    
    -- 유통기한 확인 (ingredients 테이블)
    CONCAT(i.shelf_life_days, '일') AS '유통기한',
    
    -- 영양성분 확인 (ingredient_nutrition 테이블)
    CONCAT(FORMAT(n.calories, 1), ' kcal') AS '칼로리(100g)',
    CONCAT(FORMAT(n.carbs, 1), ' g') AS '탄수화물',
    CONCAT(FORMAT(n.protein, 1), ' g') AS '단백질',
    CONCAT(FORMAT(n.fat, 1), ' g') AS '지방'
    
FROM ingredients i
LEFT JOIN ingredient_nutrition n ON i.id = n.ingredient_id
WHERE i.shelf_life_days IS NOT NULL  -- 데이터가 들어간 것만 조회
ORDER BY i.name ASC;                 -- 이름순 정렬