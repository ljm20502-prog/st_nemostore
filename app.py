import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Nemostore Professional EDA Dashboard", layout="wide")

# --- UTILS ---
def format_krw(amount):
    """금액을 읽기 쉬운 원 단위 콤마 형식으로 포맷팅"""
    if pd.isna(amount):
        return "N/A"
    return f"{int(amount):,}원"

def calculate_interest_score(row):
    """관심도(Interest Score) 계산: viewCount + (favoriteCount * 3)"""
    return row.get('viewCount', 0) + (row.get('favoriteCount', 0) * 3)

# --- DATA LOADING ---
@st.cache_data
def load_data(source_type="DB", uploaded_file=None):
    """데이터 소스(DB 또는 CSV)로부터 데이터 로드"""
    if source_type == "CSV" and uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            return df
        except Exception as e:
            st.error(f"CSV 로드 중 오류 발생: {e}")
            return pd.DataFrame()
    else:
        # nemo_store.db를 우선적으로 확인
        db_path = "data/nemo_store.db"
        if not os.path.exists(db_path):
            db_path = "data/nemostore.db"
        
        if not os.path.exists(db_path):
            return pd.DataFrame()

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT * FROM stores", conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"DB 로드 중 오류 발생: {e}")
            return pd.DataFrame()

def preprocess_data(df):
    """데이터 전처리: 단위 변환 및 파생 변수 생성"""
    if df.empty:
        return df
    
    # 1. 금액 단위 변환 (JSON 1,000 -> KRW 1)
    amount_cols = ['deposit', 'monthlyRent', 'premium', 'maintenanceFee']
    for col in amount_cols:
        if col in df.columns:
            df[col] = df[col] * 1000
    
    # 2. 관심도 점수 계산
    df['interestScore'] = df.apply(calculate_interest_score, axis=1)
    
    # 3. 평당 월세 계산 (size 대비 월세)
    # size가 0인 경우를 방지하기 위해 0.01로 대체하거나 NaN 처리 가능
    df['rent_per_area'] = df.apply(lambda r: (r['monthlyRent'] / r['size']) if r['size'] > 0 else 0, axis=1)
    
    # 4. 날짜 변환
    if 'createdDateUtc' in df.columns:
        df['createdDateUtc'] = pd.to_datetime(df['createdDateUtc'])
    
    return df

# --- SECTION 1: OVERVIEW ---
def create_overview_section(df):
    st.header("📊 SECTION 1: 전체 EDA 개요")
    
    # KPI 카드
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("전체 매물 수", f"{len(df):,}개")
    m2.metric("중앙 보증금", format_krw(df['deposit'].median()))
    m3.metric("중앙 월세", format_krw(df['monthlyRent'].median()))
    m4.metric("평균 면적", f"{df['size'].mean():.2f}㎡")
    m5.metric("평균 권리금", format_krw(df['premium'].mean()))
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        # 월세 분포
        fig_rent = px.histogram(df, x="monthlyRent", title="월세 분포 (KRW)", 
                                labels={"monthlyRent": "월세"}, color_discrete_sequence=['#1f77b4'])
        st.plotly_chart(fig_rent, use_container_width=True)
        
        # 보증금 분포
        fig_dep = px.histogram(df, x="deposit", title="보증금 분포 (KRW)", 
                               labels={"deposit": "보증금"}, color_discrete_sequence=['#aec7e8'])
        st.plotly_chart(fig_dep, use_container_width=True)

    with c2:
        # 월세 vs 면적 산점도
        fig_scatter = px.scatter(df, x="size", y="monthlyRent", color="businessLargeCodeName",
                                 title="면적 대비 월세 상관관계", 
                                 labels={"size": "면적(㎡)", "monthlyRent": "월세"},
                                 hover_data=["title"])
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        # 업종 대분류별 매물 수
        type_counts = df['businessLargeCodeName'].value_counts().reset_index()
        type_counts.columns = ['업종', '매물수']
        fig_bar = px.bar(type_counts, x='업종', y='매물수', title="업종 대분류별 매물 수",
                         color_discrete_sequence=['#1f77b4'])
        st.plotly_chart(fig_bar, use_container_width=True)

    # 자동 인사이트 (Overview)
    st.info(f"""
    **[Overview Insight]** 
    - 현재 시장의 중앙 월세는 **{format_krw(df['monthlyRent'].median())}**이며, 가장 매물이 많은 업종은 **{df['businessLargeCodeName'].mode()[0]}**입니다.
    - 면적과 월세 사이에는 정(+)의 상관관계가 관찰됩니다.
    """)

# --- SECTION 2: INDUSTRY ANALYSIS ---
def create_industry_analysis(df):
    st.header("🏢 SECTION 2: 업종별 시장 분석")
    
    # 사이드바 필터는 호출부(main)에서 처리됨
    # 여기서는 필터링된 데이터(df)를 대상으로 시각화
    
    m1, m2, m3, m4 = st.columns(4)
    if not df.empty:
        m1.metric("선택 업종 평균 월세", format_krw(df['monthlyRent'].mean()))
        m2.metric("선택 업종 평균 보증금", format_krw(df['deposit'].mean()))
        m3.metric("평균 평당 월세", format_krw(df['rent_per_area'].mean()))
        m4.metric("평균 관심도 점수", f"{df['interestScore'].mean():.2f}")
    
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        # 층별 월세 Box Plot
        fig_box = px.box(df, x="floor", y="monthlyRent", title="층별 월세 분포",
                         labels={"floor": "층수", "monthlyRent": "월세"})
        st.plotly_chart(fig_box, use_container_width=True)
        
        # 업종별 평균 월세 비교 (데이터가 충분할 때)
        avg_rent_by_sub = df.groupby('businessMiddleCodeName')['monthlyRent'].mean().sort_values(ascending=False).reset_index()
        fig_ind_bar = px.bar(avg_rent_by_sub, x='monthlyRent', y='businessMiddleCodeName', orientation='h',
                             title="중분류별 평균 월세 규모", labels={"monthlyRent": "평균 월세", "businessMiddleCodeName": "중분류"})
        st.plotly_chart(fig_ind_bar, use_container_width=True)

    with c2:
        # 평당 월세 Top 10
        top_rent_per_area = df.nlargest(10, 'rent_per_area')
        fig_top_rent = px.bar(top_rent_per_area, x='rent_per_area', y='title', orientation='h',
                              title="평당 월세 Top 10 매물", labels={"rent_per_area": "평당 월세", "title": "매물명"})
        fig_top_rent.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top_rent, use_container_width=True)
        
        # 관심도 상위 매물
        top_interest = df.nlargest(10, 'interestScore')
        fig_top_interest = px.bar(top_interest, x='interestScore', y='title', orientation='h',
                                  title="관심도(조회+찜) 상위 매물", labels={"interestScore": "관심도 점수", "title": "매물명"})
        fig_top_interest.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top_interest, use_container_width=True)

    # 자동 인사이트 (Industry)
    if not df.empty:
        high_rent_floor = df.groupby('floor')['monthlyRent'].mean().idxmax()
        st.info(f"""
        **[Market Insight]** 
        - 분석 결과, **{high_rent_floor}층** 매물의 평균 월세가 가장 높게 형성되어 있습니다.
        - **{df.nlargest(1, 'rent_per_area')['title'].values[0]}** 매물이 평당 효율 측면에서 가장 높은 가치를 보이고 있습니다.
        """)

# --- SECTION 3: SEARCH & DETAILS ---
def create_search_section(df):
    st.header("🔍 SECTION 3: 매물 검색 & 상세 조회")
    
    c1, c2, c3 = st.columns(3)
    search_keyword = c1.text_input("제목 키워드 검색")
    subway_keyword = c2.text_input("지하철역 키워드 검색")
    min_interest = c3.slider("최소 관심도 점수", 0, int(df['interestScore'].max() if not df.empty else 100), 0)
    
    # 검색 필터 적용
    search_df = df.copy()
    if search_keyword:
        search_df = search_df[search_df['title'].str.contains(search_keyword, case=False, na=False)]
    if subway_keyword:
        search_df = search_df[search_df['nearSubwayStation'].str.contains(subway_keyword, case=False, na=False)]
    search_df = search_df[search_df['interestScore'] >= min_interest]
    
    # 테이블 표시용 가공
    display_cols = ['title', 'businessMiddleCodeName', 'monthlyRent', 'deposit', 'premium', 'size', 'interestScore']
    display_df = search_df[display_cols].copy()
    for col in ['monthlyRent', 'deposit', 'premium']:
        display_df[col] = display_df[col].apply(lambda x: f"{int(x):,}")
    
    st.dataframe(display_df.rename(columns={
        'title': '매물명', 'businessMiddleCodeName': '업종', 'monthlyRent': '월세(원)', 
        'deposit': '보증금(원)', 'premium': '권리금(원)', 'size': '면적(㎡)', 'interestScore': '관심도'
    }), use_container_width=True)
    
    st.subheader("📋 개별 매물 상세 정보")
    for _, row in search_df.iterrows():
        with st.expander(f"📌 {row['title']} ({row['businessMiddleCodeName']})"):
            sc1, sc2, sc3 = st.columns(3)
            sc1.write(f"**보증금:** {format_krw(row['deposit'])}")
            sc1.write(f"**월세:** {format_krw(row['monthlyRent'])}")
            sc1.write(f"**권리금:** {format_krw(row['premium'])}")
            
            sc2.write(f"**면적:** {row['size']}㎡")
            sc2.write(f"**층수:** {row['floor']} / {row['groundFloor']}")
            sc2.write(f"**평당 월세:** {format_krw(row['rent_per_area'])}")
            
            sc3.write(f"**관리비:** {format_krw(row['maintenanceFee'])}")
            sc3.write(f"**관심도:** {row['interestScore']} 점")
            sc3.write(f"**생성일:** {row['createdDateUtc'].strftime('%Y-%m-%d') if pd.notna(row['createdDateUtc']) else 'N/A'}")
            st.write(f"**주변역:** {row['nearSubwayStation']}")

# --- MAIN ---
def main():
    st.title("🏙️ Nemostore Professional EDA & Market Insights")
    st.markdown("""
    이 대시보드는 상업용 부동산 데이터 수집 결과를 바탕으로 시장 트렌드 분석 및 매물 리서치를 지원하기 위해 설계되었습니다.
    좌측 사이드바를 통해 데이터 소스를 선택하거나 필터를 조정할 수 있습니다.
    """)
    
    # SIDEBAR: DATA SOURCE
    st.sidebar.title("🛠️ 데이터 옵션")
    data_source = st.sidebar.radio("데이터 소스 선택", ["SQLite DB", "CSV 파일 업로드"])
    
    raw_df = pd.DataFrame()
    if data_source == "SQLite DB":
        raw_df = load_data(source_type="DB")
    else:
        uploaded_file = st.sidebar.file_uploader("CSV 파일 업로드", type="csv")
        if uploaded_file:
            raw_df = load_data(source_type="CSV", uploaded_file=uploaded_file)
    
    if raw_df.empty:
        st.warning("데이터가 로드되지 않았습니다. DB 존재 여부나 업로드 파일을 확인하세요.")
        return

    # PREPROCESS
    df = preprocess_data(raw_df)
    
    # SIDEBAR: FILTERS
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 필터링")
    
    # 업종 필터
    large_codes = ["전체"] + sorted(df['businessLargeCodeName'].unique().tolist())
    selected_large = st.sidebar.selectbox("업종 대분류", large_codes)
    
    filtered_df = df.copy()
    if selected_large != "전체":
        filtered_df = filtered_df[filtered_df['businessLargeCodeName'] == selected_large]
        
    middle_codes = ["전체"] + sorted(filtered_df['businessMiddleCodeName'].unique().tolist())
    selected_middle = st.sidebar.selectbox("업종 중분류", middle_codes)
    if selected_middle != "전체":
        filtered_df = filtered_df[filtered_df['businessMiddleCodeName'] == selected_middle]

    # 금액/면적 필터
    dep_range = st.sidebar.slider("보증금 범위 (만원)", 0, int(df['deposit'].max()/10000), (0, int(df['deposit'].max()/10000)))
    rent_range = st.sidebar.slider("월세 범위 (만원)", 0, int(df['monthlyRent'].max()/10000), (0, int(df['monthlyRent'].max()/10000)))
    size_range = st.sidebar.slider("면적 범위 (㎡)", 0, int(df['size'].max()), (0, int(df['size'].max())))
    
    filtered_df = filtered_df[
        (filtered_df['deposit'] >= dep_range[0] * 10000) & (filtered_df['deposit'] <= dep_range[1] * 10000) &
        (filtered_df['monthlyRent'] >= rent_range[0] * 10000) & (filtered_df['monthlyRent'] <= rent_range[1] * 10000) &
        (filtered_df['size'] >= size_range[0]) & (filtered_df['size'] <= size_range[1])
    ]

    # TABS
    tab1, tab2, tab3 = st.tabs(["전체 EDA", "업종 분석", "매물 탐색"])
    
    with tab1:
        create_overview_section(df) # 전체 데이터 기준 개요
    
    with tab2:
        create_industry_analysis(filtered_df) # 필터링된 데이터 기준 분석
        
    with tab3:
        create_search_section(filtered_df) # 필터링된 데이터 기준 검색

if __name__ == "__main__":
    main()
