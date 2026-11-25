"""Channel x MMP daily dashboard. Run: streamlit run dashboard/app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st

import config
import loader
import metrics as M

st.set_page_config(page_title="채널 × MMP 대시보드", layout="wide")


@st.cache_data(show_spinner="CSV 불러오는 중…")
def _load_dir(data_dir: str, signature: tuple):
    return loader.load_all(data_dir)


@st.cache_data(show_spinner="CSV 불러오는 중…", max_entries=3)
def _load_uploads(uploads: tuple):
    return loader.load_all(uploads=list(uploads))


def fmt_int(x):
    return f"{x:,.0f}"


st.title("채널 × MMP 일별 대시보드")

# ---------- data source: local folder (if CSVs exist there) or in-app upload (cloud) ----------
has_local = bool(loader.files_signature(config.DATA_DIR))
with st.sidebar:
    st.header("데이터")
    mode = st.radio("소스", ["로컬 폴더", "파일 업로드"], horizontal=True) if has_local else "파일 업로드"
    if mode == "파일 업로드":
        ups = st.file_uploader("CSV 업로드 (복수 선택)", type="csv", accept_multiple_files=True,
                               help="파일명 규칙: YYYY-MM-DD_channel.csv, YYYY-MM-DD_appsflyer.csv")
        st.caption("업로드한 파일은 서버 메모리에서만 처리되며 디스크·저장소에 저장하지 않습니다.")
        if not ups:
            st.info("채널·앱스플라이어 CSV를 올리면 대시보드가 표시됩니다. "
                    "파일명은 `YYYY-MM-DD_channel.csv`, `YYYY-MM-DD_appsflyer.csv` 형식이어야 합니다.")
            st.stop()
        df, issues = _load_uploads(tuple((u.name, u.getvalue()) for u in ups))
    else:
        df, issues = _load_dir(str(config.DATA_DIR), loader.files_signature(config.DATA_DIR))

if df.empty:
    st.warning("읽을 수 있는 데이터가 없습니다. 파일명 규칙과 컬럼을 확인해 주세요. "
               "(정합성·검증 이슈는 아래에 표시됩니다)")
    if not issues.empty:
        st.dataframe(issues, hide_index=True, use_container_width=True)
    st.stop()

# ---------- sidebar ----------
with st.sidebar:
    st.header("필터")
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    dmin, dmax = df["date"].min().date(), df["date"].max().date()
    rng = st.date_input("기간", (dmin, dmax), min_value=dmin, max_value=dmax)
    d0, d1 = (rng[0], rng[1]) if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax)
    channels = st.multiselect("채널", sorted(df["channel"].unique()), default=sorted(df["channel"].unique()))
    camp_opts = sorted(df.loc[df["channel"].isin(channels), "campaign"].unique())
    campaigns = st.multiselect("캠페인", camp_opts, default=camp_opts)
    src_label = st.radio("집계 기준", ["매체", "MMP"], horizontal=True)
    src = "ch" if src_label == "매체" else "mmp"
    other = "mmp" if src == "ch" else "ch"
    st.caption(f"데이터: {dmin} ~ {dmax} · {df['date'].nunique()}일 · {len(df)}행")
    n_warn = int((issues["level"] != "info").sum()) if not issues.empty else 0
    if n_warn:
        st.warning(f"검증 이슈 {n_warn}건 — '정합성·검증' 탭 확인")

f = df[(df["date"].dt.date >= d0) & (df["date"].dt.date <= d1)
       & df["channel"].isin(channels) & df["campaign"].isin(campaigns)]
if f.empty:
    st.info("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["요약", "드릴다운", "정합성·검증"])

# ---------- tab 1: summary ----------
with tab1:
    tot = M.aggregate(f).iloc[0]
    st.subheader(f"KPI 요약 ({src_label} 기준)")
    cards = [("비용", "cost", fmt_int), ("회원가입", "signups", fmt_int),
             ("구매", "purchases", fmt_int), ("구매매출", "revenue", fmt_int),
             ("ROAS", "roas", lambda x: f"{x:,.0f}%")]
    cols = st.columns(3) + st.columns(3)  # two rows so long numbers don't truncate
    for c, (label, m, fn) in zip(cols, cards):
        v = tot[M.col(m, src)]
        c.metric(label, fn(v) if pd.notna(v) else "-")
        if m == "cost":
            c.caption("매체 데이터 기준")
        else:
            o = tot[M.col(m, other)]
            gap = M.pct((tot[M.col(m, "mmp")] / tot[M.col(m, "ch")] - 1) * 100) if tot[M.col(m, "ch")] else "-"
            c.caption(f"{config.SOURCE_LABEL[other]} {fn(o)} · MMP/매체 {gap}")

    st.subheader("일별 추이")
    metric_opts = {"구매": "purchases", "구매매출": "revenue", "회원가입": "signups", "클릭": "clicks",
                   "ROAS(%)": "roas", "CPA·구매": "cpa_purchase", "CPC": "cpc", "CTR(%)": "ctr"}
    pick = st.selectbox("지표", list(metric_opts))
    daily = M.aggregate(f, ["date"])
    mname = metric_opts[pick]
    long = pd.concat([daily[["date", f"{mname}_{s}"]].rename(columns={f"{mname}_{s}": "value"})
                      .assign(source=config.SOURCE_LABEL[s]) for s in ("ch", "mmp")])
    fig = px.line(long, x="date", y="value", color="source", markers=True,
                  labels={"date": "일", "value": pick, "source": "기준"})
    st.plotly_chart(fig, use_container_width=True)
    cost_fig = px.bar(daily, x="date", y="cost", labels={"date": "일", "cost": "비용"})
    st.plotly_chart(cost_fig, use_container_width=True)

# ---------- tab 2: drilldown ----------
with tab2:
    level = st.radio("집계 단위", list(config.LEVEL_COLS), horizontal=True, index=1)
    by = config.LEVEL_COLS[level]
    agg = M.aggregate(f, by)
    agg.insert(0, "label", agg[by].astype(str).agg(" › ".join, axis=1))
    show = pd.DataFrame({
        "구분": agg["label"], "비용": agg["cost"], "노출": agg["impressions"],
        "클릭": agg[M.col("clicks", src)], "회원가입": agg[M.col("signups", src)],
        "구매": agg[M.col("purchases", src)], "구매매출": agg[M.col("revenue", src)],
        "CTR(%)": agg[f"ctr_{src}"], "CPC": agg[f"cpc_{src}"],
        "CPA·구매": agg[f"cpa_purchase_{src}"], "ROAS(%)": agg[f"roas_{src}"],
    }).sort_values("비용", ascending=False)
    st.caption(f"{src_label} 기준 · 비용·노출은 매체 데이터")
    st.dataframe(show, hide_index=True, use_container_width=True, column_config={
        "비용": st.column_config.NumberColumn(format="%d"), "노출": st.column_config.NumberColumn(format="%d"),
        "클릭": st.column_config.NumberColumn(format="%d"), "회원가입": st.column_config.NumberColumn(format="%d"),
        "구매": st.column_config.NumberColumn(format="%d"), "구매매출": st.column_config.NumberColumn(format="%d"),
        "CTR(%)": st.column_config.NumberColumn(format="%.2f"), "CPC": st.column_config.NumberColumn(format="%.0f"),
        "CPA·구매": st.column_config.NumberColumn(format="%.0f"), "ROAS(%)": st.column_config.NumberColumn(format="%.0f"),
    })
    bm = st.selectbox("차트 지표", ["ROAS(%)", "CPA·구매", "구매", "구매매출"], key="bar_metric")
    bar = px.bar(show.sort_values(bm, ascending=(bm == "CPA·구매")), x=bm, y="구분", orientation="h",
                 height=max(300, 28 * len(show)))
    bar.update_layout(yaxis={"autorange": "reversed"})
    st.plotly_chart(bar, use_container_width=True)

# ---------- tab 3: reconciliation ----------
with tab3:
    st.subheader("매체 대 MMP 격차 (MMP/매체 − 1)")
    gl = {"clicks": "클릭", "signups": "회원가입", "purchases": "구매", "revenue": "구매매출"}
    lvl = st.radio("집계 단위", ["채널", "캠페인", "소재"], horizontal=True, key="gap_level")
    gby = config.LEVEL_COLS[lvl]
    g = M.aggregate(f, gby)
    g.insert(0, "label", g[gby].astype(str).agg(" › ".join, axis=1))
    gap_cols = [f"gap_{m}" for m in gl]
    heat = g.set_index("label")[gap_cols].rename(columns={f"gap_{m}": v for m, v in gl.items()})
    hfig = px.imshow(heat, text_auto=".1f", aspect="auto", color_continuous_scale="RdBu",
                     zmin=-40, zmax=40, labels={"color": "격차%"}, height=max(250, 30 * len(heat)))
    st.plotly_chart(hfig, use_container_width=True)

    st.subheader(f"임계치 초과 행 (|격차| > {config.GAP_THRESHOLD_PCT:.0f}%, 소재·일 단위)")
    rows = M.add_derived(f[f["match"] == "both"].copy())
    over = rows[(rows[gap_cols].abs() > config.GAP_THRESHOLD_PCT).any(axis=1)]
    st.caption(f"{len(over)} / {len(rows)}행")
    if len(over):
        out = over[["date", "channel", "campaign", "group", "creative"] + gap_cols].copy()
        out["date"] = out["date"].dt.date
        out = out.rename(columns={f"gap_{m}": f"{v} 격차%" for m, v in gl.items()})
        st.dataframe(out, hide_index=True, use_container_width=True)

    st.subheader("데이터 검증 이슈")
    if issues.empty:
        st.success("이슈 없음: 파일 쌍 일치, 전 행 매칭")
    else:
        st.dataframe(issues, hide_index=True, use_container_width=True)

st.divider()
st.caption("수치는 CSV 원본 합계 기반(정확). 지표 간 격차의 원인 해석은 추정이며 이 화면은 원인을 단정하지 않습니다.")
