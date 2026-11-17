from pathlib import Path
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pycountry
import streamlit as st

# ------------------------------------------------------------
# Netflix Content Library Dashboard
# Run with: streamlit run app.py
# ------------------------------------------------------------

st.set_page_config(
    page_title="Netflix | Content Intelligence",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path(__file__).parent / "netflix_titles(1).csv"

RED = "#E50914"
BG = "#09090B"
PANEL = "#151519"
TEXT = "#F5F5F5"
MUTED = "#A1A1AA"
GRID = "#303038"
ACCENT = "#B20710"

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; }}
      .stApp {{ background: radial-gradient(circle at 80% 0%, #241014 0%, {BG} 38%); color: {TEXT}; }}
      [data-testid="stSidebar"] {{ background: #111114; border-right: 1px solid #29292f; }}
      [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
      .block-container {{ padding-top: 1.6rem; padding-bottom: 2.2rem; max-width: 1600px; }}
      h1, h2, h3 {{ color: {TEXT} !important; letter-spacing: -0.035em; }}
      .eyebrow {{ color: {RED}; font-size: .76rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }}
      .hero-title {{ font-size: clamp(2rem, 4vw, 3.25rem); font-weight: 800; line-height: 1.05; margin: .2rem 0 .45rem; }}
      .hero-sub {{ color: {MUTED}; font-size: .98rem; margin-bottom: 1.1rem; }}
      .kpi {{ background: linear-gradient(145deg, #1b1b21, #111115); border: 1px solid #303038; border-radius: 16px; padding: 17px 19px; min-height: 112px; box-shadow: 0 8px 26px rgba(0,0,0,.16); }}
      .kpi-label {{ color: {MUTED}; font-size: .76rem; text-transform: uppercase; letter-spacing: .1em; font-weight: 700; }}
      .kpi-value {{ color: {TEXT}; font-size: 1.85rem; font-weight: 800; margin-top: 7px; line-height: 1.15; }}
      .kpi-accent {{ color: {RED}; }}
      .section-head {{ display:flex; align-items:center; gap:10px; margin: 1.25rem 0 .6rem; }}
      .section-dot {{ width:8px; height:8px; background:{RED}; border-radius:50%; display:inline-block; }}
      .section-title {{ font-size:1.05rem; font-weight:800; color:{TEXT}; }}
      .section-note {{ color:{MUTED}; font-size:.78rem; margin-left:auto; }}
      div[data-testid="stPlotlyChart"] {{ background:{PANEL}; border:1px solid #2b2b32; border-radius:16px; padding:7px; }}
      .footer {{ color:#71717A; font-size:.75rem; border-top:1px solid #29292f; padding-top:14px; margin-top:22px; }}
      .stSelectbox label, .stMultiSelect label, .stSlider label, .stDateInput label {{ color:#D4D4D8 !important; font-weight:600; }}
      .stMultiSelect [data-baseweb="tag"] {{ background:{ACCENT}; }}
      .stButton button {{ background:{RED}; color:white; border:0; border-radius:9px; font-weight:700; }}
      hr {{ border-color:#29292f; }}
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"show_id", "type", "title", "country", "release_year", "rating", "listed_in"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")
    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
    df["type"] = df["type"].fillna("Unknown")
    df["rating"] = df["rating"].fillna("Not Rated").astype(str)
    df["country"] = df["country"].fillna("")
    df["listed_in"] = df["listed_in"].fillna("")
    return df

if not DATA_FILE.exists():
    st.error(
        f"Dataset not found: {DATA_FILE.name}. Place the Netflix CSV file in the same folder as app.py."
    )
    st.stop()

try:
    raw = load_data(str(DATA_FILE))
except Exception as exc:
    st.error(f"Could not load the dataset: {exc}")
    st.stop()

# Sidebar filters
st.sidebar.markdown(f"<div class='eyebrow'>Explore the catalogue</div>", unsafe_allow_html=True)
st.sidebar.title("Dashboard filters")
st.sidebar.caption("All charts and KPI cards respond to these selections.")

types = sorted(raw["type"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect("Content type", types, default=types)

years = raw["release_year"].dropna()
min_year, max_year = int(years.min()), int(years.max())
year_range = st.sidebar.slider(
    "Release year",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)

ratings = sorted(raw["rating"].dropna().unique().tolist())
selected_ratings = st.sidebar.multiselect("Content rating", ratings, default=ratings)

all_genres = sorted({
    g.strip()
    for cell in raw["listed_in"].dropna()
    for g in str(cell).split(",")
    if g.strip()
})
selected_genres = st.sidebar.multiselect("Genre", all_genres, default=[],
                                           help="Leave empty to include every genre.")

filtered = raw[
    raw["type"].isin(selected_types)
    & raw["release_year"].between(year_range[0], year_range[1], inclusive="both")
    & raw["rating"].isin(selected_ratings)
].copy()

if selected_genres:
    pattern = "|".join(re.escape(g) for g in selected_genres)
    filtered = filtered[filtered["listed_in"].str.contains(pattern, case=False, na=False)]

st.sidebar.markdown("---")
if st.sidebar.button("Reset filters", use_container_width=True):
    st.rerun()
st.sidebar.caption(f"Showing **{len(filtered):,}** of **{len(raw):,}** titles.")

# Helpers
def split_values(series):
    values = []
    for cell in series.fillna(""):
        values.extend([x.strip() for x in str(cell).split(",") if x.strip()])
    return values

def unique_count(values):
    return len(set(v for v in values if v and str(v).strip()))

def iso3(country):
    aliases = {
        "United States": "USA",
        "United States of America": "USA",
        "United Kingdom": "GBR",
        "South Korea": "KOR",
        "North Korea": "PRK",
        "Russia": "RUS",
        "Soviet Union": "RUS",
        "Czech Republic": "CZE",
        "Czechia": "CZE",
        "Taiwan": "TWN",
        "Hong Kong": "HKG",
        "Iran": "IRN",
        "Venezuela": "VEN",
        "Syria": "SYR",
        "Vietnam": "VNM",
        "Bolivia": "BOL",
        "Tanzania": "TZA",
        "Moldova": "MDA",
        "Palestine": "PSE",
        "West Germany": "DEU",
        "East Germany": "DEU",
    }
    if country in aliases:
        return aliases[country]
    try:
        return pycountry.countries.lookup(country).alpha_3
    except LookupError:
        return None

def plot_layout(fig, height=340, showlegend=False):
    fig.update_layout(
        height=height,
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family="DM Sans, sans-serif", color=TEXT, size=11),
        margin=dict(l=18, r=18, t=48, b=18),
        title=dict(font=dict(size=15, color=TEXT), x=0.03, y=0.97),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(color="#D4D4D8", size=10)
        ),
        showlegend=showlegend,
        hoverlabel=dict(bgcolor="#202027", font_color=TEXT),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(color=MUTED), title_font=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     tickfont=dict(color=MUTED), title_font=dict(color=MUTED))
    return fig

def section(label, note=""):
    st.markdown(
        f"<div class='section-head'><span class='section-dot'></span>"
        f"<span class='section-title'>{label}</span>"
        f"<span class='section-note'>{note}</span></div>",
        unsafe_allow_html=True,
    )

# Header
st.markdown("<div class='eyebrow'>Streaming intelligence · Netflix dataset</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>NETFLIX <span style='color:#E50914'>CONTENT</span> OVERVIEW</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='hero-sub'>A data-led view of Netflix's catalogue, content mix, genre distribution and global reach.</div>",
    unsafe_allow_html=True,
)

# KPI metrics
title_count = filtered["show_id"].nunique()
genre_values = split_values(filtered["listed_in"])
country_values = split_values(filtered["country"])
rating_count = unique_count(filtered["rating"].tolist())
year_min = int(filtered["release_year"].min()) if filtered["release_year"].notna().any() else "—"
year_max = int(filtered["release_year"].max()) if filtered["release_year"].notna().any() else "—"
kpis = [
    ("TOTAL TITLES", f"{title_count:,}", "Catalogue size"),
    ("UNIQUE RATINGS", f"{rating_count:,}", "Content classifications"),
    ("UNIQUE GENRES", f"{unique_count(genre_values):,}", "Genre categories"),
    ("FIRST RELEASE", str(year_min), "Earliest selected year"),
    ("LATEST RELEASE", str(year_max), "Latest selected year"),
    ("COUNTRIES", f"{unique_count(country_values):,}", "Country entries"),
]
cols = st.columns(6, gap="small")
for col, (label, value, sub) in zip(cols, kpis):
    col.markdown(
        f"<div class='kpi'><div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'><span class='kpi-accent'>{value}</span></div>"
        f"<div style='color:#777780;font-size:.72rem;margin-top:5px'>{sub}</div></div>",
        unsafe_allow_html=True,
    )

# Main chart row: map + donut
section("GLOBAL DISTRIBUTION", "Titles by country · content mix")
left, right = st.columns([1.55, 1], gap="medium")

with left:
    country_counts = pd.Series(country_values).value_counts().rename_axis("country").reset_index(name="titles")
    if not country_counts.empty:
        country_counts["iso3"] = country_counts["country"].apply(iso3)
        map_data = country_counts.dropna(subset=["iso3"])
        if not map_data.empty:
            fig_map = px.choropleth(
                map_data,
                locations="iso3",
                color="titles",
                hover_name="country",
                hover_data={"titles": True, "iso3": False},
                color_continuous_scale=[[0, "#3B1116"], [0.45, "#A30D18"], [1, "#FF3344"]],
                projection="natural earth",
                title="Movies & TV shows by country",
            )
            fig_map.update_geos(
                bgcolor=PANEL, showframe=False, showcoastlines=True,
                coastlinecolor="#45454D", showland=True, landcolor="#292930",
                showocean=True, oceancolor=PANEL, showcountries=True,
                countrycolor="#484850",
            )
            fig_map.update_layout(
                height=410, paper_bgcolor=PANEL, font=dict(color=TEXT),
                margin=dict(l=5, r=5, t=48, b=5),
                coloraxis_colorbar=dict(title=dict(text="Titles", font=dict(color=MUTED)),
                                        tickfont=dict(color=MUTED)),
                title=dict(font=dict(size=15), x=.03),
            )
            st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No country names in the filtered data could be matched to map locations.")
    else:
        st.info("No country data available for the current filters.")

with right:
    type_counts = filtered["type"].value_counts().rename_axis("type").reset_index(name="titles")
    if not type_counts.empty:
        fig_donut = px.pie(
            type_counts, names="type", values="titles", hole=.66,
            color="type", color_discrete_map={"Movie": RED, "TV Show": "#777780"},
            title="Movies vs TV shows",
        )
        fig_donut.update_traces(
            textposition="inside", textinfo="percent+label",
            marker=dict(line=dict(color=PANEL, width=4)),
            hovertemplate="%{label}<br>%{value:,} titles<br>%{percent}<extra></extra>",
        )
        fig_donut.add_annotation(
            text=f"<b>{title_count:,}</b><br><span style='font-size:11px'>TITLES</span>",
            x=.5, y=.5, showarrow=False, font=dict(size=22, color=TEXT),
        )
        st.plotly_chart(plot_layout(fig_donut, 410, True), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.info("No content type data for the current filters.")

# Top 10 genre + rating
section("CATALOGUE BREAKDOWN", "Most common categories and maturity ratings")
c1, c2 = st.columns(2, gap="medium")

with c1:
    genre_counts = pd.Series(genre_values).value_counts().head(10).sort_values()
    if not genre_counts.empty:
        gd = genre_counts.rename_axis("genre").reset_index(name="titles")
        fig_genre = px.bar(
            gd, x="titles", y="genre", orientation="h", text="titles",
            title="Top 10 genres",
            color="titles", color_continuous_scale=["#5C1018", RED],
        )
        fig_genre.update_traces(textposition="outside", cliponaxis=False,
                                hovertemplate="%{y}<br>%{x:,} titles<extra></extra>")
        fig_genre.update_layout(coloraxis_showscale=False)
        fig_genre.update_xaxes(title=None, showgrid=False, visible=False)
        fig_genre.update_yaxes(title=None, showgrid=False)
        st.plotly_chart(plot_layout(fig_genre, 390), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.info("No genre data for the current filters.")

with c2:
    rating_counts = filtered["rating"].value_counts().head(10).sort_values()
    if not rating_counts.empty:
        rd = rating_counts.rename_axis("rating").reset_index(name="titles")
        fig_rating = px.bar(
            rd, x="titles", y="rating", orientation="h", text="titles",
            title="Top 10 content ratings",
            color="titles", color_continuous_scale=["#5C1018", RED],
        )
        fig_rating.update_traces(textposition="outside", cliponaxis=False,
                                 hovertemplate="%{y}<br>%{x:,} titles<extra></extra>")
        fig_rating.update_layout(coloraxis_showscale=False)
        fig_rating.update_xaxes(title=None, showgrid=False, visible=False)
        fig_rating.update_yaxes(title=None, showgrid=False)
        st.plotly_chart(plot_layout(fig_rating, 390), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.info("No rating data for the current filters.")

# Release year area chart
section("RELEASE TRENDS", "Annual content releases by type")
yearly = (
    filtered.dropna(subset=["release_year"])
    .groupby(["release_year", "type"])
    .size().reset_index(name="titles")
)
if not yearly.empty:
    fig_area = px.area(
        yearly, x="release_year", y="titles", color="type",
        color_discrete_map={"Movie": RED, "TV Show": "#9A9AA3"},
        title="Movies and TV shows by release year",
        line_group="type",
    )
    fig_area.update_traces(hovertemplate="%{x:.0f}<br>%{fullData.name}: %{y:,}<extra></extra>")
    fig_area.update_xaxes(title="Release year", dtick=5, showgrid=False)
    fig_area.update_yaxes(title="Number of titles", rangemode="tozero")
    st.plotly_chart(plot_layout(fig_area, 380, True), use_container_width=True,
                    config={"displayModeBar": False})
else:
    st.info("No release-year data for the current filters.")

# Data table and download
with st.expander("View filtered dataset"):
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=320)
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data (CSV)",
        data=csv,
        file_name="netflix_filtered_data.csv",
        mime="text/csv",
    )

st.markdown(
    "<div class='footer'>NETFLIX CONTENT INTELLIGENCE · Built with Streamlit, Plotly and Python. "
    "Country totals count each title once for every country listed in its country field.</div>",
    unsafe_allow_html=True,
)
