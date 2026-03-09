import streamlit as st
import pandas as pd
import requests, uuid, time, json, pymysql, re
from datetime import datetime, timedelta


# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="AI 냉장고 요리사", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    .stButton > button { border-radius: 20px; border: 1px solid #E2E8F0; background: white; color: #64748B; font-weight: 600; }
    .stButton > button:hover { border-color: #10B981; color: #10B981; }
    .dash-card { background: white; padding: 20px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #F1F5F9; margin-bottom: 20px; }
    .fridge-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; border-radius: 12px; margin-bottom: 8px; border-left: 6px solid; }
    .status-red { background-color: #FEF2F2; border-left-color: #EF4444; color: #991B1B; }
    .status-orange { background-color: #FFFBEB; border-left-color: #F59E0B; color: #92400E; }
    .status-green { background-color: #F0FDF4; border-left-color: #10B981; color: #166534; }
    .recipe-card { background: white; border-radius: 16px; border: 1px solid #F1F5F9; overflow: hidden; margin-bottom: 20px; transition: 0.3s; }
    </style>
""", unsafe_allow_html=True)

# --- 2. OCR 설정 및 DB 연결 함수 ---
INVOKE_URL = "https://apuc0c1uh7.apigw.ntruss.com/recipe/real_receipt/infer"
SECRET_KEY = "QmhEampKY0lxdEp5aEdCUHBHbUJHTFFReEhXSGZsVHo="

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='root', # 실제 비밀번호 입력
        db='cooking_db',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# --- 로그인 상태 초기화 ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = ""

# --- 로그인 화면 구현 ---
if not st.session_state.logged_in:
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    
    # 탭을 나눠서 로그인과 회원가입을 깔끔하게 분리
    tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])
    
    with tab_login:
        login_email = st.text_input("이메일", key="login_email")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        
        if st.button("로그인", use_container_width=True):
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 사용자가 입력한 이메일과 비번이 DB에 있는지 확인 (기억해낸다!)
                sql = "SELECT id, name FROM users WHERE email = %s AND password_hash = %s"
                cursor.execute(sql, (login_email, login_pw))
                user = cursor.fetchone()
                
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user['id']
                    st.session_state.user_name = user['name']
                    st.success(f"반가워요, {user['name']}님!")
                    st.rerun()
                else:
                    st.error("이메일 또는 비밀번호가 틀렸어요. 회원가입을 먼저 해주세요!")
            conn.close()

    with tab_signup:
        st.write("새로운 계정을 만듭니다.")
        new_email = st.text_input("사용할 이메일", key="new_email")
        new_pw = st.text_input("사용할 비밀번호", type="password", key="new_pw")
        new_name = st.text_input("이름 (닉네임)", key="new_name")
        
        if st.button("가입하기", use_container_width=True):
            if new_email and new_pw and new_name:
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        # 사용자가 준 정보를 DB에 저장 (기억시킨다!)
                        sql = "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s)"
                        cursor.execute(sql, (new_email, new_pw, new_name))
                    conn.commit()
                    st.success("이제 가입하신 정보로 로그인이 가능합니다! '로그인' 탭으로 가주세요.")
                except Exception as e:
                    st.error(f"이미 등록된 이메일이거나 오류가 발생했어요: {e}")
                finally:
                    conn.close()
            else:
                st.warning("모든 항목을 입력해주세요.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def get_db_ingredients():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "SELECT name, shelf_life_days FROM ingredients"
            cursor.execute(sql)
            return cursor.fetchall()
    except Exception as e:
        st.error(f"DB 재료 로드 오류: {e}")
        return []
    finally:
        if 'conn' in locals(): conn.close()

# --- 3. 세션 상태 초기화 ---
if 'page' not in st.session_state: st.session_state.page = '대시보드'
if 'total_spend' not in st.session_state: st.session_state.total_spend = 0
if 'spend_data' not in st.session_state:
    st.session_state.spend_data = pd.DataFrame(columns=['날짜', '금액'])
if 'fav_recipes' not in st.session_state: st.session_state.fav_recipes = []

# 지출 합산 함수 (통합)
def add_expense(amount):
    if 1000 <= amount <= 300000:
        st.session_state.total_spend += amount
        new_row = pd.DataFrame({'날짜': [datetime.now().strftime('%m/%d')], '금액': [amount]})
        st.session_state.spend_data = pd.concat([st.session_state.spend_data, new_row], ignore_index=True)

# --- 4. 메뉴바 ---
st.markdown('<h2 style="color:#10B981; text-align:center;">나만의 레시피🥬</h2>', unsafe_allow_html=True)
nav = st.columns(5)
m_list = ["📊 대시보드", "🍴 레시피", "🫙 냉장고", "📈 식비통계", "❤️ 즐겨찾기"]
for i, m in enumerate(m_list):
    if nav[i].button(m, use_container_width=True):
        st.session_state.page = m.split(" ")[1]

st.write("---")

# --- 5. 페이지 구현 ---
if st.session_state.page == '대시보드':
    # 상단 환영 메시지
    st.write(f"## 안녕하세요, {st.session_state.user_name}님! 👋")
    st.write("오늘도 맛있는 요리 만들어볼까요?")

    uploaded_file = st.file_uploader("📸 영수증 사진을 올려주세요", type=["jpg", "jpeg", "png"])

    # 변수 초기화
    matched_items = []
    total_price = 0
    today = datetime.now()

    if uploaded_file:
        with st.spinner('🚀 영수증에서 재료와 유통기한을 찾는 중...'):
            img_bytes = uploaded_file.getvalue()
            message = {'images': [{'format': 'jpg', 'name': 'receipt'}], 'requestId': str(uuid.uuid4()), 'version': 'V2', 'timestamp': int(round(time.time() * 1000))}
            headers = {'X-OCR-SECRET': SECRET_KEY}
            files = {'file': ('receipt.jpg', img_bytes, 'image/jpeg'), 'message': (None, json.dumps(message), 'application/json')}

            try:
                # 1. OCR 호출
                response = requests.post(INVOKE_URL, headers=headers, files=files)
                res = response.json()
                
                # 2. 텍스트 추출 및 합치기
                all_fields = [f['inferText'] for img in res.get('images', []) for f in img.get('fields', [])]
                full_text_scan = "".join(all_fields).replace(" ", "")

                # [디버깅] 영수증에서 읽은 글자 확인 (나중에 재료 안 뜨면 이 부분을 보세요)
                # st.write("🔍 읽은 글자:", full_text_scan) 

                # 3. 총액 추출
                all_nums = [int(re.sub(r'[^0-9]', '', w)) for w in all_fields if 4 <= len(re.sub(r'[^0-9]', '', w)) <= 8]
                total_price = max(all_nums) if all_nums else 0

                # 4. DB 재료 매칭 및 유통기한 계산
                db_data = get_db_ingredients() # 이 함수는 코드 상단에 정의되어 있어야 함
                if not db_data:
                    st.warning("⚠️ DB의 ingredients 테이블에 데이터가 없습니다.")

                for row in db_data:
                    raw_db_name = row['name']
                    # DB 이름에서 ( ) 제거 및 공백 제거 후 비교
                    clean_db_name = re.sub(r'\(.*\)', '', raw_db_name).replace(" ", "").strip()
                    
                    if clean_db_name and clean_db_name in full_text_scan:
                        if row['shelf_life_days'] is not None:
                            days = int(row['shelf_life_days'])
                            expiry = (today + timedelta(days=days)).strftime('%Y-%m-%d')
                        else:
                            expiry = "기한 정보 없음"
                        
                        matched_items.append({"매칭된 재료": raw_db_name, "유통기한": expiry})
                
                # 중복 제거
                if matched_items:
                    matched_items = pd.DataFrame(matched_items).drop_duplicates('매칭된 재료').to_dict('records')

            except Exception as e:
                st.error(f"분석 중 오류 발생: {e}")

    # --- 대시보드 UI 배치 ---
    # (1) 상단 요약 카드
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="stat-card"><p class="stat-title">인식된 재료</p><p class="stat-value">{len(matched_items)}개</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><p class="stat-title">유통기한 계산</p><p class="stat-value" style="color:#10B981;">{"완료" if uploaded_file else "-"}</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><p class="stat-title">영수증 총액</p><p class="stat-value">{total_price:,}원</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="stat-card" style="background:#3B82F6; color:white;"><p class="stat-title" style="color:white;">상태</p><p class="stat-value">정상</p></div>', unsafe_allow_html=True)

    st.write("---")

    # (2) 중앙 섹션 (재료 목록 & 필터)
    col_left, col_right = st.columns([1.2, 0.8])

    with col_left:
        st.markdown('<div class="content-box"><div class="box-header">📋 재료 및 유통기한 목록</div>', unsafe_allow_html=True)
        if matched_items:
            st.table(matched_items) 
            # 저장 버튼 추가
            if st.button("💾 냉장고에 모두 저장하기"):
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        for item in matched_items:
                            sql = "INSERT INTO fridge (user_id, name, expiry_date) VALUES (%s, %s, %s)"
                            cursor.execute(sql, (st.session_state.user_id, item['매칭된 재료'], item['유통기한']))
                        
                        if total_price > 0:
                            sql_e = "INSERT INTO expenses (user_id, amount, date) VALUES (%s, %s, %s)"
                            cursor.execute(sql_e, (st.session_state.user_id, total_price, datetime.now()))
                    conn.commit()
                    st.success("냉장고와 지출 내역에 저장되었습니다!")
                except Exception as e:
                    st.error(f"저장 실패: {e}")
                finally:
                    conn.close()
        else:
            st.info("영수증을 올리면 여기에 재료와 유통기한이 표시됩니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="dash-card"><h4>🎯 맞춤 레시피 필터</h4>', unsafe_allow_html=True)

        f1, f2 = st.columns(2)

        with f1: st.multiselect("음식 종류", ["한식", "중식", "일식", "양식"], default=["한식"])

        with f2: st.radio("영양 테마", ["고단백", "저당", "비건", "저칼로리"], horizontal=True)

    with right_col:
        st.subheader("🧊 내 냉장고 (임박순)")
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # 임의의 데이터 (실제 데이터로 연결 가능)
        fridge_data = [{"name": "닭가슴살", "dday": 0, "class": "status-red"}, {"name": "우유", "dday": 2, "class": "status-orange"}]
        for item in fridge_data:
            st.markdown(f'<div class="fridge-item {item["class"]}"><span>{item["name"]}</span><b>D-{item["dday"] if item["dday"] > 0 else "Day"}</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == '식비통계':
    st.subheader("📈 식비 분석")
    
    # 1. DB에서 해당 유저의 지출 내역 불러오기
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 해당 유저의 지출 데이터만 필터링하여 가져옴
            sql = "SELECT date, amount FROM expenses WHERE user_id = %s ORDER BY date ASC"
            cursor.execute(sql, (st.session_state.user_id,))
            rows = cursor.fetchall()
            
            # 결과가 있다면 데이터프레임으로 변환
            if rows:
                df = pd.DataFrame(rows)
                # DB의 datetime 객체를 '05/22' 같은 문자열 형식으로 변환 (그래프 가독성)
                df['날짜'] = pd.to_datetime(df['date']).dt.strftime('%m/%d')
                total_val = df['amount'].sum()
            else:
                df = pd.DataFrame(columns=['날짜', 'amount'])
                total_val = 0
    except Exception as e:
        st.error(f"통계 로드 오류: {e}")
        df = pd.DataFrame()
        total_val = 0
    finally:
        conn.close()

    # 2. 화면 표시 (카드 및 그래프)
    st.markdown(f"""
        <div class="dash-card" style="text-align:center;">
            <p style="color:#64748B; margin-bottom:0;">{st.session_state.user_name}님의 누적 지출</p>
            <h1 style="color:#10B981; margin-top:0;">{total_val:,}원</h1>
        </div>
    """, unsafe_allow_html=True)
    
    if not df.empty:
        st.write("🗓️ 날짜별 지출 추이")
        # 막대 그래프와 선 그래프 표시
        st.line_chart(df.set_index('날짜')['amount'])
        st.bar_chart(df.set_index('날짜')['amount'])
    else:
        st.info("아직 저장된 지출 내역이 없습니다. 영수증을 등록해 보세요!")

elif st.session_state.page == '레시피':
    st.subheader("🍴 추천 레시피")
    # 레시피 카드 및 즐겨찾기 로직 (보내주신 코드 유지)

elif st.session_state.page == '즐겨찾기':
    st.subheader("❤️ 즐겨찾기 목록")
    # 즐겨찾기 리스트 로직