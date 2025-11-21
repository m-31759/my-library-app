import streamlit as st
import requests
import pandas as pd
import os
import re
import numpy as np
import cv2
import zxingcpp
import sqlite3

# ==============================================================================
# [1] API 설정 및 데이터베이스 경로
# ==============================================================================
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "로컬_ID_입력")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "로컬_SECRET_입력")

DB_FILE = 'my_bookshelf.db'

# --- [함수 1] 데이터베이스 관리 ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS books (
            isbn TEXT PRIMARY KEY,
            title TEXT,
            authors TEXT,
            publisher TEXT,
            thumbnail TEXT
        )
    ''')
    conn.commit()
    return conn

def load_data_from_db():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM books", conn)
    except:
        df = pd.DataFrame(columns=['isbn', 'title', 'authors', 'publisher', 'thumbnail'])
    conn.close()
    return df

def save_book_to_db(book_data):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM books WHERE isbn = ?", (book_data['isbn'],))
    if c.fetchone():
        conn.close()
        return False, "이미 책장에 등록된 책입니다!"
    
    try:
        c.execute("INSERT INTO books VALUES (?, ?, ?, ?, ?)", 
                  (book_data['isbn'], 
                   book_data['title'], 
                   book_data['authors'], 
                   book_data['publisher'], 
                   book_data['thumbnail'])
        )
        conn.commit()
        conn.close()
        return True, "책장에 저장되었습니다!"
    except Exception as e:
        conn.close()
        return False, f"저장 실패: {e}"

# --- [함수 2] 네이버 API 검색 ---
def search_book_naver(isbn_input):
    if not NAVER_CLIENT_ID or "로컬" in NAVER_CLIENT_ID:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        return None
        
    isbn_clean = re.sub(r'[^0-9]', '', str(isbn_input))
    if not isbn_clean: return None

    url = "https://openapi.naver.com/v1/search/book.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": isbn_clean, "display": 1}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['total'] > 0:
                item = data['items'][0]
                return {
                    'title': re.sub('<.*?>', '', item['title']),
                    'authors': re.sub('<.*?>', '', item['author']),
                    'publisher': re.sub('<.*?>', '', item['publisher']),
                    'isbn': isbn_clean,
                    'thumbnail': item['image']
                }
    except: pass
    return None

# --- [함수 3] ZXing 바코드 리더 ---
def decode_with_zxing(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None: return None
        
        # 이미지 전처리 (선명하게)
        kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
        image = cv2.filter2D(image, -1, kernel)

        results = zxingcpp.read_barcodes(image)
        for result in results:
            if result.text:
                return result.text
    except Exception:
        pass
    return None


# ==============================================================================
# [메인] 화면 구성
# ==============================================================================
st.title("📚 내 방구석 도서관 (클라우드 버전)")
st.caption("바코드를 찍어 책을 등록해보세요!")

if 'current_book' not in st.session_state:
    st.session_state['current_book'] = None

tab1, tab2, tab3 = st.tabs(["📷 사진 업로드", "📹 라이브 스캔", "⌨️ 직접 입력"])

# --- [Tab 1] 사진 업로드 ---
with tab1:
    uploaded_file = st.file_uploader("바코드 사진을 올려주세요", type=['jpg', 'png', 'jpeg'])
    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 사진", width=200)
        with st.spinner("바코드 읽는 중..."):
            isbn = decode_with_zxing(uploaded_file)
            if isbn:
                st.success(f"ISBN 발견: {isbn}")
                book = search_book_naver(isbn)
                if book:
                    st.session_state['current_book'] = book
                else:
                    st.error("네이버에서 책을 찾을 수 없습니다.")
            else:
                st.warning("바코드를 찾지 못했습니다. 더 선명한 사진을 써보세요.")

# --- [Tab 2] 라이브 스캔 ---
with tab2:
    camera_img = st.camera_input("바코드를 카메라에 비춰주세요")
    if camera_img:
        with st.spinner("분석 중..."):
            isbn = decode_with_zxing(camera_img)
            if isbn:
                st.success(f"ISBN 발견: {isbn}")
                book = search_book_naver(isbn)
                if book:
                    st.session_state['current_book'] = book
            else:
                st.warning("인식 실패. 다시 시도해주세요.")

# --- [Tab 3] 직접 입력 ---
with tab3:
    isbn_manual = st.text_input("ISBN 번호를 직접 입력하세요")
    if st.button("검색"):
        book = search_book_naver(isbn_manual)
        if book:
            st.session_state['current_book'] = book
        else:
            st.error("책을 찾을 수 없습니다.")

# ==============================================================================
# [공통] 검색 결과 및 저장 로직
# ==============================================================================
if st.session_state['current_book']:
    st.divider()
    book = st.session_state['current_book']
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image(book['thumbnail'], width=100)
    with col2:
        st.subheader(book['title'])
        st.write(f"저자: {book['authors']} | 출판사: {book['publisher']}")
        st.caption(f"ISBN: {book['isbn']}")
    
    if st.button("📥 내 책장에 저장하기", use_container_width=True):
        success, msg = save_book_to_db(book)
        if success:
            st.success(msg)
            st.session_state['current_book'] = None
            st.rerun()
        else:
            st.warning(msg)

# ==============================================================================
# [목록] 저장된 책 리스트
# ==============================================================================
st.divider()
st.subheader("📂 내 책장 목록")
df = load_data_from_db()

if not df.empty:
    # 보기 좋게 데이터프레임 출력
    st.dataframe(
        df[['title', 'authors', 'publisher']], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "title": "제목",
            "authors": "저자",
            "publisher": "출판사"
        }
    )
else:
    st.info("아직 저장된 책이 없습니다. 위에서 책을 추가해보세요!")
