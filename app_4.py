import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, date

# ==============================
# 0. 세션 상태 초기값
# ==============================
if "biz_num" not in st.session_state:
    st.session_state["biz_num"] = ""


# ==========================================
# 1. 설정 및 초기화
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 기존 get_client 함수를 지우고 이 코드로 교체하세요.

def get_client():
    try:
        # [1순위] 웹(Streamlit Cloud) 환경인지 먼저 확인
        # secrets.json 파일을 찾는 게 아니라, 웹사이트에 입력한 Secrets를 먼저 봅니다.
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            
            # 줄바꿈 문자 처리 (필수)
            if "private_key" in key_dict:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
            # 파일(_file)이 아니라 정보(_info)로 인증
            creds = Credentials.from_service_account_info(key_dict, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client

        # [2순위] 웹이 아니면 내 컴퓨터(로컬) 파일 확인
        # 웹에서는 이 부분까지 오지 않으므로 에러가 안 납니다.
        elif os.path.exists("secrets.json"):
            creds = Credentials.from_service_account_file("secrets.json", scopes=SCOPES)
            client = gspread.authorize(creds)
            return client

        else:
            st.error("⚠️ 인증 정보를 찾을 수 없습니다. (웹 Secrets 설정 또는 로컬 json 파일 확인)")
            return None

    except Exception as e:
        st.error(f"⚠️ 인증 에러 발생: {e}")
        return None
# ==========================================
# 2. 데이터 로딩 (장비목록 & 사용자관리 & 기업목록)
# ==========================================

def get_master_data(client):
    """장비목록, 사용자, 기업목록 로딩"""
    try:
        doc = client.open("장비관리시스템")
        
        # [1] 장비 목록
        sheet_equip = doc.worksheet("장비목록")
        equip_records = sheet_equip.get_all_records()
        
        dept_map = {}
        info_map = {}
        
        for row in equip_records:
            dept = row.get('부서명')
            eq_name = row.get('장비명')
            eq_no = row.get('장비번호')
            eq_type = row.get('장비구분')
            if not dept or not eq_name:
                continue

            if dept not in dept_map:
                dept_map[dept] = []
            dept_map[dept].append(eq_name)
            info_map[eq_name] = {"no": eq_no, "type": eq_type}
            
        # [2] 사용자 목록
        sheet_user = doc.worksheet("사용자관리")
        user_records = sheet_user.get_all_records()
        user_db = {
            str(row['아이디']): row
            for row in user_records
            if row.get('아이디')
        }

        # [3] 기업 목록 (제목 무시하고 위치로 가져오기)
        comp_db = {}
        try:
            sheet_comp = doc.worksheet("기업목록")
            all_rows = sheet_comp.get_all_values()
            
            # 첫 줄(제목) 빼고 두 번째 줄부터 끝까지 반복
            for row in all_rows[1:]:
                if len(row) >= 2:
                    c_name = str(row[0]).strip()  # A열: 기업명
                    c_num = str(row[1]).strip()   # B열: 사업자번호
                    
                    if c_name:
                        comp_db[c_name] = c_num
        except Exception as e:
            # 기업목록 시트가 없어도 에러 안 나게 처리
            pass 
        
        return dept_map, info_map, user_db, comp_db
        
    except Exception as e:
        st.error(f"데이터 로딩 전체 에러: {e}")
        return {}, {}, {}, {}


def load_log_data(sheet):
    """장비일지 불러오기"""
    rows = sheet.get_all_values()
    cols = [
        "사용목적", "활용유형", "사용기관 기업명", "사용기관 사업자등록번호", "내부부서명",
        "업종", "품목", "세부품목", "제품명", "시료수/시험수",
        "세부지원공개여부", "세부지원내용", "장비명", "장비번호", "장비구분",
        "사용시작일", "사용종료일", "휴무일자포함", "사용시간", "사용료", "사용목적기타"
    ]
    if len(rows) <= 1:
        return pd.DataFrame(columns=cols)
    
    cleaned_rows = []
    for row in rows[1:]:
        if len(row) > 21:
            row = row[:21]
        elif len(row) < 21:
            row += [""] * (21 - len(row))
        cleaned_rows.append(row)

    return pd.DataFrame(cleaned_rows, columns=cols)


# ==========================================
# 3. 로그인 페이지
# ==========================================

def login_page():
    st.set_page_config(page_title="로그인 진단", layout="centered")
    st.title("🔒 로그인 진단 모드")
    
    if st.button("구글 시트 연결 테스트"):
        st.info("비밀번호 입력 후 로그인하세요.")

    st.markdown("---")
    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인 시도"):
            client = get_client()
            if not client:
                return
            _, _, user_db, _ = get_master_data(client)
            
            if username in user_db:
                sheet_pw = str(user_db[username]["비밀번호"]).strip()
                input_pw = str(password).strip()
                
                if sheet_pw == input_pw:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = username 
                    st.session_state["username"] = user_db[username]["이름"]
                    st.session_state["user_dept"] = user_db[username]["부서"]
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("비밀번호 불일치")
            else:
                st.error("없는 아이디입니다.")


# ==========================================
# 4. 메인 앱 (기간별 다운로드 기능 적용)
# ==========================================

def main_app():
    st.set_page_config(page_title="장비가동일지", layout="wide")
    
    # ▼▼▼ 마스터 아이디 입력란 ▼▼▼
    MASTER_IDS = ["admin", "manager"]
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

    client = get_client()
    if not client:
        return
    
    try:
        doc = client.open("장비관리시스템")
    except:
        st.error("파일 열기 실패")
        return

    dept_equip_map, equip_info_db, _, comp_db = get_master_data(client)
    
    my_id = st.session_state.get("user_id", "")
    my_name = st.session_state.get("username", "")
    my_dept = st.session_state.get("user_dept", "")
    
    is_master = (my_id in MASTER_IDS) or (my_dept == "ALL") or (my_dept == "총괄")

    # [사이드바]
    st.sidebar.title(f"👤 {my_name}님")
    if is_master:
        st.sidebar.success("👑 전체 관리자")
        dept_list = list(dept_equip_map.keys())
    else:
        st.sidebar.caption(f"소속: {my_dept}")
        dept_list = [my_dept] if my_dept in dept_equip_map else []
    
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()
    st.sidebar.markdown("---")
    
    st.sidebar.header("1. 장비 선택 (다운로드 대상)")
    sel_dept = st.sidebar.selectbox("부서", dept_list)
    equip_list = dept_equip_map.get(sel_dept, [])
    sel_equip = st.sidebar.selectbox("장비", equip_list)
    
    curr_info = equip_info_db.get(sel_equip, {"no": "", "type": ""})

    if sel_equip:
        st.title(f"📝 {sel_equip} 가동일지")
    else:
        st.title("👈 왼쪽에서 장비를 선택해주세요.")
        st.stop()

    tab1, tab2 = st.tabs(["입력하기 (Write)", "조회 및 다운로드 (Read)"])

    # ===================================
    # [탭1] 입력
    # ===================================
    with tab1:
        with st.form("main_form"):
            st.markdown("##### 1. 기본 정보")
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                f01_purpose = st.selectbox(
                    "사용목적",
                    ["시험", "분석", "계측", "생산", "교육", "기타"]
                )
            with c2:
                f02_type = st.selectbox(
                    "활용유형",
                    ["내부", "내부타부서", "외부", "간접지원"]
                )

            # [수정된 기업명 & 사업자번호 입력 부분]
            with c3:
                # 기업목록 정렬 (가나다순)
                comp_list = sorted(list(comp_db.keys()))
                comp_options = ["직접입력"] + comp_list

                sel_comp = st.selectbox(
                    "기업명 (검색 가능)",
                    comp_options,
                    placeholder="기업을 선택하세요",
                    key="sel_comp"
                )

                if sel_comp == "직접입력":
                    f03_biz_name = st.text_input("기업명 직접 작성")
                else:
                    f03_biz_name = sel_comp
                    # 선택된 기업의 사업자번호를 세션 변수에 저장
                    st.session_state["biz_num"] = comp_db.get(sel_comp, "")

            with c4:
                # 사업자번호는 session_state["biz_num"]와 연결됨
                f04_biz_num = st.text_input(
                    "사업자번호", 
                    value=st.session_state["biz_num"]
                )

            # ------------------------------
            # 2. 제품/시료 정보
            # ------------------------------
            st.markdown("##### 2. 제품/시료 정보")
            c5, c6, c7, c8 = st.columns(4)
            with c5:
                f05_dept = st.text_input("내부부서명", value=sel_dept)
            with c6:
                f06_industry = st.selectbox(
                    "업종",
                    ["기계", "전기전자", "화학", "바이오", "기타"]
                )
            with c7:
                f07_item = st.text_input("품목")
            with c8:
                f08_sub_item = st.text_input("세부품목")
            
            c9, c10 = st.columns([2, 1])
            with c9:
                f09_prod_name = st.text_input("제품명")
            with c10:
                f10_sample_cnt = st.number_input("시료수", min_value=0, step=1)

            # ------------------------------
            # 3. 상세 및 장비
            # ------------------------------
            st.markdown("##### 3. 상세 및 장비")
            c11, c12 = st.columns([1, 4])
            with c11:
                f11_public = st.radio("공개여부", ["Y", "N"], horizontal=True)
            with c12:
                f12_content = st.text_input("세부지원내용")

            c13, c14, c15 = st.columns(3)
            with c13:
                f13_eq_name = st.text_input("장비명", value=sel_equip, disabled=True)
            with c14:
                f14_eq_no = st.text_input("장비번호", value=curr_info['no'], disabled=True)
            with c15:
                f15_eq_type = st.text_input("장비구분", value=curr_info['type'], disabled=True)

            # ------------------------------
            # 4. 일정
            # ------------------------------
            st.markdown("##### 4. 일정")
            c16, c17, c18, c19, c20 = st.columns([1.2, 1.2, 0.6, 0.8, 1])
            with c16:
                f16_start = st.date_input("시작일", value=date.today())
            with c17:
                f17_end = st.date_input("종료일", value=date.today())
            with c18:
                st.write("")
                f18_holiday = st.checkbox("휴무포함")
            with c19:
                f19_hours = st.number_input("시간", min_value=0.0, step=0.5)
            with c20:
                f20_fee = st.number_input("사용료", min_value=0, step=1000)
            
            f21_etc = st.text_input("비고")

            st.markdown("---")
            if st.form_submit_button("💾 저장하기", use_container_width=True):
                val_holiday = "Y" if f18_holiday else "N"
                save_eq_no = curr_info['no']
                save_eq_type = curr_info['type']
                
                row_data = [
                    f01_purpose, f02_type, f03_biz_name, f04_biz_num, f05_dept,
                    f06_industry, f07_item, f08_sub_item, f09_prod_name, f10_sample_cnt,
                    f11_public, f12_content, sel_equip, save_eq_no, save_eq_type,
                    str(f16_start), str(f17_end), val_holiday, f19_hours, f20_fee, f21_etc
                ]
                try:
                    target_sheet = doc.worksheet(sel_equip)
                    target_sheet.append_row(row_data)
                    st.success("✅ 저장 완료!")
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    # ===================================
    # [탭2] 조회 및 다운로드
    # ===================================
    with tab2:
        c_refresh, c_dummy = st.columns([1, 5])
        with c_refresh:
            if st.button("🔄 새로고침"):
                st.rerun()
        
        try:
            target_sheet = doc.worksheet(sel_equip)
            df = load_log_data(target_sheet)
            
            if not df.empty:
                # 1. 전체 데이터 보여주기
                st.dataframe(df.iloc[::-1])
                
                st.markdown("---")
                st.subheader("📥 엑셀(CSV) 다운로드 센터")
                
                col_d1, col_d2 = st.columns([1, 1.5])
                
                # [옵션 A] 전체 다운로드
                with col_d1:
                    st.markdown("**1. 전체 데이터 받기**")
                    st.write("")
                    st.write("")
                    csv_all = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📦 전체 목록 다운로드",
                        data=csv_all,
                        file_name=f"{sel_equip}_전체.csv",
                        mime="text/csv"
                    )

                # [옵션 B] 기간별 필터링 다운로드
                with col_d2:
                    st.markdown("**2. 기간 설정 다운로드**")
                    
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        d_start = st.date_input(
                            "부터 (Start)",
                            value=date.today().replace(day=1)
                        )
                    with dc2:
                        d_end = st.date_input("까지 (End)", value=date.today())

                    # 날짜 필터링 로직
                    df['temp_date'] = pd.to_datetime(
                        df['사용시작일'],
                        errors='coerce'
                    ).dt.date
                    
                    mask = (df['temp_date'] >= d_start) & (df['temp_date'] <= d_end)
                    filtered_df = df[mask].drop(columns=['temp_date'])
                    
                    st.write(f"🔍 검색된 데이터: **{len(filtered_df)}건**")
                    
                    if not filtered_df.empty:
                        csv_filter = filtered_df.to_csv(index=False).encode('utf-8-sig')
                        file_label = f"{sel_equip}_{d_start}~{d_end}.csv"
                        st.download_button(
                            label="📅 기간별 데이터 다운로드",
                            data=csv_filter,
                            file_name=file_label,
                            mime="text/csv",
                            key="btn_period_down"
                        )
                    else:
                        st.caption("해당 기간의 데이터가 없습니다.")
            else:
                st.info("데이터가 없습니다.")
                
        except gspread.exceptions.WorksheetNotFound:
            st.warning("데이터 시트가 없습니다.")


# ==========================================
# 5. 진입점
# ==========================================

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if st.session_state["logged_in"]:
    main_app()
else:
    login_page()