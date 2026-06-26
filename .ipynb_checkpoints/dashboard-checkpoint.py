import streamlit as st
import pandas as pd
import numpy as np
import pymysql
from sqlalchemy import create_engine, text
from pymongo import MongoClient
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Dashboard UMKM Indonesia",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# KONFIGURASI KONEKSI
# ─────────────────────────────────────────────
MYSQL_HOST     = "localhost"
MYSQL_USER     = "root"
MYSQL_PASSWORD = ""
MYSQL_DB       = "db_umkm_shopee"
MYSQL_PORT     = 3307

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB  = "db_umkm_shopee"

# ─────────────────────────────────────────────
# KONEKSI DATABASE
# ─────────────────────────────────────────────
@st.cache_resource
def get_mysql_engine():
    return create_engine(
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )

@st.cache_resource
def get_mongo_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[MONGO_DB]

# ─────────────────────────────────────────────
# LOAD DATA (cache 10 menit)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_transaksi(_engine):
    return pd.read_sql("SELECT * FROM transaksi", _engine)

@st.cache_data(ttl=600)
def load_kategori(_engine):
    return pd.read_sql("SELECT * FROM transaksi_kategori", _engine)

@st.cache_data(ttl=600)
def load_cross_analytics(_engine):
    return pd.read_sql("SELECT * FROM cross_system_analytics", _engine)

@st.cache_data(ttl=600)
def load_log_pembatalan():
    mongo_db = get_mongo_db()
    docs = list(mongo_db["log_pembatalan"].find(
        {}, {"_id":0,"order_id":1,"provinsi":1,"alasan_pembatalan":1,
             "metode_pembayaran":1,"potensi_revenue":1,"total_qty":1}
    ))
    return pd.DataFrame(docs) if docs else pd.DataFrame()

@st.cache_data(ttl=600)
def load_cross_mongo():
    mongo_db = get_mongo_db()
    pipeline = [
        {"$group": {
            "_id": "$provinsi",
            "total_batal": {"$sum": 1},
            "alasan_terbanyak": {"$first": "$alasan_pembatalan"},
            "revenue_hilang":   {"$sum": "$potensi_revenue"},
        }},
        {"$sort": {"total_batal": -1}},
    ]
    docs = list(mongo_db["log_pembatalan"].aggregate(pipeline))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    df.rename(columns={"_id": "provinsi"}, inplace=True)
    return df


# ═════════════════════════════════════════════
# MAIN APP
# ═════════════════════════════════════════════
def main():

    # ── Header ──
    st.markdown("""
    <h1 style='text-align:center; color:#2C3E50;'>
        🏪 Dashboard UMKM Indonesia
    </h1>
    <p style='text-align:center; color:#7F8C8D; font-size:16px;'>
        Sistem Big Data Terintegrasi: MySQL + MongoDB + Apache Spark
    </p>
    <hr>
    """, unsafe_allow_html=True)

    # ── Cek koneksi ──
    col_s1, col_s2 = st.columns(2)
    try:
        engine = get_mysql_engine()
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        col_s1.success("✅ MySQL: Terhubung")
    except Exception as e:
        col_s1.error(f"❌ MySQL: {e}")
        st.stop()

    try:
        mongo_db = get_mongo_db()
        mongo_db.list_collection_names()
        col_s2.success("✅ MongoDB: Terhubung")
    except Exception as e:
        col_s2.error(f"❌ MongoDB: {e}")
        st.stop()

    # ── Load data ──
    with st.spinner("Memuat data dari MySQL & MongoDB..."):
        df       = load_transaksi(engine)
        df_kat   = load_kategori(engine)
        df_cross = load_cross_analytics(engine)
        df_batal = load_log_pembatalan()
        df_mongo = load_cross_mongo()

    # ─────────────────────────────────────────────
    # SIDEBAR FILTER
    # ─────────────────────────────────────────────
    st.sidebar.header("🔽 Filter Data")

    tahun_list = sorted(
    df["tahun"]
    .dropna()
    .astype(int)       
    .unique()
    .tolist()
    )

    tahun_sel = st.sidebar.multiselect(
    "Tahun",
    tahun_list,
    default=tahun_list
    )

    status_list = sorted(df["status_pesanan"].dropna().unique().tolist())
    status_sel  = st.sidebar.multiselect("Status Pesanan", status_list, default=status_list)

    prov_list = sorted(df["provinsi"].dropna().unique().tolist())
    prov_sel  = st.sidebar.multiselect("Provinsi (kosong = semua)", prov_list, default=[])

    bayar_list = sorted(df["metode_pembayaran"].dropna().unique().tolist())
    bayar_sel  = st.sidebar.multiselect("Metode Pembayaran", bayar_list, default=bayar_list)

    st.sidebar.markdown("---")
    st.sidebar.caption("🗄️ Sumber: MySQL + MongoDB\nProyek Big Data — SQL & NoSQL")

    # ── Terapkan filter ──
    mask = (
        df["tahun"].isin(tahun_sel) &
        df["status_pesanan"].isin(status_sel) &
        df["metode_pembayaran"].isin(bayar_sel)
    )
    if prov_sel:
        mask = mask & df["provinsi"].isin(prov_sel)
    df_f = df[mask].copy()

    if df_f.empty:
        st.warning("Tidak ada data yang sesuai filter.")
        st.stop()

    # ─────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────
    st.subheader("📊 Key Performance Indicators")

    total_order  = len(df_f)
    sel_mask     = df_f["status_pesanan"] == "Selesai"
    bat_mask     = df_f["status_pesanan"] == "Batal"
    total_rev    = df_f.loc[sel_mask, "total_pembayaran"].sum()
    success_rate = df_f[sel_mask].shape[0] / total_order * 100 if total_order else 0
    cancel_rate  = df_f[bat_mask].shape[0]  / total_order * 100 if total_order else 0
    avg_order    = df_f.loc[sel_mask, "total_pembayaran"].mean() if sel_mask.any() else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("🛒 Total Order",     f"{total_order:,}")
    k2.metric("💰 Total Revenue",   f"Rp {total_rev/1e9:.2f}M")
    k3.metric("✅ Success Rate",    f"{success_rate:.1f}%")
    k4.metric("❌ Cancel Rate",     f"{cancel_rate:.1f}%")
    k5.metric("📦 Avg Order Value", f"Rp {avg_order:,.0f}")

    st.markdown("---")

    # ─────────────────────────────────────────────
    # TABS
    # ─────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Overview Penjualan",
        "🗺️ Analisis Provinsi",
        "💳 Metode Pembayaran",
        "🔗 Integrasi SQL↔NoSQL",
        "🏷️ Kategori & Waktu",
    ])

    # ── TAB 1: OVERVIEW ──────────────────────────
    with tab1:
        st.subheader("Overview Penjualan")
        c1, c2 = st.columns(2)

        df_tren = (
            df_f.groupby(["tahun","bulan"])
            .agg(jumlah_order=("order_id","count"),
                 total_penjualan=("total_pembayaran","sum"))
            .reset_index()
        )
        df_tren["periode"] = (
            df_tren["tahun"].astype(str) + "-" +
            df_tren["bulan"].astype(str).str.zfill(2)
        )
        fig_tren = make_subplots(specs=[[{"secondary_y":True}]])
        fig_tren.add_trace(go.Bar(
            x=df_tren["periode"], y=df_tren["total_penjualan"]/1e6,
            name="Revenue (Juta Rp)", marker_color="#3498DB", opacity=0.7
        ), secondary_y=False)
        fig_tren.add_trace(go.Scatter(
            x=df_tren["periode"], y=df_tren["jumlah_order"],
            name="Jumlah Order", line=dict(color="#E67E22",width=2), mode="lines+markers"
        ), secondary_y=True)
        fig_tren.update_layout(title="Tren Bulanan: Revenue & Order",
                               hovermode="x unified", height=380,
                               legend=dict(orientation="h",y=-0.2))
        fig_tren.update_yaxes(title_text="Revenue (Juta Rp)", secondary_y=False)
        fig_tren.update_yaxes(title_text="Jumlah Order",      secondary_y=True)
        c1.plotly_chart(fig_tren, use_container_width=True)

        status_cnt = df_f["status_pesanan"].value_counts().reset_index()
        status_cnt.columns = ["status","jumlah"]
        cmap = {"Selesai":"#2ECC71","Batal":"#E74C3C",
                "Dalam Pengiriman":"#3498DB","Diterima":"#F39C12"}
        fig_status = px.pie(status_cnt, values="jumlah", names="status",
                            title="Distribusi Status Pesanan",
                            color="status", color_discrete_map=cmap, hole=0.4)
        fig_status.update_traces(textinfo="label+percent+value")
        fig_status.update_layout(height=380)
        c2.plotly_chart(fig_status, use_container_width=True)

        fig_gauge = go.Figure(go.Indicator(
            mode="number+gauge+delta",
            value=success_rate,
            delta={"reference":80,"valueformat":".1f"},
            title={"text":"Order Success Rate (%)"},
            gauge={
                "axis":{"range":[0,100]},
                "bar":{"color":"#2C3E50"},
                "steps":[
                    {"range":[0,50],"color":"#E74C3C"},
                    {"range":[50,80],"color":"#F1C40F"},
                    {"range":[80,100],"color":"#2ECC71"},
                ],
                "threshold":{"line":{"color":"red","width":4},"thickness":0.75,"value":90}
            }
        ))
        fig_gauge.update_layout(height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)

    # ── TAB 2: PROVINSI ──────────────────────────
    with tab2:
        st.subheader("Analisis per Provinsi")
        top_n = st.slider("Top N Provinsi", 5, 34, 15)

        df_prov = (
            df_f[df_f["status_pesanan"]=="Selesai"]
            .groupby("provinsi")
            .agg(total_revenue=("total_pembayaran","sum"),
                 jumlah_order=("order_id","count"))
            .sort_values("total_revenue",ascending=False)
            .head(top_n).reset_index()
        )
        fig_prov = px.bar(
            df_prov, x="total_revenue", y="provinsi", orientation="h",
            title=f"Top {top_n} Provinsi — Total Revenue",
            color="total_revenue", color_continuous_scale="Blues",
            text=df_prov["total_revenue"].apply(lambda x: f"Rp {x/1e6:.1f}M"),
            labels={"total_revenue":"Revenue (Rp)","provinsi":"Provinsi"}
        )
        fig_prov.update_traces(textposition="auto")
        fig_prov.update_layout(height=500, showlegend=False,
                               yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig_prov, use_container_width=True)

        if not df_cross.empty and "risk_level" in df_cross.columns:
            risk_colors = {"CRITICAL":"#E74C3C","HIGH":"#E67E22",
                           "MEDIUM":"#F1C40F","LOW":"#2ECC71"}
            fig_risk = px.bar(
                df_cross.sort_values("tingkat_pembatalan_pct",ascending=False).head(20),
                x="provinsi", y="tingkat_pembatalan_pct",
                color="risk_level", color_discrete_map=risk_colors,
                title="Risk Level Pembatalan per Provinsi (Top 20)",
                labels={"tingkat_pembatalan_pct":"Tingkat Batal (%)","provinsi":"Provinsi"},
                category_orders={"risk_level":["CRITICAL","HIGH","MEDIUM","LOW"]}
            )
            fig_risk.update_layout(height=420, xaxis_tickangle=-40)
            st.plotly_chart(fig_risk, use_container_width=True)

    # ── TAB 3: PEMBAYARAN ────────────────────────
    with tab3:
        st.subheader("Analisis Metode Pembayaran")

        df_pay = (
            df_f.groupby("metode_pembayaran")
            .agg(jumlah=("order_id","count"),
                 total_nilai=("total_pembayaran","sum"))
            .sort_values("jumlah",ascending=False).reset_index()
        )
        c1, c2 = st.columns(2)

        fig_pie = px.pie(df_pay, values="jumlah", names="metode_pembayaran",
                         title="Distribusi Jumlah Transaksi (%)",
                         hole=0.35, color_discrete_sequence=px.colors.qualitative.Set3)
        fig_pie.update_traces(textinfo="label+percent")
        fig_pie.update_layout(height=400)
        c1.plotly_chart(fig_pie, use_container_width=True)

        fig_bar = px.bar(df_pay, x="metode_pembayaran", y="total_nilai",
                         title="Total Nilai Transaksi per Metode",
                         color="total_nilai", color_continuous_scale="Teal",
                         text=df_pay["total_nilai"].apply(lambda x: f"Rp {x/1e6:.0f}M"),
                         labels={"total_nilai":"Nilai (Rp)","metode_pembayaran":"Metode"})
        fig_bar.update_traces(textposition="auto")
        fig_bar.update_layout(height=400, showlegend=False)
        c2.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Heatmap: Metode Pembayaran vs Status")
        pivot = df_f.groupby(["metode_pembayaran","status_pesanan"]).size().unstack(fill_value=0)
        fig_heat = px.imshow(pivot, text_auto=True, aspect="auto",
                             color_continuous_scale="Blues",
                             title="Jumlah Transaksi: Metode vs Status")
        fig_heat.update_layout(height=400)
        st.plotly_chart(fig_heat, use_container_width=True)

    # ── TAB 4: INTEGRASI SQL↔NoSQL ───────────────
    with tab4:
        st.subheader("🔗 Integrasi Real-Time: MySQL + MongoDB")
        st.caption("JOIN langsung saat dashboard dibuka — data selalu fresh")

        st.info("🗄️ **MySQL** memberi data penjualan per provinsi")
        st.info("🍃 **MongoDB** memberi data pembatalan per provinsi")

        sql_live = pd.read_sql("""
            SELECT provinsi,
                   COUNT(*) AS total_pesanan,
                   SUM(total_pembayaran) AS total_revenue,
                   COUNT(CASE WHEN status_pesanan='Selesai' THEN 1 END) AS pesanan_selesai,
                   COUNT(CASE WHEN status_pesanan='Batal'   THEN 1 END) AS pesanan_batal
            FROM transaksi GROUP BY provinsi ORDER BY total_revenue DESC
        """, engine)

        if not df_mongo.empty:
            merged = sql_live.merge(df_mongo, on="provinsi", how="left")
            merged["total_batal"]      = merged["total_batal"].fillna(0).astype(int)
            merged["revenue_hilang"]   = merged["revenue_hilang"].fillna(0).astype(int)
            merged["alasan_terbanyak"] = merged["alasan_terbanyak"].fillna("N/A")
        else:
            merged = sql_live.copy()
            merged["total_batal"]      = merged["pesanan_batal"]
            merged["revenue_hilang"]   = 0
            merged["alasan_terbanyak"] = "N/A"

        merged["rasio_konversi"] = (merged["pesanan_selesai"]/merged["total_pesanan"]*100).round(1)
        merged["rasio_batal"]    = (merged["total_batal"]/merged["total_pesanan"]*100).round(1)

        st.dataframe(
            merged[["provinsi","total_pesanan","total_revenue","rasio_konversi",
                    "total_batal","rasio_batal","revenue_hilang","alasan_terbanyak"]]
            .rename(columns={
                "total_pesanan":"Total Order","total_revenue":"Revenue (Rp)",
                "rasio_konversi":"Konversi (%)","total_batal":"Batal",
                "rasio_batal":"% Batal","revenue_hilang":"Revenue Hilang",
                "alasan_terbanyak":"Alasan Terbanyak",
            }),
            use_container_width=True, height=400
        )

        fig_scatter = px.scatter(
            merged, x="rasio_konversi", y="total_revenue",
            size="total_pesanan", color="rasio_batal",
            hover_name="provinsi", color_continuous_scale="RdYlGn_r",
            title="Konversi Rate vs Revenue (warna = % batal, ukuran = total order)",
            labels={"rasio_konversi":"Konversi (%)","total_revenue":"Revenue (Rp)"}
        )
        fig_scatter.update_layout(height=450)
        st.plotly_chart(fig_scatter, use_container_width=True)

        if not df_batal.empty and "alasan_pembatalan" in df_batal.columns:
            alasan_cnt = (df_batal["alasan_pembatalan"]
                          .value_counts().head(10).reset_index())
            alasan_cnt.columns = ["alasan","jumlah"]
            fig_alasan = px.bar(
                alasan_cnt, x="jumlah", y="alasan", orientation="h",
                title="Top 10 Alasan Pembatalan (MongoDB)",
                color="jumlah", color_continuous_scale="Reds", text="jumlah"
            )
            fig_alasan.update_traces(textposition="auto")
            fig_alasan.update_layout(height=400, showlegend=False,
                                     yaxis={"categoryorder":"total ascending"})
            st.plotly_chart(fig_alasan, use_container_width=True)

    # ── TAB 5: KATEGORI & WAKTU ──────────────────
    with tab5:
        st.subheader("Analisis Kategori Produk & Pola Waktu")
        c1, c2 = st.columns(2)

        df_kat_merge = df_kat.merge(
            df_f[["order_id","status_pesanan","total_pembayaran"]], on="order_id"
        ).query("status_pesanan == 'Selesai'")

        top_kat = (
            df_kat_merge.groupby("kategori")
            .agg(jumlah_order=("order_id","count"),
                 total_penjualan=("total_pembayaran","sum"))
            .sort_values("jumlah_order",ascending=False)
            .head(10).reset_index()
        )
        fig_kat = px.bar(
            top_kat, x="jumlah_order", y="kategori", orientation="h",
            title="Top 10 Kategori Produk Terlaris",
            color="total_penjualan", color_continuous_scale="Viridis",
            text=top_kat["jumlah_order"].apply(lambda x: f"{x:,}"),
            labels={"jumlah_order":"Jumlah Order","kategori":"Kategori"}
        )
        fig_kat.update_traces(textposition="auto")
        fig_kat.update_layout(height=420, showlegend=False,
                              yaxis={"categoryorder":"total ascending"})
        c1.plotly_chart(fig_kat, use_container_width=True)

        jam_data = df_f.groupby("jam")["order_id"].count().reset_index()
        jam_data.columns = ["jam","jumlah"]
        top3 = jam_data.nlargest(3,"jumlah")["jam"].tolist()
        jam_data["warna"] = jam_data["jam"].apply(
            lambda j: "🔴 Tersibuk" if j in top3 else "🔵 Normal"
        )
        fig_jam = px.bar(
            jam_data, x="jam", y="jumlah", color="warna",
            title="Distribusi Order per Jam",
            color_discrete_map={"🔴 Tersibuk":"#E74C3C","🔵 Normal":"#3498DB"},
            labels={"jam":"Jam","jumlah":"Jumlah Order"}
        )
        fig_jam.update_layout(height=420, xaxis=dict(tickmode="linear",dtick=1))
        c2.plotly_chart(fig_jam, use_container_width=True)

        if "sesi_waktu" in df_f.columns:
            sesi = (df_f.groupby("sesi_waktu")["order_id"]
                    .count().reset_index()
                    .sort_values("order_id",ascending=False))
            sesi.columns = ["sesi_waktu","jumlah"]
            fig_sesi = px.pie(sesi, values="jumlah", names="sesi_waktu",
                              title="Distribusi Order per Sesi Waktu",
                              color_discrete_sequence=px.colors.sequential.Plasma_r,
                              hole=0.4)
            fig_sesi.update_traces(textinfo="label+percent+value")
            fig_sesi.update_layout(height=380)
            st.plotly_chart(fig_sesi, use_container_width=True)

    st.markdown("---")
    st.caption(
        "📊 Sistem Big Data UMKMS Indonesia | "
        "MySQL (XAMPP) + MongoDB (Compass) + Apache Spark | "
        "Dashboard: Streamlit + Plotly"
    )


if __name__ == "__main__":
    main()