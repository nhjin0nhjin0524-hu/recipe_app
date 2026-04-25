# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests, uuid, time, json, pymysql, re
import plotly.express as px
from datetime import datetime, timedelta
import random
# --- [안전한 이모지 사전] SyntaxError 방지를 위해 유니코드로 정의합니다 ---
EMO_DASH = "\U0001F4CA"   # 📊
EMO_RECIPE = "\U0001F374" # 🍴
EMO_FRIDGE = "\U0001FAD9" # 🫙
EMO_CASH = "\U0001F4C8"   # 📈
EMO_HEART = "\U00002764"  # ❤️
EMO_EMPTY_HEART = "\U0001F90D" # 🤍 (또는 🤍)
EMO_MONEY = "\U0001F4B8"  # 💸
EMO_VEGE = "\U0001F966"   # 🥦
EMO_ALERT = "\U0001F6A8"  # 🚨
EMO_SEARCH = "\U0001F50D" # 🔍
EMO_PLUS = "\U00002795"   # ➕
EMO_PENCIL = "\U0000270F" # ✏️
EMO_SCALE = "\U00002696"  # ⚖️
EMO_TRASH = "\U0001F5D1"  # 🗑️
EMO_SAVE = "\U0001F4BE"   # 💾
EMO_HELLO = "\U0001F44B"  # 👋
EMO_BAG = "\U0001F45C"    # 👜
EMO_CAMERA = "\U0001F4F7" # 📷
EMO_KEY = "\U00002328"    # ⌨️
EMO_PEOPLE = "\U0001F46A" # 👨‍👩‍👧‍👦
EMO_FOLDER = "\U0001F4C1" # 📁
EMO_STAR = "\U00002728"   # ✨
EMO_BROOM = "\U0001FE9A"  # 🧹
EMO_DICE = "\U0001F3B2"   # 🎲
EMO_DOWN = "\U0001F53D"   # 🔽
EMO_UP = "\U0001F53C"     # 🔼

# --- 1. 페이지 설정 및 디자인 ---

st.set_page_config(page_title="AI 냉장고 요리사", layout="wide") # 👈 이 줄 끝에 )가 잘 닫혔는지 꼭 확인!



st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        max-width: 100vw !important;
        overflow-x: hidden !important;
        font-family: 'Pretendard', sans-serif;
    }

    /* 🚨 1. [메뉴바 전용] 5칸짜리 컬럼만 한 줄로 강제 고정 */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 2px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(5)) > [data-testid="column"] {
        flex: 1 1 20% !important;
        min-width: 0px !important;
    }

    /* 🚨 2. [나머지 일반 컬럼] 냉장고 등은 화면이 좁으면 밑으로 자연스럽게 떨어지게 허용 */
    div[data-testid="stHorizontalBlock"]:not(:has(> div:nth-child(5))) {
        flex-wrap: wrap !important;
    }

    /* 기본 버튼 디자인 */
    .stButton > button {
        width: 100% !important;
        border-radius: 12px;
        padding: 0px !important;
        white-space: nowrap !important;
    }
    .stButton > button div[data-testid="stMarkdownContainer"] p {
        font-weight: 800 !important;
        margin: 0 !important;
    }

    /* 📱 3. 모바일 전용 최적화 */
    @media (max-width: 768px) {
        /* 상단 메뉴 버튼 크기 유지 */
        .stButton > button { height: 32px !important; }
        .stButton > button div[data-testid="stMarkdownContainer"] p { font-size: 8.5px !important; letter-spacing: -0.5px !important; }

        /* 대시보드 및 전체 폰트 축소 */
        .main-title { font-size: 22px !important; margin-bottom: 5px !important; }
        h3, .stMarkdown h3 { font-size: 15px !important; }
        
        /* 💡 냉장고 카드 모바일 2열(50%) 배치 */
        div[data-testid="stHorizontalBlock"]:not(:has(> div:nth-child(5))) > [data-testid="column"] {
            min-width: 48% !important;
            flex: 1 1 48% !important;
            padding: 0 4px !important;
            margin-bottom: 10px !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. OCR 설정 및 DB 연결 함수 ---
INVOKE_URL = "https://ccse0ls88v.apigw.ntruss.com/custom/v1/50582/7e4ce7a941fe74d6ee3c56235520aaeb568c2b28b69643d6e51e513aa4360eff/document/receipt"
SECRET_KEY = "cFlNcHRFdXN2VmxUUFZDRGlzTkVSeU5oRW5CcXFIQUY="

def get_db_connection():
    return pymysql.connect(
        host='mysql-2657d414-nhjin0nhjin0524-f196.d.aivencloud.com',
        port=21782,
        user='avnadmin',
        password='AVNS_X0ag18_z-mAK5vkZG9P',
        db='cooking_db',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
		ssl={'use_ssl': True}
    )

# 💡 [스마트 단위 추론기] 식재료 이름을 보고 가장 자연스러운 단위를 찰떡같이 찾아냅니다!
def guess_item_unit(item_name):
    name = item_name.replace(" ", "") # 띄어쓰기 제거 후 검사
    
    ## 1. 액체 및 양념류 (ml)
    # 💡 '물'이라는 한 글자 때문에 콩나물, 해물이 잡히는 것을 막기 위해 '생수', '탄산수' 등으로 구체화!
    if any(k in name for k in ["우유", "생수", "식용유", "기름", "올리브유", "카놀라유", "간장", "식초", "참기름", "들기름", "액젓", "맛술", "미림", "주스", "콜라", "사이다", "소스", "드레싱", "케첩", "마요네즈"]):
        return "ml"
        
    # 💡 만약 진짜 그냥 "물"이라고 입력했을 때만 ml로 주려면 이렇게 예외처리!
    if name == "물":
        return "ml"
        
    # 2. 육류, 해산물, 가루류 (g)
    if any(k in name for k in ["소고기", "돼지고기", "닭고기", "삼겹살", "목살", "항정살", "한우", "오징어", "새우", "연어", "조개", "밀가루", "부침가루", "튀김가루", "설탕", "소금", "고춧가루", "버터", "깨", "마늘", "콩나물",]):
        return "g"
        
    # 3. 묶음 채소류 (단)
    if any(k in name for k in ["시금치", "부추", "미나리", "열무", "얼갈이"]):
        return "단"
        
    # 4. 파 종류 (대)
    if any(k in name for k in ["대파", "쪽파", "실파"]):
        return "대"
        
    # 5. 얇은 잎채소 및 가공품 (장)
    if any(k in name for k in ["깻잎", "상추", "라이스페이퍼", "치즈", "식빵", "김"]):
        return "장"
        
    # 6. 두부 및 묵류 (모)
    if any(k in name for k in ["두부", "묵"]):
        if "순두부" in name: 
            return "봉지"
        return "모"
        
    # 7. 배추류 (포기)
    if any(k in name for k in ["배추", "김치"]):
        return "포기"
        
    # 8. 통 생물 (마리)
    if any(k in name for k in ["생선", "고등어", "갈치", "꽁치", "통닭"]):
        return "마리"
        
    # 9. 면, 가공식품류 (봉지 / 팩)
    if any(k in name for k in ["라면", "소면", "당면", "파스타면", "어묵", "만두", "소시지", "순대"]):
        return "봉지"
    if any(k in name for k in ["버섯", "딸기", "방울토마토", "베이컨"]):
        return "팩"
        
    # 10. 그 외 일반적인 채소, 과일, 알류는 모두 '개'로 처리합니다.
    # (양파, 고추, 당근, 감자, 고구마, 사과, 계란, 달걀 등)
    return "개"

# ---------------------------------------------------------
# 💡 [팝업 함수 모음] 재료 이름 수정 및 수량 관리
# ---------------------------------------------------------
@st.dialog("✏️ 재료 이름 수정")
def edit_ingredient_name(item_id, current_name):
    new_name = st.text_input("새로운 이름을 입력하세요", value=current_name)
    
    if st.button("저장하기", use_container_width=True):
        if new_name.strip() == "":
            st.warning("이름을 비워둘 수 없습니다!")
            return
            
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 💡 드디어 찾은 진짜 이름 'custom_name'을 적어줍니다!!
                sql = "UPDATE user_pantry SET custom_name = %s WHERE id = %s" 
                cursor.execute(sql, (new_name, item_id))
            conn.commit()
            
            st.success("✨ 이름이 성공적으로 변경되었습니다!")
            time.sleep(1) 
            st.rerun()    
        except Exception as e:
            st.error(f"저장 중 에러가 발생했습니다: {e}")
        finally:
            if 'conn' in locals() and conn.open: conn.close()

@st.dialog("⚖️ 재료 정보 수정")
def edit_ingredient_amount(item_id, current_amount, unit, current_expiry):
    # 1. 수량 수정
    new_amount = st.number_input(f"수량 ({unit})", value=float(current_amount), min_value=0.0, step=1.0)
    
    # 2. 💡 [신규] 유통기한 수정 기능 추가!
    # 기존 날짜가 문자열일 수도 있으니 안전하게 변환해서 넣어줍니다.
    if isinstance(current_expiry, str):
        try: current_expiry = datetime.strptime(current_expiry, '%Y-%m-%d').date()
        except: current_expiry = datetime.now().date()
        
    new_expiry = st.date_input("⏳ 유통기한 변경", value=current_expiry)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 저장", use_container_width=True):
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # 💡 수량(quantity)과 기한(expires_at)을 동시에 업데이트!
                    sql = "UPDATE user_pantry SET quantity = %s, expires_at = %s WHERE id = %s"
                    cursor.execute(sql, (new_amount, new_expiry, item_id))
                conn.commit()
                st.rerun()
            except Exception as e:
                st.error(f"수정 실패: {e}")
            finally: conn.close()
            
    with col2:
        if st.button("🗑️ 삭제", type="primary", use_container_width=True):
            delete_fridge_item(item_id)
            st.rerun()


# 💡 [영수증 분석 AI] (현재는 UI 테스트 및 발표 시연을 위한 스마트 시뮬레이터입니다)
def extract_items_from_receipt(image_file):
    # 실제 배포 시에는 이 부분을 구글 Vision API나 네이버 OCR 호출 코드로 교체합니다.
    time.sleep(2.5) # AI가 이미지를 분석하는 듯한 리얼한 로딩 시간 (2.5초 대기) ⏳
    
    # 🛒 3가지 장보기 시나리오 중 하나를 랜덤으로 뽑아냅니다. (발표 시연용으로 최고!)
    scenarios = [
        ["삼겹살", "상추", "깻잎", "마늘", "쌈장"],
        ["우유", "계란", "식빵", "버터"],
        ["두부", "대파", "양파", "콩나물", "소고기"]
    ]
    extracted_items = random.choice(scenarios)
    
    return extracted_items


import re

def clean_recipe_title(raw_title):
    if not raw_title: return "제목 없음"
    
    # 1. 쓸데없는 괄호, 이모지, 기호 등 1차 청소
    text = re.sub(r'🔥.*', '', raw_title)
    text = re.sub(r'\[.*?\]|\(.*?\)|<.*?>', '', text)
    text = re.sub(r'[!?!|ㅣ✨❤️👍😍😋]', ' ', text)
    text = text.replace('~', ' ')
    
    # 2. 🛡️ 요리명 앞뒤를 더럽히는 '어그로 주범' 단어들 전역 삭제
    # (이렇게 하면 '만들기', '레시피' 같은 찌꺼기가 먼저 날아가서 본체만 깔끔하게 남습니다)
    noise_words = [
        '만들기', '황금레시피', '레시피', '초간단', '대박', '비법', '비밀', 
        '무조건', '절대', '꿀팁', '인생', '성공률', '이대로', '이렇게', 
        '하는법', '하는 법', '끓이는법', '끓이는 법', '만드는법', '만드는 법',
        '맛있게', '쉽게', '간단하게', '버전', '백종원의', '쿠킹로그', '초스피드', '집에서',
        '사먹지', '마세요', '가장 맛있는', '평생 써먹는', '끝판왕', '밥도둑', '백종원', 
    ]
    for word in noise_words:
        text = text.replace(word, ' ')
        
    # 다중 공백 하나로 압축
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 혜진님의 완벽한 요리 사전
    food_dictionary = [
        "제육덮밥", "오징어덮밥", "낙지덮밥", "쭈꾸미덮밥", "마파두부덮밥", "불고기덮밥", "소고기덮밥", "참치마요덮밥", "치킨마요덮밥", "스팸마요덮밥", "연어덮밥", "장어덮밥", "새우장덮밥", "가지덮밥", "마늘종덮밥", "카레", "짜장", "잡채밥", "유산슬밥", "게장비빔밥", "꼬막비빔밥", "육회비빔밥", "아보카도명란비빔밥", "돌솥비빔밥", "전주비빔밥", "간장계란밥", "김치볶음밥", "새우볶음밥", "계란볶음밥", "마늘볶음밥", "카레라이스", "하이라이스", "오므라이스", "김밥", "참치김밥", "치즈김밥", "유부초밥", "주먹밥", "김치전", "해물파전", "파전", "부추전", "감자전", "애호박전", "호박전", "동태전", "육전", "깻잎전", "고추전", "동그랑땡", "녹두전", "빈대떡", "배추전", "버섯전", "표고버섯전", "굴전", "새우전", "명태전", "부침개", "김치부침개", "오징어김치전", "오꼬노미야끼", "갈비찜", "소갈비찜", "돼지갈비찜", "매운갈비찜", "찜닭", "안동찜닭", "로제찜닭", "어묵", "오징어", "계란", "고구마", "짜글이", "스테이크", "닭볶음탕", "계란찜", "폭탄계란찜", "뚝배기계란찜", "아구찜", "아귀찜", "해물찜", "꽃게찜", "대게찜", "김치찜", "묵은지김치찜", "돼지고기김치찜", "등갈비찜", "묵은지등갈비찜", "차돌박이찜", "편백찜", "수육", "보쌈", "돼지고기수육", "소고기수육", "편육", "편육냉채", "김치찌개", "참치김치찌개", "돼지고기김치찌개", "된장찌개", "차돌된장찌개", "해물된장찌개", "청국장", "부대찌개", "순두부찌개", "고추장찌개", "동태찌개", "비지찌개", "미역국", "소고기미역국", "무국", "소고기무국", "콩나물국", "북엇국", "황태해장국", "시금치된장국", "육개장", "닭개장", "삼계탕", "백숙", "닭곰탕", "갈비탕", "설렁탕", "곰탕", "감자탕", "뼈해장국", "순대국", "돼지국밥", "마라탕", "어묵탕", "오뎅탕", "홍합탕", "잔치국수", "비빔국수", "열무국수", "칼국수", "바지락칼국수", "수제비", "들깨수제비", "라면", "짜파게티", "비빔면", "쫄면", "냉면", "물냉면", "비빔냉면", "막국수", "짜장면", "짬뽕", "우동", "볶음우동", "파스타", "토마토파스타", "크림파스타", "알리오올리오", "까르보나라", "투움바파스타", "제육볶음", "오징어볶음", "낙지볶음", "주꾸미볶음", "공심채볶음", "어묵볶음", "오뎅볶음", "감자볶음", "멸치볶음", "진미채볶음", "버섯볶음", "마늘종볶음", "소시지야채볶음", "쏘야", "두루치기", "대패두루치기", "돼지불고기", "소불고기", "닭갈비", "탕수육", "깐풍기", "돈까스", "치킨", "삼겹살", "목살구이", "생선구이", "고등어구이", "갈치구이", "두부조림", "감자조림", "우엉조림", "연근조림", "장조림", "소고기장조림", "메추리알장조림", "꽁치조림", "고등어조림", "무생채", "콩나물무침", "시금치무침", "가지무침", "오이무침", "도라지무침", "파무침", "파절이", "골뱅이무침", "도토리묵무침", "장아찌", "양파장아찌", "마늘장아찌", "계란말이", "배추김치", "깍두기", "파김치", "겉절이", "샌드위치", "토스트", "햄버거", "피자", "핫도그", "샐러드", "고구마라떼", "녹차라떼", "카페라떼", "밀크티", "아메리카노", "에이드", "스무디", "요거트", "빙수", "팬케이크", "크로플", "브레드", "소시지", "소세지", "콘치즈", "국수", "시금치", "만두", "만둣국", "전복", "죽", "닭", "샐러드", "파스타", "도라지", "김치", "청국장"
    ]
    food_dictionary.sort(key=len, reverse=True)


    
    # 3. 💡 [핵심] '여지'를 주는 유연한 추출 로직!
    for food in food_dictionary:
        if food in text:
            # 정규식 마법: 요리 이름(food)을 기준으로, 그 '앞에 있는 최대 2개의 단어'까지 한 덩어리로 묶어냅니다!
            # 예: "대박 맛있는 파송송 계란탁 라면 끓이기" -> 그룹1:"파송송 계란탁 ", 그룹2:"라면"
            pattern = r'((?:[^\s]+\s+){0,2})(\S*' + food + r'\S*)'
            match = re.search(pattern, text)
            
            if match:
                prefix_words = match.group(1) # 앞쪽 1~2개 수식어 (우리가 원했던 여지!)
                food_block = match.group(2)   # 요리 본체 (예: 사먹는갈비탕을)
                
                # 끝에 붙은 불필요한 조사('을', '를' 등)만 정교하게 잘라냅니다.
                cleaned_food_block = re.sub(r'(은|는|이|가|을|를|의|에|에서|로|으로|와|과|도|만|까지|부터|랑|,|이랑)$', '', food_block)
                
                # 만약 조사를 잘라냈는데 요리명(라면)이 깨졌다면 원상복구
                if food not in cleaned_food_block:
                    cleaned_food_block = food_block
                    
                # 앞쪽 수식어와 요리 본체를 예쁘게 합쳐서 반환!
                extracted = (prefix_words + cleaned_food_block).strip()
                return extracted
                
    # 4. 사전에 없는 완전 새로운 요리일 경우 (플랜 B)
    words = text.split()
    clean_words = []
    for w in words:
        if re.search(r'(시면|입니다|할|드릴게요|됩니다|포기한|훔친|보세요|먹자|먹는|끓여|끓인|만드는)$', w):
            continue
        clean_words.append(w)
        
    cleaned_text = " ".join(clean_words).strip()
    return cleaned_text if cleaned_text else raw_title.strip()


@st.dialog("🍴 레시피 상세 보기")
def show_recipe_detail(recipe_id, recipe_title, recipe_desc, difficulty):
    user_id = st.session_state.user_id
    is_fav = check_favorite(user_id, recipe_id)
    
    c_title, c_heart = st.columns([8, 2])
    with c_title:
        st.markdown(f"## {recipe_title}")
        
    with c_heart:
        st.write("") 
        # 💡 [수정] 찜 여부에 따라 하트가 바뀌도록 다시 적용했습니다!
        heart_icon = "❤️" if is_fav else "🤍"
        if st.button(heart_icon, key=f"fav_btn_{recipe_id}", help="즐겨찾기", use_container_width=True):
            toggle_favorite(user_id, recipe_id, is_fav)
            st.rerun() 
            
    diff_text = difficulty if difficulty else "보통"
    st.markdown(f"<span style='background-color:#FEE2E2; color:#B91C1C; padding:4px 10px; border-radius:12px; font-weight:bold; font-size:14px;'>🔥 난이도 : {diff_text}</span>", unsafe_allow_html=True)
    
    if recipe_desc:
        st.write(recipe_desc)
        
    st.write("---")
    st.subheader("🛒 필요 재료")
    
    # 👇 [추가된 부분] 팝업을 열 때, 내 냉장고에서 '유통기한 3일 이하' 남은 임박 재료 이름만 쏙 뽑아옵니다!
    urgent_names = []
    try:
        fridge_items = get_fridge_items(st.session_state.user_id)
        today = datetime.now().date()
        for item in fridge_items:
            exp = item.get('expiry_date')
            if exp:
                if isinstance(exp, str):
                    try: exp = datetime.strptime(exp, '%Y-%m-%d').date()
                    except: continue
                elif hasattr(exp, 'date'):
                    exp = exp.date()
                    
                if (exp - today).days <= 3: # D-3 이내인 재료들만 이름 수집
                    urgent_names.append(item['item_name'].replace(" ", ""))
    except Exception as e:
        print(f"임박재료 확인 에러: {e}")
    # 👆 [추가 끝]

    ingredients = get_recipe_ingredients(recipe_id)
    if ingredients:
        for ing in ingredients:
            ing_name = ing['name'].strip()
            a_val = str(ing['amount']).strip() if ing['amount'] else ""
            u_val = str(ing['unit_name']).strip() if ing.get('unit_name') else ""
            
            # 💡 [스마트 필터 0단계] '인분 양 3' 같은 데이터를 예쁜 뱃지로 바꿔줍니다!
            if "인분" in ing_name.replace(" ", ""):
                portion_num = a_val if a_val else "".join(filter(str.isdigit, ing_name))
                if not portion_num: portion_num = "1"
                st.markdown(f"<div style='margin-bottom: 12px; display: inline-block; background-color: #F1F5F9; color: #475569; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 700;'>👨‍👩‍👧‍👦 {portion_num}인분 기준</div>", unsafe_allow_html=True)
                continue 
         
            # 💡 [스마트 필터 1단계] 이름에 잘못 붙어버린 단위 분리
            words = ing_name.split() 
            if len(words) > 1:
                last_word = words[-1]
                common_units = ["모", "단", "줌", "마리", "포기", "스푼", "큰술", "컵", "봉지"]
                if last_word in common_units:
                    ing_name = " ".join(words[:-1]) 
                    if not u_val: u_val = last_word 
                elif last_word == "반":
                    ing_name = " ".join(words[:-1])
                    a_val = "반 " + a_val if a_val else "반"

            # 💡 [스마트 필터 2단계] 단위가 비어있으면 식재료에 맞춰 눈치껏 채워줌!
            if a_val and not u_val:
                if any(k in ing_name for k in ["양파", "당근", "고추", "피망", "파프리카", "감자", "고구마", "계란", "달걀", "사과", "토마토"]):
                    u_val = "개" 
                elif any(k in ing_name for k in ["대파", "쪽파"]):
                    u_val = "대" 
                elif any(k in ing_name for k in ["두부"]):
                    u_val = "모" 
                elif any(k in ing_name for k in ["소금", "설탕", "간장", "참기름", "들기름", "고춧가루", "된장", "고추장", "쌈장", "식초", "물엿", "올리고당", "맛술", "미림", "다진마늘",  "액젓", "굴소스", "마요네즈", "케첩", "기름", "식용유", "올리브유", "버터"]):
                    u_val = "큰술" 
            
            has_amount = bool(a_val or u_val)
            amount_str = f"{a_val}{u_val}".strip() if has_amount else "적당량"
            
            is_middle_category = False
            if any(k in ing_name for k in ["양념", "육수", "소스", "드레싱", "국물", "재료"]):
                is_middle_category = True
            elif ing_name.replace(" ", "") in recipe_title.replace(" ", ""):
                if not has_amount:
                    is_middle_category = True
                        
            if is_middle_category:
                st.markdown(f"<div style='margin-top: 15px; margin-bottom: 5px; font-weight: 700; color: #0F172A; font-size: 16px;'>📁 {ing_name}</div>", unsafe_allow_html=True)
            else:
                # 👇 [핵심 추가] 이 재료가 방금 뽑아둔 '임박 재료' 리스트에 있는지 확인합니다.
                is_urgent = False
                clean_ing = ing_name.replace(" ", "")
                for u_name in urgent_names:
                    # '양파'가 '다진양파'에 포함되거나, 반대로 '다진양파'가 '양파'에 포함되는지 유연하게 검사!
                    if u_name in clean_ing or clean_ing in u_name:
                        is_urgent = True
                        break
                        
                # 💡 임박 재료라면 이름 옆에 예쁜 빨간 뱃지를 달아줍니다!
                if is_urgent:
                    st.markdown(f"<div style='margin-left: 15px; margin-bottom: 4px; color: #334155; font-size: 15px;'>• {ing_name} <span style='color: #475569; font-weight: 600;'>{amount_str}</span> <span style='color:#EF4444; font-size:12px; font-weight:bold; background-color:#FEE2E2; border: 1px solid #F87171; padding:2px 6px; border-radius:8px; margin-left: 8px;'>🚨빨리 써야 해요!</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='margin-left: 15px; margin-bottom: 4px; color: #334155; font-size: 15px;'>• {ing_name} <span style='color: #475569; font-weight: 600;'>{amount_str}</span></div>", unsafe_allow_html=True)
    else:
        st.info("상세 재료 정보가 DB에 없습니다.")

        
    # 👇👇👇 여기서부터 팝업창 맨 아래에 들어갈 [요리 완료] 버튼 기능입니다! 👇👇👇
    st.write("---")
    
    # 💡 시선을 사로잡는 안내 문구와 눈에 띄는 Primary 색상 버튼!
    st.markdown("<div style='text-align: center; margin-bottom: 10px; color: #64748B; font-size: 14px;'>요리를 완성하셨나요? 버튼을 눌러 사용한 재료를 냉장고에서 비워주세요!</div>", unsafe_allow_html=True)
    
    if st.button("✨ 요리 완성! 내 냉장고에서 재료 빼기", use_container_width=True, type="primary"):
        with st.spinner("냉장고 재고를 정리하고 있습니다... 🧹"):
            time.sleep(1) # 부드러운 애니메이션 효과를 위해 1초 대기
            deducted = cook_and_deduct_ingredients(user_id, recipe_id)
            
            if deducted:
                # 차감된 재료 목록을 예쁘게 보여줍니다.
                success_msg = "🎉 **요리 완성 축하드려요!**<br>냉장고에서 다음 재료들을 자동으로 차감했습니다:<br><br>"
                for msg in deducted:
                    success_msg += f"• {msg}<br>"
                st.success(success_msg, icon="✅")
            else:
                st.info("차감할 주요 재료가 냉장고에 없거나, 모두 상비 조미료입니다. 그래도 맛있게 드세요! 😋")
                
    # 약간의 여백
    st.write(" ") 
    
    # 💡 [핵심] key=f"close_{recipe_id}" 라는 고유한 이름표를 달아줍니다!
    if st.button("닫기", key=f"close_{recipe_id}", use_container_width=True):
        st.rerun()
    
    st.subheader("👨‍🍳 조리 순서")
    steps = get_recipe_steps(recipe_id)
    if steps:
        for step in steps:
            st.markdown(f"**Step {step['step_no']}.** {step['content']}")
    else:
        st.info("조리 순서 정보가 DB에 없습니다.")
            
    if st.button("닫기", use_container_width=True):
        st.rerun()


# 💡 현재 로그인한 사용자의 즐겨찾기 레시피 목록을 최신순으로 가져오는 함수
def get_favorite_recipes(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # favorites 테이블과 recipes 테이블을 조인(JOIN)해서 필요한 정보만 쏙쏙 뽑아옵니다!
            sql = """
                SELECT r.id, r.title, r.description, c.name as cat_name, r.difficulty 
                FROM favorites f
                JOIN recipes r ON f.recipe_id = r.id
                LEFT JOIN recipe_categories c ON r.category_id = c.id
                WHERE f.user_id = %s
                ORDER BY f.created_at DESC
            """
            cursor.execute(sql, (user_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"즐겨찾기 목록 로드 에러: {e}")
        return []
    finally:
        if 'conn' in locals() and conn.open: conn.close()
            

# 💡 1. 레시피의 필요 재료를 가져오는 함수 (컬럼명 display_name 으로 수정 완료!)
def get_recipe_ingredients(recipe_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # u.name을 u.display_name으로 정확히 수정했습니다.
            sql = """
                SELECT ri.name, ri.amount, u.display_name AS unit_name 
                FROM recipe_ingredients ri
                LEFT JOIN units u ON ri.unit_id = u.id
                WHERE ri.recipe_id = %s 
                ORDER BY ri.sort_order ASC
            """
            cursor.execute(sql, (recipe_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"재료 로드 에러: {e}")
        return []
    finally:
        if 'conn' in locals(): conn.close()

# 💡 2. 레시피의 조리 순서를 가져오는 함수 (그대로 유지)
def get_recipe_steps(recipe_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "SELECT step_no, content FROM recipe_steps WHERE recipe_id = %s ORDER BY step_no ASC"
            cursor.execute(sql, (recipe_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"조리 순서 로드 에러: {e}")
        return []
    finally:
        if 'conn' in locals(): conn.close()

# 💡 즐겨찾기 여부를 확인하는 함수
def check_favorite(user_id, recipe_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM favorites WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"즐겨찾기 확인 에러: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.open: conn.close()

# 💡 즐겨찾기를 추가하거나 삭제(토글)하는 함수
def toggle_favorite(user_id, recipe_id, current_status):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if current_status:
                # 이미 찜했으면 삭제 (해제)
                cursor.execute("DELETE FROM favorites WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
            else:
                # 찜 안했으면 추가
                cursor.execute("INSERT INTO favorites (user_id, recipe_id) VALUES (%s, %s)", (user_id, recipe_id))
        conn.commit()
    except Exception as e:
        print(f"즐겨찾기 토글 에러: {e}")
    finally:
        if 'conn' in locals() and conn.open: conn.close()
def get_recipes(search_query=None, category=None):
    CATEGORIES = ['국/탕', '찌개/전골', '볶음', '구이', '튀김', '무침/나물', '찜', '면/파스타', '밥/덮밥', '전/부침', '간식/디저트', '기타']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 💡 [핵심] 'r.id,' 를 추가하여 레시피 번호를 정상적으로 가져옵니다!
            sql = "SELECT r.id, r.title, r.description, c.name as cat_name FROM recipes r LEFT JOIN recipe_categories c ON r.category_id = c.id WHERE 1=1"
            params = []
            if search_query:
                # 제목뿐만 아니라 설명에서도 검색되도록 업그레이드했습니다
                sql += " AND (r.title LIKE %s OR r.description LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])
            if category and category in CATEGORIES:
                sql += " AND c.name = %s"
                params.append(category)
            sql += " LIMIT 20"
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally: conn.close()

# 💡 [예산 검색용] DB의 'estimated_cost' 컬럼을 활용해 예산 내의 레시피만 초고속으로 가져옵니다!
# 💡 [예산 검색용] 매번 새로운 레시피가 나오도록 RAND()를 적용했습니다!
def get_recipes_by_budget(max_budget):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 💡 ORDER BY RAND() 로 변경하고, 화면에 예쁘게 맞게 4개만 가져옵니다.
            sql = """
                SELECT r.id, r.title, r.description, c.name as cat_name, r.difficulty, r.estimated_cost
                FROM recipes r 
                LEFT JOIN recipe_categories c ON r.category_id = c.id 
                WHERE r.estimated_cost IS NOT NULL AND r.estimated_cost <= %s
                ORDER BY RAND()
                LIMIT 4
            """
            cursor.execute(sql, (max_budget,))
            return cursor.fetchall()
    except Exception as e:
        print(f"예산 레시피 로드 에러: {e}")
        return []
    finally:
        if 'conn' in locals() and conn.open: conn.close()

def get_db_ingredients():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, shelf_life_days FROM ingredients")
            return cursor.fetchall()
    except: return []
    finally:
        if 'conn' in locals(): conn.close()

def get_monthly_spending(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # date -> spent_at 으로 수정
            sql = "SELECT SUM(amount) as total FROM user_expenses WHERE user_id = %s AND DATE_FORMAT(spent_at, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')"
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            # 소수점(Decimal) 에러 방지를 위해 int()로 묶어줍니다.
            return int(result['total']) if result['total'] else 0
    except: return 0
    finally: conn.close()

# 💡 1. 냉장고 데이터 가져오기 (user_pantry 테이블 사용)
def get_fridge_items(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 💡 is_finished = 0 인 것(아직 다 안 먹고 냉장고에 있는 것)만 가져옵니다!
            # 기존 UI 코드가 깨지지 않도록 custom_name을 item_name으로 둔갑시켜 가져옵니다.
            sql = """
                SELECT id, custom_name AS item_name, expires_at AS expiry_date, quantity AS amount, unit 
                FROM user_pantry 
                WHERE user_id = %s AND is_finished = 0 
                ORDER BY expires_at ASC
            """
            cursor.execute(sql, (user_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"냉장고 로드 에러: {e}")
        return []
    finally:
        if 'conn' in locals() and conn.open: conn.close()

# 💡 2. 재료 새로 추가하기
# 💡 [업그레이드] 재료를 추가할 때 단위가 없으면 스마트 추론기를 돌려서 채워 넣습니다!
def add_fridge_item(user_id, item_name, expiry_date, amount=1, unit=None):
    try:
        # 사용자가 단위를 입력하지 않았다면, 이름표를 보고 자동으로 단위를 맞춥니다.
        if not unit or unit == '개':
            unit = guess_item_unit(item_name)
            
        # g이나 ml 단위인 경우, 수량(amount)이 1로 들어오면 이상하므로 기본값을 100으로 세팅해줍니다.
        if unit in ["g", "ml"] and amount == 1:
            amount = 100
            
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO user_pantry (user_id, custom_name, expires_at, quantity, unit, is_finished) 
                VALUES (%s, %s, %s, %s, %s, 0)
            """
            cursor.execute(sql, (user_id, item_name, expiry_date, amount, unit))
        conn.commit()
    except Exception as e:
        print(f"냉장고 추가 에러: {e}")
    finally:
        if 'conn' in locals() and conn.open: conn.close()

# 💡 [핵심 알고리즘] 레시피 재료와 냉장고 재료를 비교해서 알아서 빼주는 함수!
def cook_and_deduct_ingredients(user_id, recipe_id):
    ingredients = get_recipe_ingredients(recipe_id)
    fridge_items = get_fridge_items(user_id) # 현재 냉장고에 있는 재료들
    
    deducted_log = [] 
    
    # 💡 [버그 수정] "콩나물"에 "물"이 들어간다고 조미료로 오해하는 사태를 막기 위해 필터를 분리했습니다!
    ignore_exact = ["물", "깨", "소금", "설탕", "후추", "간장", "된장", "고추장", "식초", "버터"]
    ignore_partial = ["기름", "소스", "육수", "액젓", "미림", "맛술", "물엿", "고춧가루", "다진마늘", "양념", "국물", "시럽"]
    
    for req_ing in ingredients:
        req_name = req_ing['name'].replace(" ", "")
        
        # 1. 똑같은 글자일 때만 무시 (예: 진짜 마시는 "물"일 때만)
        if req_name in ignore_exact:
            continue
        # 2. 단어가 포함되어 있을 때 무시 (예: "고춧가루" 통째로 체크)
        if any(ig in req_name for ig in ignore_partial):
            continue
            
        for f_item in fridge_items:
            f_name = f_item['item_name'].replace(" ", "")
            
            if req_name in f_name or f_name in req_name:
                req_amt = req_ing['amount']
                try: deduct_amt = float(req_amt) if req_amt else 1.0
                except: deduct_amt = 1.0 
                    
                # 💡 [방어 로직 추가] DB에 수량이 빈칸(NULL)일 경우를 대비해 안전하게 1.0으로 처리!
                raw_amt = f_item.get('amount')
                current_amt = float(raw_amt) if raw_amt is not None else 1.0
                
                new_amt = current_amt - deduct_amt
                
                update_fridge_item_amount(f_item['id'], new_amt)
                
                display_deduct = int(deduct_amt) if deduct_amt % 1 == 0 else round(deduct_amt, 1)
                unit = f_item.get('unit')
                unit_str = unit if unit else '개'
                deducted_log.append(f"{f_item['item_name']} (-{display_deduct}{unit_str})")
                
                break 
                
    return deducted_log

# 💡 3. [신규] 수량 변경 및 소진 처리 (+/- 버튼용)
def update_fridge_item_amount(item_id, new_amount):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if new_amount <= 0:
                # 💡 핵심: 진짜로 지우지 않고, 수량을 0으로 만들고 다 먹었다(is_finished=1)고 표시합니다! (기록 보존)
                cursor.execute("UPDATE user_pantry SET quantity = 0, is_finished = 1 WHERE id = %s", (item_id,))
            else:
                cursor.execute("UPDATE user_pantry SET quantity = %s WHERE id = %s", (new_amount, item_id))
        conn.commit()
    except Exception as e:
        print(f"수량 업데이트 에러: {e}")
    finally:
        if 'conn' in locals() and conn.open: conn.close()

# 💡 4. 재료 삭제 (기존 삭제 버튼도 Soft Delete로 변경)
def delete_fridge_item(item_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE user_pantry SET is_finished = 1 WHERE id = %s", (item_id,))
        conn.commit()
    except Exception as e:
        print(f"재료 삭제 에러: {e}")
    finally:
        if 'conn' in locals() and conn.open: conn.close()

# --- 3. 세션 상태 초기화 ---
if 'page' not in st.session_state: st.session_state.page = '대시보드'
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'temp_matched_items' not in st.session_state: st.session_state.temp_matched_items = []
if 'total_spend' not in st.session_state: st.session_state.total_spend = 0
if 'spend_data' not in st.session_state: st.session_state.spend_data = pd.DataFrame(columns=['날짜', '금액'])
if 'last_search' not in st.session_state: st.session_state.last_search = ""
if 'recipe_page' not in st.session_state: st.session_state.recipe_page = 1
# 💡 에러 방지를 위해 변수들을 미리 '0'으로 만들어둡니다. (NameError 해결!)
monthly_total = 0
total_inventory = 0
imminent_count = 0

# --- 4. 타이틀 및 로그인 화면 ---
st.markdown('<h1 class="main-title">SMART KITCHEN</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">PREMIUM REFRIGERATOR MANAGEMENT</p>', unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])
    
    with tab_login:
        login_email = st.text_input("이메일", key="login_email")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", use_container_width=True):
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM users WHERE email = %s AND password_hash = %s", (login_email, login_pw))
                user = cursor.fetchone()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user['id']
                    st.session_state.user_name = user['name']
                    st.success(f"반가워요, {user['name']}님!")
                    st.rerun()
                else: st.error("이메일 또는 비밀번호가 틀렸어요.")
            conn.close()

    with tab_signup:
        new_email = st.text_input("사용할 이메일", key="new_email")
        new_pw = st.text_input("사용할 비밀번호", type="password", key="new_pw")
        new_name = st.text_input("이름 (닉네임)", key="new_name")
        if st.button("가입하기", use_container_width=True):
            if new_email and new_pw and new_name:
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        cursor.execute("INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s)", (new_email, new_pw, new_name))
                    conn.commit()
                    st.success("가입 완료! '로그인' 탭에서 로그인해주세요.")
                except Exception as e: st.error(f"오류: {e}")
                finally: conn.close()
            else: st.warning("모든 항목을 입력해주세요.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. 메뉴바 (짧은 이름으로 변경하여 한 줄 유지) ---
m_list = [f"{EMO_DASH} 홈", f"{EMO_RECIPE} 레시피", f"{EMO_FRIDGE} 냉장고", f"{EMO_CASH} 식비", f"{EMO_HEART} 찜"]
m_list = ["📊 홈", "🍴 레시피", "🫙 냉장고", "📈 식비", "❤️ 찜"] 
nav = st.columns(5)
for i, m in enumerate(m_list):
    if nav[i].button(m, use_container_width=True):
        # 이동할 때 글자 처리는 그대로 유지
        page_name = "대시보드" if "홈" in m else m.split(" ")[1]
        st.session_state.page = page_name
st.write("---")

import uuid # 코드 맨 위에 이 줄이 있는지 확인해 주세요! (없으면 추가)

@st.dialog("➕ 냉장고 재료 추가")
def add_ingredient_popup():
    t_ocr, t_man = st.tabs(["📷 영수증 사진 등록", "⌨️ 직접 입력"])
    
    # --- [탭 1: 영수증 분석] ---
    with t_ocr:
        uploaded_file = st.file_uploader("영수증 사진", type=["jpg", "jpeg", "png"], key="pop_ocr_up")
        if uploaded_file and st.button("🚀 분석 시작", key="pop_ocr_run"):
            st.session_state.temp_matched_items = []
            with st.spinner('영수증을 분석 중입니다...'):
                try:
                    headers = {'X-OCR-SECRET': SECRET_KEY}
                    file_bytes = uploaded_file.getvalue()
                    file_ext = uploaded_file.name.split('.')[-1]
                    payload = {'message': json.dumps({'images': [{'format': file_ext, 'name': 'receipt'}], 'requestId': str(uuid.uuid4()), 'version': 'V2', 'timestamp': int(time.time() * 1000)})}
                    response = requests.post(INVOKE_URL, headers=headers, data=payload, files=[('file', file_bytes)])
                    if response.status_code == 200:
                        json_data = response.json()
                        items = json_data.get('images', [{}])[0].get('receipt', {}).get('result', {}).get('subResults', [{}])[0].get('items', [])
                        found_list = []
                        for it in items:
                            name_val = it.get('name', {}).get('text', '알 수 없는 재료')
                            price_val = it.get('price', {}).get('price', {}).get('formatted', {}).get('value', '0')
                            found_list.append({'id': str(uuid.uuid4()), 'name': name_val, 'expiry': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'), 'price': int(str(price_val).replace(',','').replace('.','')), 'amount': 1.0})
                        st.session_state.temp_matched_items = found_list
                except: st.error("분석 중 오류가 발생했습니다.")

    # --- [탭 2: 직접 입력] ---
    # 팝업 함수 내부의 직접 입력 탭 부분
    with t_man:
        # --- 💡 [내부 보조 함수] DB에서 재료별 보관 기간 가져오기 ---
        def get_calculated_expiry(item_name):
            days = 7  # DB에 정보가 없을 경우 사용할 기본값
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # ingredients 테이블에서 해당 재료의 권장 보관일을 찾습니다.
                    sql = "SELECT shelf_life_days FROM ingredients WHERE name = %s"
                    cursor.execute(sql, (item_name,))
                    result = cursor.fetchone()
                    if result and result['shelf_life_days']:
                        days = int(result['shelf_life_days'])
            except: 
                pass
            finally: 
                if 'conn' in locals() and conn.open: conn.close()
            
            # 오늘 날짜 + 권장 기간 = 자동 유통기한 반환
            return datetime.now().date() + timedelta(days=days)

        # 1. 자주 넣는 재료 TOP 5 (DB 분석)
        frequent_items = []
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = "SELECT custom_name, COUNT(*) as cnt FROM user_pantry WHERE user_id = %s GROUP BY custom_name ORDER BY cnt DESC LIMIT 5"
                cursor.execute(sql, (st.session_state.user_id,))
                rows = cursor.fetchall()
                frequent_items = [row['custom_name'] for row in rows]
        except: pass
        finally: 
            if 'conn' in locals() and conn.open: conn.close()

        if not frequent_items: frequent_items = ["양파", "달걀", "우유", "대파", "마늘"]

        st.write(f"✨ **{st.session_state.user_name}님이 자주 넣는 재료** (즉시 저장)")
        q_cols = st.columns(5)
        for i, name in enumerate(frequent_items):
            if q_cols[i].button(name, key=f"freq_direct_{i}", use_container_width=True):
                # 💡 [업그레이드] DB 데이터 기반 날짜 계산 후 저장
                auto_expiry = get_calculated_expiry(name)
                add_fridge_item(st.session_state.user_id, name, auto_expiry, amount=1.0)
                st.success(f"'{name}' 등록 완료! (권장기한 반영: {auto_expiry})")
                time.sleep(0.5)
                st.rerun()

        # 2. 카테고리별 아이콘 선택
        categories = {
            "🥩 육류/알류": ["소고기", "돼지고기", "닭고기", "계란", "소시지", "베이컨", "오리고기", "햄"],
            "🥬 필수 채소": ["양파", "대파", "마늘", "고추", "생강", "감자", "고구마", "당근"],
            "🥗 잎/콩나물": ["상추", "깻잎", "양배추", "시금치", "부추", "청경채", "콩나물", "팽이버섯"],
            "🍎 과일/기타": ["사과", "바나나", "애호박", "오이", "가지", "토마토", "무", "두부"],
            "🥛 유제품/냉동": ["우유", "치즈", "요거트", "버터", "식빵", "어묵", "만두", "물"]
        }

        st.write("✨ **종류별로 골라보세요 (즉시 저장)**")
        for cat_name, items in categories.items():
            with st.expander(cat_name):
                for i in range(0, len(items), 4):
                    cols = st.columns(4)
                    for j in range(4):
                        if i + j < len(items):
                            item_name = items[i + j]
                            if cols[j].button(item_name, key=f"cat_direct_{cat_name}_{item_name}", use_container_width=True):
                                # 💡 [업그레이드] 아이콘 클릭 시에도 DB 데이터 기반 날짜 계산
                                auto_expiry = get_calculated_expiry(item_name)
                                add_fridge_item(st.session_state.user_id, item_name, auto_expiry, amount=1.0)
                                st.success(f"'{item_name}' 추가 완료! (기한: {auto_expiry})")
                                time.sleep(0.5)
                                st.rerun()

        st.write("---")
        st.write("⌨️ **상세 정보 입력하여 추가**")


       
# --- 6. 페이지 구현 ---

if st.session_state.page == '대시보드':
    # 💡 [순서 교정 1] 화면에 그리기 전에 "데이터 계산"부터 무조건 먼저 합니다!
    monthly_total = 0
    total_inventory = 0
    imminent_count = 0
    all_pantry_items = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1-1. 이번 달 지출 총액 계산
            current_month = datetime.now().strftime('%Y-%m')
            cursor.execute("""
                SELECT SUM(amount) as total FROM user_expenses 
                WHERE user_id = %s AND DATE_FORMAT(spent_at, '%%Y-%%m') = %s
            """, (st.session_state.user_id, current_month))
            row = cursor.fetchone()
            monthly_total = int(row['total']) if row and row['total'] else 0
            
            # 1-2. 남은 재료 & 임박 재료 계산
            cursor.execute("""
                SELECT expires_at FROM user_pantry 
                WHERE user_id = %s AND is_finished = 0
            """, (st.session_state.user_id,))
            pantry_items = cursor.fetchall()
            
            total_inventory = len(pantry_items)
            today = datetime.now().date()
            for item in pantry_items:
                exp = item.get('expires_at')
                if exp:
                    if isinstance(exp, str):
                        try: exp = datetime.strptime(exp, '%Y-%m-%d').date()
                        except: continue
                    if (exp - today).days <= 3:
                        imminent_count += 1
            
            # 1-3. 냉장고 아이템 정보도 미리 가져오기
            all_pantry_items = get_fridge_items(st.session_state.user_id)

    except Exception as e:
        st.error(f"대시보드 데이터 로드 중 오류 발생: {e}")
    finally:
        if 'conn' in locals() and conn.open: conn.close()

    # 💡 [순서 교정 2] 이제 데이터가 준비됐으니 "화면 출력"을 시작합니다.
    emoji_money = "\U0001F4B8"
    emoji_vege = "\U0001F966"
    emoji_alert = "\U0001F6A8"

    st.write(f"### {st.session_state.user_name}님 👋")
    st.write("오늘은 어떤 요리를 만들어 볼까요?")
    
    # 📱 가로 3열 배치 강제 적용
    cols = st.columns(3)
    
    with cols[0]:
        st.markdown(f"""
            <div class="dash-card">
                <h4>지출 {emoji_money}</h4>
                <h2 style='color: #0F172A; font-weight: 800; margin: 0;'>{monthly_total:,}</h2>
            </div>
        """, unsafe_allow_html=True)
            
    with cols[1]:
        st.markdown(f"""
            <div class="dash-card">
                <h4>재료 {emoji_vege}</h4>
                <h2 style='color: #0F172A; font-weight: 800; margin: 0;'>{total_inventory}</h2>
            </div>
        """, unsafe_allow_html=True)
            
    with cols[2]:
        st.markdown(f"""
            <div class="dash-card">
                <h4>임박 {emoji_alert}</h4>
                <h2 style='color: #EF4444; font-weight: 800; margin: 0;'>{imminent_count}</h2>
            </div>
        """, unsafe_allow_html=True)

    st.write("---")

    # --- 🎯 빠른 레시피 검색 섹션 ---
    st.subheader("🎯 빠른 레시피 검색")
    d_c1, d_c2, d_c3 = st.columns([2, 4, 1])
    
    with d_c1:
        dash_cat_list = ["전체", "국/탕", "찌개/전골", "볶음", "구이", "튀김", "무침/나물", "찜", "면/파스타", "밥/덮밥", "전/부침", "간식/디저트", "기타"]
        d_sel = st.selectbox("카테고리", dash_cat_list, key="dash_sel")
        
    with d_c2:
        d_kw = st.text_input("검색어", placeholder="재료나 요리명...", key="dash_kw")
        
    with d_c3:
        st.write(" ") ; st.write(" ") 
        d_btn = st.button("🔍 검색", key="dash_btn", use_container_width=True)

    if d_btn or d_kw:
        res = get_recipes(d_kw, d_sel if d_sel != '전체' else None)
        if res:
            for idx, r in enumerate(res):
                title = clean_recipe_title(r.get('title') or "제목 없음")
                recipe_id = r.get('id') 
                if st.button(f"🍴 {title}", key=f"dash_res_{recipe_id}_{idx}", use_container_width=True):
                    show_recipe_detail(recipe_id, title, r.get('description',''), "보통")
        else:
            st.info("조건에 맞는 레시피가 없습니다.")

    st.write("---")

    # --- 💰 예산 맞춤 추천 ---
    st.subheader("💰 예산 맞춤 가성비 레시피")
    user_budget = st.slider("한 끼 예산 설정 (원)", 1000, 30000, 10000, 1000)
    if st.button("🔄 다른 레시피 찾기", type="primary", use_container_width=True):
        st.session_state.budget_recipes = get_recipes_by_budget(user_budget)
        st.session_state.budget_amount = user_budget

    if 'budget_recipes' in st.session_state and st.session_state.budget_recipes:
        b_cols = st.columns(2)
        for idx, rec in enumerate(st.session_state.budget_recipes):
            with b_cols[idx % 2]:
                with st.container(border=True):
                    title = clean_recipe_title(rec.get('title',''))
                    st.markdown(f"**{title}**")
                    st.markdown(f"<span style='color:#10B981;'>{int(rec.get('estimated_cost', 0)):,}원</span>", unsafe_allow_html=True)
                    if st.button("보기", key=f"bud_btn_{rec['id']}_{idx}"):
                        show_recipe_detail(rec['id'], title, rec.get('description',''), rec.get('difficulty'))

    st.write("---")
    l_sec, r_sec = st.columns([1.5, 1])
    with l_sec:
        st.subheader("재료 관리👜")
        if st.button("➕ 새 재료 추가 (영수증/직접)", use_container_width=True):
            add_ingredient_popup()
	
    with r_sec:
        st.subheader("⚠️ 빨리 사용하세요!")
        if all_pantry_items:
            # 유통기한 순 정렬 후 상위 4개만
            sorted_items = sorted(all_pantry_items, key=lambda x: x.get('expiry_date') or datetime.max.date())[:4]
            for item in sorted_items:
                st.markdown(f'<div class="fridge-item status-red">{item["item_name"]}</div>', unsafe_allow_html=True)


elif st.session_state.page == '레시피':
    # 1. 변수 설정
    icon_fork = "\U0001F374"
    icon_search = "\U0001F50D"
    icon_alert = "\U0001F6A8"

    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-top: -10px; margin-bottom: 15px;">
            <span style="font-size: 28px; margin-right: 10px;">{icon_fork}</span>
            <h2 style="font-family: 'Inter', sans-serif; font-weight: 700; font-size: 28px; color: #000000; margin: 0;">맞춤 레시피 추천</h2>
        </div>
    """, unsafe_allow_html=True)

    search_query = st.text_input(f"{icon_search} 찾으시는 요리나 재료가 있나요?", placeholder="예: 김치찌개, 양파...")

    # 2. 내 냉장고 데이터 분석 (여기서 모든 계산을 끝냅니다)
    pantry_items = get_fridge_items(st.session_state.user_id)
    today = datetime.now().date()

    def get_exp_days(x):
        val = x.get('expiry_date')
        if not val: return 999
        if hasattr(val, 'date'): d = val.date()
        else: d = datetime.strptime(str(val), '%Y-%m-%d').date()
        return (d - today).days

    # 유통기한 지난 거 빼고 정렬
    valid_pantry_items = [item for item in pantry_items if item.get('expiry_date') and get_exp_days(item) >= 0]
    all_exp_items = sorted(valid_pantry_items, key=get_exp_days)

    # 💡 [순서 교정] 변수를 미리 하나로 합쳐서 준비합니다
    urgent_names = []
    seen_names = set() 

    # 진짜 임박한 거 먼저 담기
    for item in all_exp_items:
        if get_exp_days(item) <= 3:
            clean_name = item['item_name'].replace(" ", "") 
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                urgent_names.append(item['item_name'])
        if len(urgent_names) >= 10: break

    # 임박한 게 너무 없으면 싱싱한 거라도 채우기 (혜진님의 플랜 B)
    if not urgent_names and all_exp_items:
        for item in all_exp_items:
            clean_name = item['item_name'].replace(" ", "")
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                urgent_names.append(item['item_name'])
            if len(urgent_names) >= 2: break

    # 3. 드디어 화면에 출력 (이제 들여쓰기가 밖으로 나와서 무조건 보입니다!)
    if urgent_names and not search_query:
        st.subheader(f"{icon_alert} 냉장고 파먹기")
        
        if 'fridge_page' not in st.session_state: st.session_state.fridge_page = 1
        items_per_page = 8
        offset = (st.session_state.fridge_page - 1) * items_per_page

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 혜진님의 SQL 쿼리 로직
                conditions = " OR ".join(["ri.name LIKE %s"] * len(urgent_names))
                count_cases = " + ".join(["MAX(CASE WHEN ri.name LIKE %s THEN 1 ELSE 0 END)"] * len(urgent_names))
                params = [f"%{name}%" for name in urgent_names] + [f"%{name}%" for name in urgent_names] + [f"%{urgent_names[0]}%"]
                
                sql = f"""
                    SELECT r.id, r.title, r.description, c.name as cat_name, r.difficulty,
                           ({count_cases}) as match_count,
                           MAX(CASE WHEN ri.name LIKE %s THEN 1 ELSE 0 END) as has_top_urgent
                    FROM recipes r 
                    LEFT JOIN recipe_categories c ON r.category_id = c.id 
                    JOIN recipe_ingredients ri ON r.id = ri.recipe_id
                    WHERE {conditions}
                    GROUP BY r.id, r.title, r.description, c.name, r.difficulty
                    ORDER BY match_count DESC, has_top_urgent DESC
                    LIMIT {items_per_page + 1} OFFSET {offset} 
                """
                cursor.execute(sql, tuple(params))
                all_fetched = cursor.fetchall()
                
                has_next = len(all_fetched) > items_per_page
                urgent_recipes = all_fetched[:items_per_page]

                if urgent_recipes:
                    cols = st.columns(2)
                    for idx, rec in enumerate(urgent_recipes):
                        with cols[idx % 2]:
                            with st.container(border=True):
                                title = clean_recipe_title(rec.get('title') or "제목 없음")
                                match_cnt = rec.get('match_count', 1)
                                st.markdown(f"**{title}** <span style='color:#EF4444; font-size:12px; font-weight:bold;'>🔥 {match_cnt}개 소진</span>", unsafe_allow_html=True)
                                if st.button("보기", key=f"urg_{st.session_state.fridge_page}_{idx}_{rec['id']}"):
                                    show_recipe_detail(rec['id'], title, rec.get('description',''), rec.get('difficulty'))
                    
                    # 💡 페이지 버튼도 밖으로 확실히 빼기
                    st.write("---")
                    b_cols = st.columns([1, 2, 1])
                    if st.session_state.fridge_page > 1:
                        if b_cols[0].button("⬅️ 이전", use_container_width=True):
                            st.session_state.fridge_page -= 1
                            st.rerun()
                    b_cols[1].markdown(f"<div style='text-align:center;'>{st.session_state.fridge_page} 페이지</div>", unsafe_allow_html=True)
                    if has_next:
                        if b_cols[2].button("다음 ➡️", use_container_width=True):
                            st.session_state.fridge_page += 1
                            st.rerun()
        finally:
            if 'conn' in locals(): conn.close()

    # --- 💡 [기능 1+2] 재료명 검색 & 페이지네이션 ---
    if search_query:
        st.subheader(f"🔍 '{search_query}' 검색 결과")
        
        items_per_page = 6 # 한 페이지당 보여줄 레시피 개수 (수정 가능!)
        offset = (st.session_state.recipe_page - 1) * items_per_page
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                search_kw = f"%{search_query}%"
                
                # 1. 총 검색 결과 개수 파악 (재료 테이블 JOIN)
                count_sql = """
                    SELECT COUNT(DISTINCT r.id) as total
                    FROM recipes r
                    LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
                    WHERE r.title LIKE %s OR r.description LIKE %s OR ri.name LIKE %s
                """
                cursor.execute(count_sql, (search_kw, search_kw, search_kw))
                total_recipes = cursor.fetchone()['total']
                total_pages = (total_recipes + items_per_page - 1) // items_per_page
                
                # 2. 현재 페이지에 해당하는 데이터만 가져오기 (LIMIT, OFFSET 적용)
                fetch_sql = """
                    SELECT DISTINCT r.id, r.title, r.description, c.name as cat_name, r.difficulty 
                    FROM recipes r 
                    LEFT JOIN recipe_categories c ON r.category_id = c.id 
                    LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
                    WHERE r.title LIKE %s OR r.description LIKE %s OR ri.name LIKE %s
                    LIMIT %s OFFSET %s
                """
                cursor.execute(fetch_sql, (search_kw, search_kw, search_kw, items_per_page, offset))
                recipes = cursor.fetchall()
        finally: conn.close()

        # 검색 결과 렌더링
        if recipes:
            st.write(f"총 **{total_recipes}**개의 레시피가 검색되었습니다.")
            cols = st.columns(2)
            for idx, rec in enumerate(recipes):
                with cols[idx % 2]:
                    with st.container(border=True):
                        cat_name = rec.get('cat_name') or "기타"
                        raw_title = rec.get('title') or "제목 없음"
                        title = clean_recipe_title(raw_title)
                        desc = rec.get('description') or ""
                        recipe_id = rec.get('id')
                        difficulty = rec.get('difficulty')
                        
                        st.markdown(f"**[{cat_name}] {title}**")
                        st.write(f"<p style='font-size:13px; color:#64748B;'>{desc[:80]}...</p>", unsafe_allow_html=True)
                        
                        # 키값이 중복되지 않게 고유 ID 적용
                        if st.button("레시피 보기", key=f"view_{recipe_id}", use_container_width=True):
                            show_recipe_detail(recipe_id, title, desc, difficulty)
            
            # --- 💡 하단 페이지 이동 버튼 ---
            st.write("---")
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if st.session_state.recipe_page > 1:
                    if st.button("⬅️ 이전 페이지", use_container_width=True):
                        st.session_state.recipe_page -= 1
                        st.rerun()
            with pc2:
                st.markdown(f"<div style='text-align:center; padding-top:5px; color:#64748B;'><b>{st.session_state.recipe_page} / {total_pages if total_pages > 0 else 1}</b></div>", unsafe_allow_html=True)
            with pc3:
                if st.session_state.recipe_page < total_pages:
                    if st.button("다음 페이지 ➡️", use_container_width=True):
                        st.session_state.recipe_page += 1
                        st.rerun()
        else:
            st.warning("일치하는 레시피나 재료가 없습니다.")
            
    # 검색어가 없을 때 기본 추천 화면
    # 검색어가 없을 때 기본 추천 화면
    else:
        st.write("---")
        
        c_title, c_btn = st.columns([4, 1])
        with c_title:
            st.subheader("🎲 오늘의 추천 레시피")
        with c_btn:
            # 💡 사용자가 원할 때만 새로운 랜덤 레시피를 뽑도록 버튼 추가
            if st.button("🔄 다른 레시피", use_container_width=True):
                st.session_state.random_recipes = [] # 보관소를 비워서 다시 뽑게 만듦

        # 💡 [핵심] 한 번 뽑은 랜덤 레시피는 세션에 저장해서 새로고침되어도 날아가지 않게 고정!
        if 'random_recipes' not in st.session_state or not st.session_state.random_recipes:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT r.id, r.title, r.description, c.name as cat_name, r.difficulty 
                        FROM recipes r 
                        LEFT JOIN recipe_categories c ON r.category_id = c.id 
                        ORDER BY RAND() 
                        LIMIT 4
                    """)
                    st.session_state.random_recipes = cursor.fetchall()
            finally: conn.close()

        # 세션에 고정된 레시피를 화면에 출력
        if st.session_state.random_recipes:
            cols = st.columns(2)
            for idx, rec in enumerate(st.session_state.random_recipes):
                with cols[idx % 2]:
                    with st.container(border=True):
                        cat_name = rec.get('cat_name') or "기타"
                        raw_title = rec.get('title') or "제목 없음"
                        title = clean_recipe_title(raw_title)
                        desc = rec.get('description') or ""
                        recipe_id = rec.get('id')
                        difficulty = rec.get('difficulty')
                        
                        st.markdown(f"**[{cat_name}] {title}**")
                        st.write(f"<p style='font-size:13px; color:#64748B;'>{desc[:80]}...</p>", unsafe_allow_html=True)
                        
                        # 이제 버튼을 눌러도 레시피가 안 바뀌므로 팝업이 무사히 뜹니다!
                        if st.button("레시피 보기", key=f"rand_rec_{recipe_id}_{idx}"):
                            show_recipe_detail(recipe_id, title, desc, difficulty)

   

elif st.session_state.page == '식비':
    st.subheader("📈 식비 분석")
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 💡 [핵심 수정] DATE_FORMAT을 써서 '이번 달(예: 2026-03)' 데이터만 쏙 뽑아옵니다!
            current_month = datetime.now().strftime('%Y-%m')
            sql = """
                SELECT spent_at AS date, amount 
                FROM user_expenses 
                WHERE user_id = %s AND DATE_FORMAT(spent_at, '%%Y-%%m') = %s
                ORDER BY spent_at ASC
            """
            cursor.execute(sql, (st.session_state.user_id, current_month))
            rows = cursor.fetchall()
            
            if rows:
                df = pd.DataFrame(rows)
                df['날짜'] = pd.to_datetime(df['date']).dt.strftime('%m/%d')
                total_val = int(df['amount'].sum()) # 소수점 방지
            else:
                df = pd.DataFrame(columns=['날짜', 'amount'])
                total_val = 0
    except Exception as e:
        st.error(f"통계 로드 오류: {e}")
        df = pd.DataFrame()
        total_val = 0
    finally:
        if 'conn' in locals() and conn.open: conn.close()
        

    st.markdown(f"""
        <div class="dash-card" style="text-align:center;">
            <p style="color:#64748B; margin-bottom:0;">{st.session_state.user_name}님의 이번 달 지출</p>
            <h1 style="color:#10B981; margin-top:0;">{total_val:,}원</h1>
        </div>
    """, unsafe_allow_html=True)
    
    # 👇 여기서부터 수정된 코드입니다! 👇
    if not df.empty:
        st.write("🗓️ 날짜별 지출 추이")
        
        # 💡 1. 스트림릿 기본 차트 대신 Plotly 면적(Area) 차트 생성
        fig = px.area(
            df, 
            x='날짜', 
            y='amount',
            labels={'날짜': '결제일', 'amount': '지출 금액 (원)'},
            markers=True
        )
        
        # 💡 2. 테마 컬러(에메랄드 그린) 및 반투명도 적용
        fig.update_traces(
            line_color='#10B981', 
            fillcolor='rgba(16, 185, 129, 0.2)'
        )
        
        # 💡 3. 배경 투명화 및 안내선 깔끔하게 튜닝
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, title=None),
            yaxis=dict(showgrid=True, gridcolor='#F1F5F9', title=None),
            hovermode='x unified'
        )
        
        # 💡 4. 화면에 출력!
        st.plotly_chart(fig, use_container_width=True)
        
    else: 
        st.info("아직 저장된 지출 내역이 없습니다. 영수증을 등록해 보세요!")



elif st.session_state.page == '냉장고':
    h_c1, h_c2 = st.columns([3, 1])
    with h_c1:
        # 💡 [수정] 제목 크기를 줄이고 줄바꿈을 방지했습니다.
        st.markdown(f"""
            <div style="display: flex; align-items: center; margin-top: -10px; margin-bottom: 5px;">
                <span style="font-size: 24px; margin-right: 8px;">{EMO_FRIDGE}</span>
                <h2 style="font-family: 'Pretendard', sans-serif; font-weight: 700; font-size: 22px; color: #000000; margin: 0; white-space: nowrap;">
                    나의 냉장고 관리
                </h2>
            </div>
        """, unsafe_allow_html=True)
    with h_c2:
        if st.button("➕ 재료 추가", key="fridge_add_btn", use_container_width=True):
            add_ingredient_popup()

    st.write("---")

    all_pantry_items = get_fridge_items(st.session_state.user_id)
    today = datetime.now().date()
    
    if all_pantry_items:
        def safe_sort_by_date(x):
            val = x.get('expiry_date')
            if not val: return datetime.max.date()
            if hasattr(val, 'date'): return val.date()
            try: return datetime.strptime(str(val), '%Y-%m-%d').date()
            except: return datetime.max.date()
        
        sorted_items = sorted(all_pantry_items, key=safe_sort_by_date)
        
        cols = st.columns(4) 
        for idx, item in enumerate(sorted_items):
            exp_date = safe_sort_by_date(item)
            if exp_date != datetime.max.date():
                d_day = (exp_date - today).days
                exp_str = exp_date.strftime('%Y-%m-%d')
                if d_day <= 3: 
                    color_class = "status-red"     
                    d_text = f"D-{d_day}" if d_day >= 0 else f"만료({abs(d_day)}일)"
                elif d_day <= 7: 
                    color_class = "status-orange"  
                    d_text = f"D-{d_day}"
                else: 
                    color_class = "status-green"   
                    d_text = f"D-{d_day}"
            else:
                color_class = "status-default"     
                exp_str = "기한 모름"
                d_text = "D-?"
            
            with cols[idx % 4]:
                raw_amt = item.get('amount')
                amt_val = float(raw_amt) if raw_amt is not None else 1.0 
                raw_unit = item.get('unit')
                unit_val = str(raw_unit) if raw_unit else '개'
                display_amt = int(amt_val) if amt_val % 1 == 0 else round(amt_val, 1)

                # 💡 [수정] 악성코드 같았던 margin-bottom: -40px 제거, 내용 겹침 해결
                st.markdown(f'''
                    <div class="dash-card {color_class}" style="padding: 12px; border-left: 5px solid; border-radius: 12px; margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <span style="font-size: 10px; color: #64748B;">{exp_str}</span>
                            <b style="font-size: 12px; font-weight: 800; text-align: right;">{d_text}</b>
                        </div>
                        <h4 style="margin: 0; color: #1E293B; font-weight: 800; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item['item_name']}</h4>
                    </div>
                ''', unsafe_allow_html=True)
                
                # 💡 [수정] 좁은 모바일 화면을 위해 버튼 글자를 짧게 수정
                col_edit_name, col_edit_amt = st.columns(2)
                with col_edit_name:
                    if st.button("✏️ 이름", key=f"btn_name_{item['id']}", use_container_width=True):
                        edit_ingredient_name(item['id'], item['item_name'])
                        
                with col_edit_amt:
                    if st.button("⚖️ 수량", key=f"btn_amt_{item['id']}", use_container_width=True):
                        edit_ingredient_amount(item['id'], item['amount'], unit_val, item['expiry_date'])
                
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
		
               

elif st.session_state.page == '찜':
    # 💡 1. 사용할 이모지들을 안전한 코드로 정의 (이미 상단에 정의했다면 생략 가능)
    EMO_HEART = "\U00002764"  # ❤️

    # 💡 2. 직접 그림을 넣지 말고 {EMO_HEART} 변수를 사용하세요!
    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-top: -10px; margin-bottom: 15px;">
            <span style="font-size: 28px; margin-right: 10px;">{EMO_HEART}</span>
            <h2 style="font-family: 'Inter', sans-serif; font-weight: 700; font-size: 28px; color: #000000; margin: 0; letter-spacing: -0.5px;">
                나의 즐겨찾기 레시피
            </h2>
        </div>
    """, unsafe_allow_html=True) # 👈 이 줄의 """ 와 ) 가 정확히 있는지 보세요!
    
    # 리스트 출력 부분의 제목 앞에도 변수로 교체!
    # st.markdown(f"**{EMO_HEART} [{cat_name}] {title}**")
    
    # 💡 2. DB에서 내가 찜한 레시피들 가져오기
    fav_recipes = get_favorite_recipes(st.session_state.user_id)
    
    if fav_recipes:
        st.write(f"총 **{len(fav_recipes)}**개의 레시피를 찜하셨어요!")
        st.write("---")
        
        # 💡 3. 레시피 카드를 2열로 예쁘게 배치
        cols = st.columns(2)
        for idx, rec in enumerate(fav_recipes):
            with cols[idx % 2]:
                with st.container(border=True):
                    cat_name = rec.get('cat_name') or "기타"
                    raw_title = rec.get('title') or "제목 없음"
                    title = clean_recipe_title(raw_title)
                    desc = rec.get('description') or ""
                    recipe_id = rec.get('id')
                    difficulty = rec.get('difficulty')
                    
                    # 제목 앞에 빨간 하트를 붙여서 즐겨찾기 느낌을 살려줍니다!
                    st.markdown(f"**❤️ [{cat_name}] {title}**")
                    
                    if desc:
                        short_desc = desc[:80] + ('...' if len(desc) > 80 else '')
                        st.write(f"<p style='font-size:13px; color:#64748B; margin-bottom: 8px;'>{short_desc}</p>", unsafe_allow_html=True)
                    else:
                        st.write("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
                        
                    # 레시피 보기 버튼 (이전에 만든 팝업 함수 재활용!)
                    if st.button("레시피 보기", key=f"fav_page_rec_{recipe_id}_{idx}", use_container_width=True):
                        show_recipe_detail(recipe_id, title, desc, difficulty)
    else:
        # 찜한 레시피가 없을 때 보여줄 안내 문구
        st.info("아직 찜한 레시피가 없습니다. 마음에 드는 레시피에 하트를 눌러보세요!")


