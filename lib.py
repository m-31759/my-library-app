import streamlit as st
import requests
import pandas as pd
import os
import re
import numpy as np
import cv2
import zxingcpp
import sqlite3 # 👈 SQLite 데이터베이스 라이브러리 추가!

# ==============================================================================
# [1] API 설정 및 데이터베이스 경로
# ==============================================================================
# Streamlit Secrets에서 키를 가져옵니다.
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "로컬 테스트 ID")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "로컬 테스트 SECRET")

DB_FILE = 'my_bookshelf.db' # 데이터베이스 파일 이름

# --- [함수 1] 데이터베이스 관리 ---
def get_db_connection():
    """데이터베이스에 연결하고, 테이블이 없으면 생성합니다."""
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
    """DB에서 모든 책 목록을 불러옵니다."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM books", conn)
    conn.close()
    return df

def save_book_to_db(book_data):
    """새로운 책을 DB에 저장합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 중복 체크
    c.execute("SELECT 1 FROM books WHERE isbn = ?", (book_data['isbn'],))
    if c.fetchone():
        conn.close()
        return False, "이미 책장에 등록된 책입니다!"
    
    # 데이터 삽입
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

# --- [함수 2] 네이버 API 검색 (생략) --- (이전 코드와 동일)
def search_book_naver(isbn_input):
    # API 키 검사 (클라우드 배포 시 필수)
    if NAVER_CLIENT_ID == "로컬 테스트 ID":
        st.error("⚠️ 클라우드에서 실행하려면 API 키를 Streamlit Secrets에 입력해야 합니다!")
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

# --- [함수 3] ZXing 바코드 리더 --- (이전 코드와 동일)
def decode_with_zxing(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
        image = cv2.filter2D(image, -1, kernel)

        bardet = cv2.barcode.BarcodeDetector()
        results = zxingcpp.read_barcodes(image)
        
        for result in results:
            if result.text:
                return result.text
    except Exception:
        pass
    return None


# ==============================================================================
# [메인] 화면 구성 및 로직
# ==============================================================================
st.title("📚 내 방구석 도서관")
st.caption("SQLite DB로 목록이 안전하게 저장됩니다.")

if 'current_book' not in st.session_state:
    st.session_state['current_book'] = None

# 탭 구성 (UI는 이전과 동일)
tab1, tab2, tab3 = st.tabs(["📷 고화질 촬영 (추천)", "📹 라이브 스캔", "⌨️ 직접 입력"])

# --- [Tab 1, 2, 3] 검색 로직 (이전과 동일) ---
# (코드 간소화를 위해 UI 로직은 이전 코드와 동일하다고 가정하고, DB 저장 부분만 변경)

# 검색 결과 후 저장 버튼 클릭 시:
if st.session_state['current_book']:
    book = st.session_state['current_book']
    st.divider()
    
    # ... (생략: 이미지 및 텍스트 출력) ...
    
    if st.button("📥 내 책장에 저장하기", use_container_width=True):
        success, msg = save_book_to_db(book) # 👈 DB 저장 함수 호출
        if success:
            st.success(msg)
            st.session_state['current_book'] = None
            st.rerun()
        else:
            st.warning(msg)

# --- 목록 보여주기 ---
st.divider()
df = load_data_from_db() # 👈 DB에서 데이터 불러오기
st.subheader(f"📂 내 책장 ({len(df)}권)")

if not df.empty:
    st.dataframe(df[['title', 'authors', 'publisher']], use_container_width=True, hide_index=True)
else:
    st.info("책장이 비었습니다. 책을 등록해보세요!")
# (참고: 위의 UI 로직은 간소화했으나, 실제 코드는 이전 버전의 UI 로직을 사용해 주세요.)
