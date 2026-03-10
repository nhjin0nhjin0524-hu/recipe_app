# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**AI 냉장고 요리사** - 사용자 냉장고 재료 기반 레시피 추천 앱.
- 백종원 YouTube 채널 레시피 333개를 크롤링해 MySQL DB에 적재
- Streamlit UI로 냉장고 관리, 레시피 추천, 식비 통계 제공
- 영수증 OCR(네이버 CLOVA)로 재료 자동 등록

## 앱 실행

```bash
streamlit run uiux.py
# 또는 최신 버전
streamlit run uiux2.py
```

## DB 연결 정보

- **DB**: MySQL `cooking_db` (localhost:3306)
- **계정**: root / root
- **문자셋**: utf8mb4
- 스키마 초기화: `앱레시피1.sql` 실행 (⚠️ DROP DATABASE 포함)
- 데이터 로드: `load.sql`

Python에서 연결 시 `pymysql`(uiux.py) 또는 `mysql.connector`(fix_*.py) 둘 다 사용 중.
한글 출력 시 반드시 `sys.stdout.reconfigure(encoding='utf-8')` 추가.

## DB 핵심 스키마

```
ingredients         재료 마스터 (avg_price: 100g/ml 기준 원화, piece는 1개 가격)
units               단위 마스터 (g, ml, cup, tbsp, tsp, piece / to_base, base_code로 환산)
recipes             레시피 (estimated_cost, cook_time_min, servings, thumbnail_url 등)
recipe_ingredients  레시피-재료 연결 (amount 원문, ingredient_id FK, unit_id FK)
ingredient_packaging_conversions  piece 단위 재료의 1개당 g/ml 무게 저장
user_pantry         유저 냉장고 재료 (expires_at 기반 유통기한 알림)
```

### 가격 계산 로직 (`estimated_cost`)

`recipe_ingredients`의 amount × unit 환산 → base_code 기준:
- `g` / `ml`: `(avg_price / 100) × base_amount`
- `piece` + default_unit=`piece`: `avg_price × 개수`
- `piece` + default_unit=`g`: `(avg_price / 100) × piece_weight(g) × 개수` (ingredient_packaging_conversions 참조)

## 데이터 파이프라인 스크립트 (실행 순서)

| 스크립트 | 역할 |
|---|---|
| `재료별가격데이터최종.ipynb` | 서울시 생필품 가격 API로 66개 재료 단가 수집 |
| `fix_ingredient_matching.py` | API 미수록 재료 134개 단가 직접 입력, 잘못된 매핑 초기화 |
| `fix_piece_unit.py` | piece 단위 재료 62개의 1개당 무게(g) 입력, 가격 재계산 |
| `fix_null_unit.py` | unit_id NULL 재료 자동 배정 (키워드 기반 piece/tbsp) + 비용 재계산 |
| `fix_null_amount.py` | amount NULL 재료 타 레시피 평균값 또는 기본값으로 채움 |
| `fetch_servings_cooktime.py` | YouTube API로 servings, cook_time_min, thumbnail_url 추출 |

각 스크립트는 독립 실행 가능하며 실행 결과를 동명의 `.log` 파일에 기록.

## 외부 API

- **서울시 생필품 가격**: `ListNecessariesPricesService` (이마트 기준 66개 품목)
- **YouTube Data API v3**: `developerKey` 사용, 50개씩 batch 요청
- **네이버 CLOVA OCR**: 영수증 이미지 → 재료명 추출 (uiux.py)
- **KAMIS (농산물유통정보)**: `p_cert_key` + `p_cert_id` 필요, 엔드포인트 `http://www.kamis.or.kr/service/price/xml.do`

## 알려진 데이터 품질 이슈

- `recipe_ingredients`에 ingredient_id NULL 231개 (섹션 헤더가 재료로 잘못 크롤링)
- unit_id NULL 165개 (amount는 있으나 단위 배정 실패)
- `estimated_cost` 이상값: 수박화채 301원(수박 단가 누락), 소갈비찜 326,483원 등
- `cook_time_min` 1분으로 잡힌 오감지 약 10개 (설명문 내 조리 단계 시간을 총 조리시간으로 오인)
