import streamlit as st
import requests
import pandas as pd
import os
import re
import numpy as np
import cv2
import zxingcpp  # 👈 새로 추가된 강력한 바코드 리더기
from PIL import Image

# ==============================================================================
# 👇 [필수] 네이버 API 키 입력
# ==============================================================================
# 스트림릿 클라우드의 '비밀 금고(Secrets)'에서 키를 가져옵니다.
if 'NAVER_CLIENT_ID' in st.secrets:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
else:
    # 혹시 로컬에서 테스트할 때를 대비해 (원래 쓰던 키를 여기 입력해두면 됩니다)
    NAVER_CLIENT_ID = "아까_쓰던_내_클라이언트_ID"
    NAVER_CLIENT_SECRET = "아까_쓰던_내_시크릿_키"
# ==============================================================================

st.set_page_config(page_title="내 손안의 도서관", page_icon="📚")

# --- [함수 1] 데이터 관리 ---
CSV_FILE = 'my_bookshelf.csv'

def load_data():
    if os.path.exists(CSV_FILE):
        try: return pd.read_csv(CSV_FILE)
        except: return pd.DataFrame(columns=['title', 'authors', 'publisher', 'isbn', 'thumbnail'])
    else: return pd.DataFrame(columns=['title', 'authors', 'publisher', 'isbn', 'thumbnail'])

def save_book_to_csv(book_data):
    df = load_data()
    if str(book_data['isbn']) in df['isbn'].astype(str).values:
        return False, "이미 책장에 등록된 책입니다!"
    new_row = pd.DataFrame([book_data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    return True, "책장에 저장되었습니다!"

# --- [함수 2] 네이버 API 검색 ---
def search_book_naver(isbn_input):
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

# --- [함수 3] ZXing 바코드 리더 (성능 최강!) ---
def decode_with_zxing(image_file):
    try:
        # 1. 파일 읽어서 OpenCV 포맷(numpy array)으로 변환
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # 2. ZXing으로 바코드 찾기
        results = zxingcpp.read_barcodes(image)
        
        # 3. 결과 확인
        for result in results:
            # 책 바코드는 보통 'EAN-13' 형식이지만, 숫자만 맞으면 되므로 텍스트 반환
            if result.text:
                return result.text
                
    except Exception as e:
        st.error(f"분석 오류: {e}")
    return None

# ==============================================================================
# [메인 UI]
# ==============================================================================
st.title("📚 내 손안의 도서관 (Pro)")

if "여기에" in NAVER_CLIENT_ID:
    st.error("⚠️ API 키를 입력해주세요!")
    st.stop()

if 'current_book' not in st.session_state:
    st.session_state['current_book'] = None

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📷 고화질 촬영", "📹 라이브 스캔", "⌨️ 직접 입력"])

# [Tab 1] 고화질 촬영 (ZXing 적용)
with tab1:
    st.info("💡 가장 강력한 모드입니다. 사진을 찍어 올려주세요.")
    uploaded_file = st.file_uploader("바코드 사진 업로드", type=['jpg', 'png', 'jpeg'])
    
    if uploaded_file is not None:
        with st.spinner("ZXing 엔진으로 분석 중..."):
            # 파일 포인터 초기화
            uploaded_file.seek(0)
            detected_isbn = decode_with_zxing(uploaded_file)
            
            if detected_isbn:
                st.success(f"✅ 바코드 발견! ({detected_isbn})")
                res = search_book_naver(detected_isbn)
                if res:
                    st.session_state['current_book'] = res
                else:
                    st.warning("바코드는 읽었으나 네이버에 정보가 없습니다.")
            else:
                st.error("❌ 바코드를 찾을 수 없습니다. (배경이 너무 복잡하거나 잘렸는지 확인해주세요)")

# [Tab 2] 라이브 스캔 (ZXing 적용)
with tab2:
    st.caption("PC 웹캠 권장")
    img_file = st.camera_input("바코드 스캔")
    if img_file:
        detected_isbn = decode_with_zxing(img_file)
        if detected_isbn:
            st.success(f"인식 성공: {detected_isbn}")
            res = search_book_naver(detected_isbn)
            st.session_state['current_book'] = res
        else:
            st.warning("인식 실패")

# [Tab 3] 직접 입력
with tab3:
    with st.form('manual_form'):
        txt_input = st.text_input("ISBN 번호")
        if st.form_submit_button("검색"):
            if txt_input:
                res = search_book_naver(txt_input)
                st.session_state['current_book'] = res

# --- 공통 결과 및 저장 ---
if st.session_state['current_book']:
    book = st.session_state['current_book']
    st.divider()
    c1, c2 = st.columns([1, 2])
    with c1:
        if book['thumbnail']: st.image(book['thumbnail'], width=120)
    with c2:
        st.subheader(book['title'])
        st.write(f"{book['authors']} | {book['publisher']}")
        if st.button("📥 저장하기", use_container_width=True):
            save_book_to_csv(book)
            st.toast("저장 완료!")
            st.session_state['current_book'] = None
            st.rerun()

st.divider()
df = load_data()
if not df.empty:
    st.dataframe(df[['title', 'authors']], use_container_width=True, hide_index=True)
