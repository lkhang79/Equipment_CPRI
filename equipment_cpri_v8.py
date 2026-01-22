import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import os
import io
import re

# ==============================
# ✅ [추가] 날짜/시간 전처리 함수 (활용률 0 문제 해결 핵심)
# ==============================
def clean_date_str(x):
    """'2026.01.17', '2026/01/17', '2026-01-17 00:00:00' 등을 '2026-01-17'로 정리"""
    s = "" if x is None else str(x).strip()
    if not s:
        return ""
    s = s.replace(".", "-").replace("/", "-")
    if len(s) >= 10:
        s = s[:10]
    return s

def parse_hours(x):
    """
    '2', '2.5', ' 2시간', '1,000', '0:30' 같은 값들을 float(시간)으로 변환
    """
    s = "" if x is None else str(x).strip()
    if not s:
        return 0.0

    s = s.replace(",", "")  # 1,000 -> 1000

    # 0:30 같은 형태(시:분) 처리
    if re.match(r"^\d+\s*:\s*\d+$", s):
        hh, mm = s.split(":")
        try:
            return float(hh) + float(mm) / 60.0
        except:
            return 0.0

    # 숫자만 뽑기 (예: '2시간' -> '2')
    m = re.findall(r"[-+]?\d*\.?\d+", s)
    if not m:
        return 0.0
    try:
        return float(m[0])
    except:
        return 0.0


# ==============================
# 0. 세션 상태 초기값
# ==============================
if "biz_num" not in st.session_state:
    st.session_state["biz_num"] = ""
if "selected_industry" not in st.session_state:
    st.session_state["selected_industry"] = "소재"
if "selected_item" not in st.session_state:
    st.session_state["selected_item"] = ""
if "calc_results" not in st.session_state:
    st.session_state["calc_results"] = None


# ==========================================
# 1. 설정 및 초기화
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client():
    try:
        try:
            if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
                key_dict = dict(st.secrets["gcp_service_account"])
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                creds = Credentials.from_service_account_info(key_dict, scopes=SCOPES)
                client = gspread.authorize(creds)
                return client
        except:
            pass

        SECRET_PATH = "secrets.json"

        if os.path.exists(SECRET_PATH):
            creds = Credentials.from_service_account_file(SECRET_PATH, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client
        else:
            ABS_PATH = r"E:\AI\equipment\secrets.json"
            if os.path.exists(ABS_PATH):
                creds = Credentials.from_service_account_file(ABS_PATH, scopes=SCOPES)
                client = gspread.authorize(creds)
                return client

            st.error("⚠️ secrets.json 파일을 찾을 수 없습니다.")
            return None

    except Exception as e:
        st.error(f"⚠️ 인증 에러: {e}")
        return None


# ==========================================
# 2. 업종별 품목 및 세부품목 매핑
# ==========================================
INDUSTRY_ITEMS = {
    "소재": ["세라믹", "금속", "화학", "섬유"],
    "기계로봇": ["공작기계", "일반산업기계", "건설기계", "금형", "로봇"],
    "바이오": ["바이오_의약", "의료기기"],
    "자동차운송": ["자동차_내연기관", "항공", "미래운송_드론_미래차", "전기차", "수소차", "자율차"],
    "전기전자": ["전자소자부품_제품", "광_레이저", "반도체디스플레이", "이차전지_에너지", "디지털제조"],
    "조선해양": ["조선", "해양"],
    "디자인": ["디자인_"]
}

ITEM_SUB_ITEMS = {
    "세라믹": ["후막(적층) 공정", "유리(용융/코팅) 공정", "단결정 공정", "극한환경 공정", "박막 공정"],
    "금속": ["철강소재", "비철소재"],
    "화학": ["고분자(플라스틱)", "정밀화학", "화학공정(석유화학)"],
    "섬유": ["의류용", "산업용", "생활용"],
    "공작기계": ["공작기계"],
    "일반산업기계": ["일반산업기계"],
    "건설기계": ["건설기계"],
    "금형": ["금형"],
    "로봇": ["제조업용 로봇", "전문 서비스용 로봇", "개인 서비스용 로봇", "로봇부품"],
    "바이오_의약": ["의약품", "화장품", "식품(기능성식품 포함)"],
    "의료기기": ["치료수술 기기·시스템", "기능복원·보조기기", "영상의료 기기·시스템", "진단의료 기기·시스템"],
    "자동차_내연기관": ["동력발생장치", "동력전달장치", "제동장치", "차체", "조향장치", "전기전자", "장치부품", "전기장치", "현가장치"],
    "항공": ["항공부품"],
    "미래운송_드론_미래차": ["드론 완제품/부품", "미래차 완제품/부품"],
    "전기차": ["구동부품모듈", "센서제어부품모듈", "배터리패키징부품모듈", "섀시 및 의장 모듈", "SW", "기타 소재부품모듈", "완성차"],
    "수소차": ["구동부품모듈", "센서제어부품모듈", "배터리패키징부품모듈", "섀시 및 의장 모듈", "SW", "기타 소재부품모듈", "완성차"],
    "자율차": ["구동부품모듈", "센서제어부품모듈", "배터리패키징부품모듈", "섀시 및 의장 모듈", "SW", "기타 소재부품모듈", "완성차"],
    "전자소자부품_제품": ["전기전자부품", "소형가전"],
    "광_레이저": ["광(조명)", "레이저"],
    "반도체디스플레이": ["반도체", "디스플레이"],
    "이차전지_에너지": ["이차전지", "에너지"],
    "디지털제조": ["디지털제조"],
    "조선": ["자율운항 선박", "친환경연료추진 선박", "전기추진 선박", "수소연료전지추진 선박", "하이브리드 선박", "친환경 고효율 선박"],
    "해양": ["가스오일 생산플랜트", "해양에너지플랜트", "극지해양플랜트", "스마트 야드"],
    "디자인_": ["디자인"]
}

def normalize_comp_name(name):
    """업체명 정규화: 공백 및 (주) 등 제거"""
    if not isinstance(name, str):
        return str(name)
    name = re.sub(r'\(주\)|（주）|\(주|주\)|㈜', '', name)
    name = name.replace(" ", "").strip()
    return name


# ==========================================
# 3. 데이터 로딩
# ==========================================
def get_master_data(client):
    try:
        doc = client.open("장비관리시스템")

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

        sheet_user = doc.worksheet("사용자관리")
        user_records = sheet_user.get_all_records()
        user_db = {str(row['아이디']): row for row in user_records if row.get('아이디')}

        comp_db = {}
        comp_norm_db = {}

        try:
            sheet_comp = doc.worksheet("기업목록")
            all_rows = sheet_comp.get_all_values()
            for row in all_rows[1:]:
                if len(row) >= 2:
                    c_name = str(row[0]).strip()
                    c_num = str(row[1]).strip()
                    if c_name:
                        comp_db[c_name] = c_num
                        norm_name = normalize_comp_name(c_name)
                        comp_norm_db[norm_name] = {"biz_num": c_num, "real_name": c_name}
        except:
            pass

        return dept_map, info_map, user_db, comp_db, comp_norm_db

    except Exception as e:
        st.error(f"데이터 로딩 에러: {e}")
        return {}, {}, {}, {}, {}

def load_log_data(sheet):
    rows = sheet.get_all_values()
    cols = ["사용목적", "활용유형", "사용기관 기업명", "사용기관 사업자등록번호", "내부부서명",
            "업종", "품목", "세부품목", "제품명", "시료수/시험수",
            "세부지원공개여부", "세부지원내용", "장비명", "장비번호", "장비구분",
            "사용시작일", "사용종료일", "휴무일자포함", "사용시간", "사용료", "사용목적기타"]
    if len(rows) <= 1:
        return pd.DataFrame(columns=cols)

    cleaned_rows = []
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) > 21:
            row = row[:21]
        elif len(row) < 21:
            row += [""] * (21 - len(row))
        cleaned_rows.append(row)

    df = pd.DataFrame(cleaned_rows, columns=cols)
    df.insert(0, "행번호", range(2, 2 + len(df)))
    return df

def load_maintenance_data(client, equip_name):
    try:
        doc = client.open("장비관리시스템")
        sheet_name = f"{equip_name}_유지보수"
        try:
            sheet = doc.worksheet(sheet_name)
            rows = sheet.get_all_values()
            if len(rows) <= 1:
                return pd.DataFrame(columns=["시작일", "종료일", "시간", "내용"])
            df = pd.DataFrame(rows[1:], columns=["시작일", "종료일", "시간", "내용"])
            return df
        except:
            return pd.DataFrame(columns=["시작일", "종료일", "시간", "내용"])
    except Exception:
        return pd.DataFrame(columns=["시작일", "종료일", "시간", "내용"])


# ==========================================
# 4. 로그인 페이지
# ==========================================
def login_page():
    st.set_page_config(page_title="로그인", layout="centered")
    st.title("🔒 로그인")

    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            client = get_client()
            if not client:
                return
            _, _, user_db, _, _ = get_master_data(client)

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
# 5. 메인 앱
# ==========================================
def main_app():
    st.set_page_config(page_title="장비가동일지", layout="wide")

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            min-width: 350px;
            max-width: 350px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ✅ 마스터 계정 ID 추가 (lkhang79 포함)
    MASTER_IDS = ["admin", "manager", "lkhang79"]
    
    client = get_client()
    if not client:
        return

    try:
        doc = client.open("장비관리시스템")
    except Exception as e:
        st.error(f"파일 열기 실패: {e}")
        return

    dept_equip_map, equip_info_db, _, comp_db, comp_norm_db = get_master_data(client)

    my_id = st.session_state.get("user_id", "")
    my_name = st.session_state.get("username", "")
    my_dept = st.session_state.get("user_dept", "")

    is_master = (my_id in MASTER_IDS) or (my_dept == "ALL") or (my_dept == "총괄")

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

    st.sidebar.header("1. 장비 선택")
    sel_dept = st.sidebar.selectbox("부서", dept_list)

    equip_list = dept_equip_map.get(sel_dept, [])
    sel_equip = st.sidebar.selectbox("장비", equip_list)

    curr_info = equip_info_db.get(sel_equip, {"no": "", "type": ""})

    if sel_equip:
        st.title(f"📝 {sel_equip} 가동일지")
    else:
        st.title("👈 왼쪽에서 장비를 선택해주세요.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["입력하기", "조회 및 수정/삭제", "활용률 계산"])

    def update_biz_num():
        selected = st.session_state.sel_comp_key
        if selected == "직접입력":
            st.session_state["biz_num"] = ""
        else:
            st.session_state["biz_num"] = comp_db.get(selected, "")

    # ===================================
    # [탭1] 입력
    # ===================================
    with tab1:
        st.markdown("##### 1. 기본 정보")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            f01_purpose = st.selectbox("사용목적", ["시험", "분석", "계측", "생산", "교육", "기타"])
        with c2:
            f02_type = st.selectbox("활용유형", ["내부", "내부타부서", "외부", "간접지원"])

        with c3:
            comp_list = sorted(list(comp_db.keys()))
            comp_options = ["직접입력"] + comp_list
            sel_comp = st.selectbox("기업명", comp_options, key="sel_comp_key", on_change=update_biz_num)
            if sel_comp == "직접입력":
                f03_biz_name = st.text_input("기업명 직접 작성")
            else:
                f03_biz_name = sel_comp

        with c4:
            f04_biz_num = st.text_input("사업자번호", value=st.session_state["biz_num"])

        st.markdown("##### 2. 제품/시료 정보")
        c5, c6, c7, c8 = st.columns(4)

        with c5:
            f05_dept = st.text_input("내부부서명", value=sel_dept)

        with c6:
            industry_list = list(INDUSTRY_ITEMS.keys())
            f06_industry = st.selectbox("업종", industry_list)

        with c7:
            item_options = INDUSTRY_ITEMS.get(f06_industry, [])
            if item_options:
                f07_item = st.selectbox("품목", item_options)
            else:
                f07_item = st.text_input("품목 (직접입력)")

        with c8:
            sub_item_options = ITEM_SUB_ITEMS.get(f07_item, [])
            if sub_item_options:
                f08_sub_item = st.selectbox("세부품목", sub_item_options)
            else:
                f08_sub_item = st.text_input("세부품목 (직접입력)")

        c9, c10 = st.columns([2, 1])
        with c9:
            f09_prod_name = st.text_input("제품명")
        with c10:
            f10_sample_cnt = st.number_input("시료수", min_value=0, step=1)

        st.markdown("##### 3. 상세 및 장비")
        c11, c12 = st.columns([1, 4])
        with c11:
            f11_public = st.radio("공개여부", ["Y", "N"], horizontal=True)
        with c12:
            default_template = "·지원개요: \n· 인증/인정/시험법 : \n· 지원내용 : "
            f12_content = st.text_area("세부지원내용", value=default_template, height=200)

        c13, c14, c15 = st.columns(3)
        with c13:
            f13_eq_name = st.text_input("장비명", value=sel_equip, disabled=True)
        with c14:
            f14_eq_no = st.text_input("장비번호", value=curr_info['no'], disabled=True)
        with c15:
            f15_eq_type = st.text_input("장비구분", value=curr_info['type'], disabled=True)

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
        if st.button("💾 저장하기", use_container_width=True):
            val_holiday = "Y" if f18_holiday else "N"
            row_data = [
                f01_purpose, f02_type, f03_biz_name, f04_biz_num, f05_dept,
                f06_industry, f07_item, f08_sub_item, f09_prod_name, f10_sample_cnt,
                f11_public, f12_content, sel_equip, curr_info['no'], curr_info['type'],
                str(f16_start), str(f17_end), val_holiday, f19_hours, f20_fee, f21_etc
            ]
            try:
                target_sheet = doc.worksheet(sel_equip)
                target_sheet.append_row(row_data)
                st.success("✅ 저장 완료!")
            except Exception as e:
                st.error(f"저장 실패: {e}")

        # ==========================================================
        # ✅ 엑셀 파일 일괄 업로드 섹션 (자동 보정 기능 추가)
        # ==========================================================
        st.markdown("---")
        st.subheader("📂 엑셀 일괄 업로드")

        template_cols = ["사용목적", "활용유형", "사용기관 기업명", "사용기관 사업자등록번호", "내부부서명",
                         "업종", "품목", "세부품목", "제품명", "시료수/시험수",
                         "세부지원공개여부", "세부지원내용", "장비명", "장비번호", "장비구분",
                         "사용시작일", "사용종료일", "휴무일자포함", "사용시간", "사용료", "사용목적기타"]

        df_template = pd.DataFrame(columns=template_cols)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_template.to_excel(writer, index=False, sheet_name='Sheet1')
        excel_data = output.getvalue()

        col_down, col_up = st.columns([1, 2.5])
        with col_down:
            st.download_button(
                label="⬇️ 장비일지 양식(빈칸) 다운로드",
                data=excel_data,
                file_name='장비일지_양식.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        with st.expander("📢 장비일지 엑셀 업로드 시 유의사항 (클릭하여 확인)", expanded=False):
            st.markdown("""
            **※ 장비일지 엑셀 업로드 시 유의사항**
            - 다운로드 받은 양식의 컬럼 순서를 변경하지 마세요.
            - 날짜 형식: YYYY-MM-DD
            - 1000건 이하로 작성 권장
            
            **✨ 자동 보정 기능**
            - 업체명이 등록된 업체와 유사하면 자동으로 정확한 이름과 사업자번호로 매칭됩니다.
            - 예: "주식회사ABC" → "(주)ABC"로 자동 보정
            - 장비명이 등록된 장비명과 일치하지 않으면 오류로 표시됩니다.
            """)

        with col_up:
            uploaded_file = st.file_uploader("작성된 엑셀 파일 업로드", type=["xlsx"])

        if uploaded_file:
            try:
                df_upload = pd.read_excel(uploaded_file)
                required_cols = ["사용기관 기업명", "사용기관 사업자등록번호", "장비명"]
                missing = [c for c in required_cols if c not in df_upload.columns]

                if missing:
                    st.error(f"❌ 필수 컬럼이 누락되었습니다: {missing} (양식을 확인해주세요)")
                else:
                    st.info(f"🔎 총 {len(df_upload)}개의 데이터 검토 중...")

                    valid_rows = []
                    error_logs = []
                    auto_corrected = []  # ✅ 자동 보정된 항목 추적

                    for idx, row in df_upload.iterrows():
                        def get_val(col_name):
                            val = row.get(col_name, "")
                            return str(val).strip() if pd.notna(val) else ""

                        u_company = get_val("사용기관 기업명")
                        u_biz_num = get_val("사용기관 사업자등록번호")
                        u_equip_name = get_val("장비명")

                        row_data_for_save = []
                        for col in template_cols:
                            row_data_for_save.append(get_val(col))

                        reasons = []
                        corrected_info = {}

                        # ✅ 장비명 검증 (자동 보정 불가 - 반드시 정확해야 함)
                        if u_equip_name not in equip_info_db:
                            reasons.append(f"등록되지 않은 장비명: {u_equip_name}")

                        # ✅ 업체명 자동 보정
                        norm_u_comp = normalize_comp_name(u_company)
                        corrected_company = u_company
                        corrected_biz_num = u_biz_num

                        if norm_u_comp in comp_norm_db:
                            # 정규화된 이름으로 매칭됨 - 정확한 업체명과 사업자번호로 대체
                            master_info = comp_norm_db[norm_u_comp]
                            corrected_company = master_info["real_name"]
                            corrected_biz_num = master_info["biz_num"]
                            
                            # 원본과 다르면 자동 보정 로그 기록
                            if u_company != corrected_company or u_biz_num != corrected_biz_num:
                                corrected_info = {
                                    "행 번호": idx + 2,
                                    "원본 기업명": u_company,
                                    "보정 기업명": corrected_company,
                                    "원본 사업자번호": u_biz_num,
                                    "보정 사업자번호": corrected_biz_num
                                }
                                auto_corrected.append(corrected_info)
                        else:
                            # 매칭되지 않음
                            if u_company:
                                reasons.append(f"미등록 업체 (정확한 이름 확인 필요): {u_company}")

                        if not reasons:
                            # ✅ 보정된 값으로 저장
                            formatted_row = []
                            for i, col in enumerate(template_cols):
                                if col == "사용기관 기업명":
                                    formatted_row.append(corrected_company)
                                elif col == "사용기관 사업자등록번호":
                                    formatted_row.append(corrected_biz_num)
                                else:
                                    formatted_row.append(row_data_for_save[i])
                            valid_rows.append(formatted_row)
                        else:
                            error_logs.append({
                                "행 번호": idx + 2,
                                "기업명": u_company,
                                "장비명": u_equip_name,
                                "오류 내용": ", ".join(reasons)
                            })

                    # ✅ 자동 보정 내역 표시
                    if auto_corrected:
                        st.success(f"✨ 자동 보정: {len(auto_corrected)}건의 업체 정보가 자동으로 수정되었습니다.")
                        with st.expander("📋 자동 보정 내역 보기", expanded=False):
                            st.table(pd.DataFrame(auto_corrected))

                    if error_logs:
                        st.error(f"❌ 검토 실패: 총 {len(error_logs)}건의 오류가 발견되었습니다.")
                        st.table(pd.DataFrame(error_logs))

                    if valid_rows:
                        st.success(f"✅ PASS: 검토 통과! (총 {len(valid_rows)}건)")

                        if st.button(f"🚀 검토 완료된 {len(valid_rows)}건 저장하기", type="primary"):
                            success_count = 0
                            from collections import defaultdict
                            grouped_data = defaultdict(list)

                            for v_row in valid_rows:
                                eq_name = v_row[12]
                                grouped_data[eq_name].append(v_row)

                            progress_bar = st.progress(0)
                            curr_idx = 0
                            total_groups = len(grouped_data)

                            for eq_name, rows in grouped_data.items():
                                try:
                                    target_sheet = doc.worksheet(eq_name)
                                    target_sheet.append_rows(rows)
                                    success_count += len(rows)
                                except Exception as e:
                                    st.error(f"[{eq_name}] 저장 중 에러: {e}")

                                curr_idx += 1
                                progress_bar.progress(curr_idx / total_groups)

                            st.balloons()
                            st.success(f"🎉 총 {success_count}건 저장이 완료되었습니다!")
                    else:
                        st.warning("⚠️ 저장할 수 있는 유효한 데이터가 없습니다. 오류를 수정한 후 다시 업로드해주세요.")

            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {e}")


    # ===================================
    # [탭2] 조회 및 수정/삭제
    # ===================================
    with tab2:
        if st.button("🔄 새로고침"):
            st.rerun()

        try:
            target_sheet = doc.worksheet(sel_equip)
            df = load_log_data(target_sheet)

            if not df.empty:
                st.dataframe(df.sort_values(by="행번호", ascending=False), use_container_width=True)

                st.markdown("---")

                with st.expander("🛠 데이터 수정 및 삭제 (클릭)", expanded=False):
                    st.write("위 표에서 **'행번호'**를 확인 후 입력해주세요.")

                    row_options = df["행번호"].tolist()
                    selected_row_num = st.selectbox("수정/삭제할 행번호(No.) 선택", row_options)

                    selected_data = df[df["행번호"] == selected_row_num].iloc[0]

                    st.info(f"선택된 데이터: **{selected_data['사용기관 기업명']}** / {selected_data['사용시작일']} ({selected_data['사용시간']}시간)")

                    with st.form("edit_form"):
                        st.write("#### 📝 내용 수정")
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            e_comp = st.text_input("기업명", value=selected_data["사용기관 기업명"])
                        with ec2:
                            e_date = st.text_input("사용시작일(YYYY-MM-DD)", value=selected_data["사용시작일"])
                        with ec3:
                            try:
                                curr_hours = float(selected_data["사용시간"])
                            except:
                                curr_hours = 0.0
                            e_hours = st.number_input("사용시간", value=curr_hours, step=0.5)

                        e_content = st.text_area("세부지원내용", value=selected_data["세부지원내용"], height=100)

                        col_btn1, col_btn2 = st.columns([1, 1])

                        with col_btn1:
                            if st.form_submit_button("✏️ 수정사항 저장"):
                                try:
                                    cols_order = ["사용목적", "활용유형", "사용기관 기업명", "사용기관 사업자등록번호", "내부부서명",
                                                 "업종", "품목", "세부품목", "제품명", "시료수/시험수",
                                                 "세부지원공개여부", "세부지원내용", "장비명", "장비번호", "장비구분",
                                                 "사용시작일", "사용종료일", "휴무일자포함", "사용시간", "사용료", "사용목적기타"]

                                    new_values = []
                                    for col in cols_order:
                                        if col == "사용기관 기업명":
                                            new_values.append(e_comp)
                                        elif col == "사용시작일":
                                            new_values.append(e_date)
                                        elif col == "사용시간":
                                            new_values.append(e_hours)
                                        elif col == "세부지원내용":
                                            new_values.append(e_content)
                                        else:
                                            new_values.append(selected_data[col])

                                    cell_range = f"A{selected_row_num}:U{selected_row_num}"
                                    target_sheet.update(range_name=cell_range, values=[new_values])

                                    st.success(f"{selected_row_num}번 행이 수정되었습니다!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"수정 실패: {e}")

                        with col_btn2:
                            pass

                    st.write("#### 🗑 데이터 삭제")
                    if st.checkbox("정말 삭제하시겠습니까?", key="del_confirm"):
                        if st.button("❌ 선택된 행 삭제", type="primary"):
                            try:
                                target_sheet.delete_rows(int(selected_row_num))
                                st.success(f"{selected_row_num}번 행이 삭제되었습니다.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")

                st.markdown("---")
                st.subheader("📥 다운로드")

                col_d1, col_d2 = st.columns([1, 1.5])

                with col_d1:
                    st.markdown("**전체 데이터**")
                    csv_all = df.drop(columns=["행번호"]).to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📦 전체 다운로드", csv_all, f"{sel_equip}_전체.csv", "text/csv")

                with col_d2:
                    st.markdown("**기간 설정**")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        d_start = st.date_input("부터", value=date.today().replace(day=1))
                    with dc2:
                        d_end = st.date_input("까지", value=date.today())

                    df['temp_date'] = pd.to_datetime(df['사용시작일'], errors='coerce').dt.date
                    mask = (df['temp_date'] >= d_start) & (df['temp_date'] <= d_end)
                    filtered_df = df[mask].drop(columns=['temp_date'])

                    st.write(f"🔍 검색: **{len(filtered_df)}건**")

                    if not filtered_df.empty:
                        csv_filter = filtered_df.drop(columns=["행번호"]).to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📅 기간별 다운로드", csv_filter,
                                           f"{sel_equip}_{d_start}~{d_end}.csv", "text/csv", key="period_dl")
            else:
                st.info("데이터가 없습니다.")
        except:
            st.warning("데이터 시트가 없습니다.")


    # ===================================
    # [탭3] 활용률 계산 (세션 상태 유지)
    # ===================================
    with tab3:
        st.header(f"📊 {sel_equip} 장비 활용률")

        # 1. 유지보수 입력
        st.subheader("🔧 유지보수/고장 시간 입력")
        with st.form("maintenance_form"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                m_start = st.date_input("시작일", value=date.today(), key="m_start")
            with mc2:
                m_end = st.date_input("종료일", value=date.today(), key="m_end")
            with mc3:
                m_hours = st.number_input("시간", min_value=0.0, step=0.5, key="m_hours")
            m_content = st.text_input("내용", key="m_content")

            if st.form_submit_button("💾 유지보수 기록 저장"):
                try:
                    sheet_name = f"{sel_equip}_유지보수"
                    try:
                        m_sheet = doc.worksheet(sheet_name)
                    except:
                        m_sheet = doc.add_worksheet(title=sheet_name, rows=100, cols=4)
                        m_sheet.append_row(["시작일", "종료일", "시간", "내용"])
                    m_sheet.append_row([str(m_start), str(m_end), m_hours, m_content])
                    st.success("✅ 저장 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

        st.markdown("---")

        # 2. 활용률 계산 및 표 출력
        st.subheader("📈 활용률 계산 (기간 설정)")

        calc_col1, calc_col2 = st.columns(2)
        with calc_col1:
            calc_start = st.date_input("시작일", value=date.today().replace(month=1, day=1), key="calc_start")
        with calc_col2:
            calc_end = st.date_input("종료일", value=date.today(), key="calc_end")

        if st.button("🔍 결과 산출하기", use_container_width=True):
            try:
                # [A] 가동가능시간 계산
                date_range = pd.date_range(start=calc_start, end=calc_end)
                workdays = date_range[date_range.dayofweek < 5]
                annual_available_hours = len(workdays) * 8.0

                # [D, E] 사용 데이터
                target_sheet = doc.worksheet(sel_equip)
                df = load_log_data(target_sheet)

                internal_hours = 0.0
                external_hours = 0.0

                if not df.empty:
                    # ✅ [핵심] 날짜/시간 전처리로 0 문제 해결
                    df['사용시작일_raw'] = df['사용시작일']
                    df['사용시작일'] = df['사용시작일'].apply(clean_date_str)
                    df['사용시작일'] = pd.to_datetime(df['사용시작일'], errors='coerce')

                    df['사용시간_raw'] = df['사용시간']
                    df['사용시간'] = df['사용시간'].apply(parse_hours)

                    df['활용유형'] = df['활용유형'].astype(str).str.strip()

                    mask = (df['사용시작일'].dt.date >= calc_start) & (df['사용시작일'].dt.date <= calc_end)
                    period_df = df.loc[mask].copy()

                    if period_df.empty:
                        st.warning("⚠️ 선택 기간에 해당하는 데이터가 없습니다. (날짜 형식/기간 확인)")
                        st.write("최근 데이터(원본 날짜/파싱 날짜/원본 시간/파싱 시간) 샘플:")
                        st.dataframe(
                            df[['사용시작일_raw', '사용시작일', '사용시간_raw', '사용시간', '활용유형']].tail(20),
                            use_container_width=True
                        )

                    internal_hours = period_df[period_df['활용유형'].str.contains('내부', na=False)]['사용시간'].sum()
                    external_hours = period_df[period_df['활용유형'].str.contains('외부', na=False)]['사용시간'].sum()

                # [C] 유지보수 시간
                maintenance_df = load_maintenance_data(client, sel_equip)
                maintenance_hours = 0.0

                if not maintenance_df.empty:
                    maintenance_df['시작일_raw'] = maintenance_df['시작일']
                    maintenance_df['시작일'] = maintenance_df['시작일'].apply(clean_date_str)
                    maintenance_df['시작일'] = pd.to_datetime(maintenance_df['시작일'], errors='coerce')

                    maintenance_df['시간_raw'] = maintenance_df['시간']
                    maintenance_df['시간'] = maintenance_df['시간'].apply(parse_hours)

                    m_mask = (maintenance_df['시작일'].dt.date >= calc_start) & (maintenance_df['시작일'].dt.date <= calc_end)
                    period_m_df = maintenance_df.loc[m_mask].copy()

                    maintenance_hours = period_m_df['시간'].sum()

                # [계산 로직]
                actual_available_hours = annual_available_hours - maintenance_hours
                actual_usage_hours = external_hours + internal_hours

                if actual_available_hours > 0:
                    utilization_rate = (actual_usage_hours / actual_available_hours)
                    external_rate = (external_hours / actual_available_hours)
                else:
                    utilization_rate = 0.0
                    external_rate = 0.0

                data = {
                    "가동가능시간\n(A)=고정값": [f"{annual_available_hours:,.1f}"],
                    "실제이용가능시간\n(B)=(A)-(C)": [f"{actual_available_hours:,.1f}"],
                    "유지보수시간\n(C)": [f"{maintenance_hours:,.1f}"],
                    "외부활용시간\n(D)": [f"{external_hours:,.1f}"],
                    "내부활용시간\n(E)": [f"{internal_hours:,.1f}"],
                    "실제이용시간\n(F)=(D)+(E)": [f"{actual_usage_hours:,.1f}"],
                    "장비가동률\n(G)=(F)/(B)": [f"{utilization_rate*100:.2f}%"],
                    "외부가동비율\n(H)=(D)/(B)": [f"{external_rate*100:.2f}%"]
                }
                result_df = pd.DataFrame(data)

                st.session_state["calc_results"] = {
                    "df": result_df,
                    "actual_available": actual_available_hours,
                    "actual_usage": actual_usage_hours,
                    "workdays_count": len(workdays),
                    "range_str": f"{calc_start} ~ {calc_end}"
                }

            except Exception as e:
                st.error(f"계산 중 오류 발생: {e}")

        if st.session_state["calc_results"] is not None:
            res = st.session_state["calc_results"]

            st.write("")
            st.markdown(f"#### 📅 기간: {res['range_str']}")
            st.dataframe(res['df'], hide_index=True, use_container_width=True)
            st.info(f"💡 **가동가능시간(A)**는 선택하신 기간 중 주말(토/일)을 제외한 {res['workdays_count']}일 × 8시간으로 자동 계산되었습니다.")

            if res['actual_usage'] == 0:
                st.warning("⚠️ 계산된 사용 시간이 0시간입니다. '사용시작일' 형식 또는 '사용시간' 값(예: 2시간/0:30/1,000 등)을 확인해주세요.")

            st.markdown("---")
            st.subheader("🎯 목표 가동률 대비 필요 시간 계산")

            col_calc1, col_calc2 = st.columns([1, 2])

            with col_calc1:
                target_rate = st.number_input("목표 가동률(%) 입력", min_value=0.0, max_value=100.0, value=70.0, step=5.0)

            with col_calc2:
                actual_av = res['actual_available']
                actual_us = res['actual_usage']

                target_usage_hours = actual_av * (target_rate / 100)
                needed_hours = target_usage_hours - actual_us

                st.write(f"**목표 달성 기준 시간:** {target_usage_hours:,.1f}시간")

                if needed_hours > 0:
                    st.error(f"🔥 목표 달성을 위해 **{needed_hours:,.1f}시간**의 추가 가동이 필요합니다!")
                elif actual_av == 0:
                    st.warning("이용 가능 시간이 0시간입니다.")
                else:
                    st.success(f"🎉 축하합니다! 이미 목표를 **{abs(needed_hours):,.1f}시간** 초과 달성했습니다.")


# ==========================================
# 6. 진입점
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if st.session_state["logged_in"]:
    main_app()
else:
    login_page()
