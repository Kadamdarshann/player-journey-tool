import streamlit as st
import pandas as pd
import os
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import base64
from io import BytesIO

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Player Journey Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; background:#0a0d14; color:#c9d1e0; }
.stApp { background:#0a0d14; }
h1,h2,h3 { font-family:'Share Tech Mono',monospace; color:#00e5ff; }
.metric-card {
    background: linear-gradient(135deg,#0d1a2a,#0a1520);
    border:1px solid rgba(0,229,255,0.2);
    border-radius:8px; padding:16px 20px;
    text-align:center; margin-bottom:8px;
}
.metric-card .val { font-family:'Share Tech Mono',monospace; font-size:1.9rem; color:#00e5ff; line-height:1; }
.metric-card .lbl { font-size:0.8rem; color:#7a8fa6; text-transform:uppercase; letter-spacing:1px; margin-top:4px; }
div[data-testid="stSidebar"] { background:#080b12; border-right:1px solid rgba(0,229,255,0.13); }
div[data-testid="stSidebar"] label { color:#c9d1e0 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CONSTANTS  — only valid 6-digit hex or rgba() strings
# ─────────────────────────────────────────────────────────────
EVENT_COLOR = {
    "Kill":          "#ff4d4d",
    "Killed":        "#ff6b6b",
    "Loot":          "#ffd700",
    "Position":      "#4db8ff",
    "BotPosition":   "#00e676",
    "BotKill":       "#ff9100",
    "BotKilled":     "#ce93d8",
    "KilledByStorm": "#b0bec5",
}
DEFAULT_COLOR = "#607d8b"

EVENT_SYMBOL = {
    "Kill":          "star",
    "Killed":        "x",
    "Loot":          "diamond",
    "Position":      "circle",
    "BotPosition":   "circle-open",
    "BotKill":       "triangle-up",
    "BotKilled":     "triangle-down",
    "KilledByStorm": "square",
}
DEFAULT_SYMBOL = "circle"

MAP_IMAGES = {
    "AmbroseValley": "AmbroseValley_Minimap.png",
    "GrandRift":     "GrandRift_Minimap.png",
    "Lockdown":      "Lockdown_Minimap.jpg",
}

DEATH_EVENTS = ["Killed", "BotKilled", "KilledByStorm"]
KILL_EVENTS  = ["Kill", "BotKill"]


# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
@st.cache_data
def load_all_data():
    base_path = "data/player_data"
    if not os.path.exists(base_path):
        st.error(f"Data directory not found: `{base_path}`")
        st.stop()

    frames = []
    for root, _, files in os.walk(base_path):
        for f in files:
            if f.endswith(".nakama-0"):
                try:
                    frames.append(pd.read_parquet(os.path.join(root, f), engine="pyarrow"))
                except Exception as e:
                    st.warning(f"Skipped {f}: {e}")

    if not frames:
        st.error("No .nakama-0 parquet files found.")
        st.stop()

    df = pd.concat(frames, ignore_index=True)

    # Decode all bytes columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda v: v.decode("utf-8") if isinstance(v, bytes) else v)

    df["ts"]   = pd.to_datetime(df["ts"], unit="s", errors="coerce")
    df         = df.dropna(subset=["ts"])
    df["date"] = df["ts"].dt.date

    for col in ["x", "z"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["x", "z"])

    df["player_type"] = df["event"].apply(lambda v: "Bot" if "Bot" in str(v) else "Human")
    return df.reset_index(drop=True)


df = load_all_data()


# ─────────────────────────────────────────────────────────────
# PER-MAP COORDINATE BOUNDS  (auto-fit from data)
# ─────────────────────────────────────────────────────────────
@st.cache_data
def build_bounds(data: pd.DataFrame) -> dict:
    out = {}
    for mid, g in data.groupby("map_id"):
        px_ = max((g["x"].max() - g["x"].min()) * 0.03, 1.0)
        pz_ = max((g["z"].max() - g["z"].min()) * 0.03, 1.0)
        out[mid] = dict(
            x_min=float(g["x"].min() - px_), x_max=float(g["x"].max() + px_),
            z_min=float(g["z"].min() - pz_), z_max=float(g["z"].max() + pz_),
        )
    return out

MAP_BOUNDS = build_bounds(df)


def get_bounds(map_id: str) -> dict:
    return MAP_BOUNDS.get(map_id, dict(x_min=0, x_max=1000, z_min=0, z_max=1000))


def load_minimap_b64(map_id: str):
    img_name = MAP_IMAGES.get(map_id, "")
    path = os.path.join("data", "player_data", "minimaps", img_name)
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────────────────────
# SIDEBAR  FILTERS
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎮 Filters")

    # 1. Map
    map_list  = sorted(df["map_id"].unique())
    map_sel   = st.selectbox("Map", map_list)
    map_df    = df[df["map_id"] == map_sel].copy()

    # 2. Date
    date_opts = ["All"] + [str(d) for d in sorted(map_df["date"].unique())]
    date_sel  = st.selectbox("Date", date_opts)
    if date_sel != "All":
        map_df = map_df[map_df["date"] == pd.to_datetime(date_sel).date()]

    # 3. Match
    match_opts = sorted(map_df["match_id"].unique())
    if not match_opts:
        st.warning("No matches for this date.")
        st.stop()
    match_sel = st.selectbox("Match", match_opts)
    match_df  = map_df[map_df["match_id"] == match_sel].copy()

    st.markdown("---")
    st.markdown("### Visibility")
    show_map   = st.checkbox("Minimap Background", True)
    show_human = st.checkbox("Show Humans", True)
    show_bot   = st.checkbox("Show Bots", True)
    show_paths = st.checkbox("Movement Paths", True)

    st.markdown("---")
    st.markdown("### Heatmap")
    show_heatmap  = st.checkbox("Enable Heatmap", False)
    heatmap_layer = st.radio(
        "Layer",
        ["All Traffic", "Kill Zones", "Death Zones", "Loot Zones"],
        disabled=not show_heatmap,
    )

    st.markdown("---")
    st.markdown("### Player Focus")
    player_opts = ["All"] + sorted(match_df["user_id"].unique().tolist())
    player_sel  = st.selectbox("Highlight Player", player_opts)


# ─────────────────────────────────────────────────────────────
# VISIBILITY FILTERS
# ─────────────────────────────────────────────────────────────
if not show_human:
    match_df = match_df[match_df["player_type"] != "Human"]
if not show_bot:
    match_df = match_df[match_df["player_type"] != "Bot"]

if match_df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

match_df = match_df.sort_values("ts").reset_index(drop=True)
ts_min   = match_df["ts"].min()


# ─────────────────────────────────────────────────────────────
# TIMELINE SLIDER
# ─────────────────────────────────────────────────────────────
total_events = len(match_df)
sl_col, ti_col = st.columns([5, 1])
with sl_col:
    idx = st.slider("Timeline — drag to replay match", 0, total_events - 1, total_events - 1)
with ti_col:
    elapsed = (match_df.iloc[idx]["ts"] - ts_min).total_seconds()
    st.markdown(
        f"<div style='padding-top:26px;font-family:monospace;color:#00e5ff;font-size:0.85rem'>"
        f"T+{elapsed:.0f}s</div>",
        unsafe_allow_html=True,
    )

view_df = match_df.iloc[: idx + 1].copy()


# ─────────────────────────────────────────────────────────────
# HEADER + METRICS
# ─────────────────────────────────────────────────────────────
st.markdown("# Player Journey Analytics")
st.markdown(f"**Map:** `{map_sel}` &nbsp;|&nbsp; **Match:** `{match_sel}`")

kills_n  = int(view_df["event"].isin(KILL_EVENTS).sum())
deaths_n = int(view_df["event"].isin(DEATH_EVENTS).sum())
loots_n  = int((view_df["event"] == "Loot").sum())
kd_ratio = f"{kills_n/deaths_n:.2f}" if deaths_n > 0 else "inf"
players_n = view_df["user_id"].nunique()

mc = st.columns(5)
for col, val, label in zip(mc,
    [players_n, kills_n, deaths_n, loots_n, kd_ratio],
    ["Players",  "Kills",  "Deaths",  "Loot",  "K/D"]):
    col.markdown(
        f'<div class="metric-card">'
        f'<div class="val">{val}</div>'
        f'<div class="lbl">{label}</div></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
# SHARED MAP DATA  — bounds from current match, not global data
# ─────────────────────────────────────────────────────────────
def match_bounds(data: pd.DataFrame) -> dict:
    """Tight bounds from the current match with a small % padding."""
    x_range = data["x"].max() - data["x"].min()
    z_range = data["z"].max() - data["z"].min()
    pad_x = max(x_range * 0.05, 10)
    pad_z = max(z_range * 0.05, 10)
    return dict(
        x_min=float(data["x"].min() - pad_x),
        x_max=float(data["x"].max() + pad_x),
        z_min=float(data["z"].min() - pad_z),
        z_max=float(data["z"].max() + pad_z),
    )

b = match_bounds(match_df)
x_min, x_max = b["x_min"], b["x_max"]
z_min, z_max = b["z_min"], b["z_max"]

minimap_b64 = load_minimap_b64(map_sel) if show_map else None


def attach_minimap(fig, opacity=0.35):
    if minimap_b64:
        fig.add_layout_image(dict(
            source=minimap_b64,
            xref="x", yref="y",        # pinned to data coordinate space
            x=x_min,   y=z_max,        # top-left in data coords
            sizex=x_max - x_min,
            sizey=z_max - z_min,
            sizing="stretch",
            opacity=opacity,
            layer="below",
        ))


def apply_base_layout(fig, height=700):
    fig.update_layout(
        height=height,
        paper_bgcolor="#0a0d14",
        plot_bgcolor="#0d1320",
        font=dict(color="#c9d1e0", family="Rajdhani"),
        xaxis=dict(range=[x_min, x_max], title="X", gridcolor="#1e2d40", zeroline=False),
        yaxis=dict(range=[z_min, z_max], title="Z", gridcolor="#1e2d40", zeroline=False),
        legend=dict(bgcolor="rgba(13,19,32,0.85)", bordercolor="rgba(0,229,255,0.25)",
                    borderwidth=1, font=dict(size=11)),
        margin=dict(l=0, r=0, t=10, b=0),
    )


def safe_color_map(events):
    """Return color_discrete_map that covers every event string in the list."""
    return {e: EVENT_COLOR.get(e, DEFAULT_COLOR) for e in events}


# ─────────────────────────────────────────────────────────────
# MAIN MAP  — full width
# ─────────────────────────────────────────────────────────────
st.markdown("### Movement Map")
fig = go.Figure()
attach_minimap(fig)

# Per-player movement paths
if show_paths:
    for uid, pgrp in view_df.groupby("user_id"):
        pos = pgrp[pgrp["event"].isin(["Position", "BotPosition"])].sort_values("ts")
        if len(pos) < 2:
            continue
        highlighted = (player_sel != "All" and uid == player_sel)
        dimmed      = (player_sel != "All" and uid != player_sel)
        lc = "rgb(0,229,255)" if highlighted else (
            "rgba(255,255,255,0.07)" if dimmed else "rgba(255,255,255,0.18)"
        )
        lw = 2.5 if highlighted else 1.0
        fig.add_trace(go.Scatter(
            x=pos["x"].tolist(), y=pos["z"].tolist(),
            mode="lines",
            line=dict(color=lc, width=lw),
            showlegend=False,
            hoverinfo="skip",
        ))

# One scatter trace per event type
for evt in sorted(view_df["event"].unique()):
    edf = view_df[view_df["event"] == evt]
    if player_sel != "All":
        opacity = 1.0 if (edf["user_id"] == player_sel).any() else 0.15
    else:
        opacity = 0.9

    fig.add_trace(go.Scatter(
        x=edf["x"].tolist(), y=edf["z"].tolist(),
        mode="markers",
        name=evt,
        opacity=opacity,
        marker=dict(
            size=7 if "Position" in evt else 14,
            color=EVENT_COLOR.get(evt, DEFAULT_COLOR),
            symbol=EVENT_SYMBOL.get(evt, DEFAULT_SYMBOL),
            line=dict(width=1, color="rgba(0,0,0,0.5)"),
        ),
        customdata=list(zip(edf["user_id"].tolist(),
                            edf["ts"].dt.strftime("%H:%M:%S").tolist())),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            f"Event: {evt}<br>"
            "X: %{x:.1f}  Z: %{y:.1f}<br>"
            "Time: %{customdata[1]}<extra></extra>"
        ),
    ))

apply_base_layout(fig, height=850)
st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# SIDE PANEL — now a 3-column row below the map
# ─────────────────────────────────────────────────────────────
leg_col, bar_col, pie_col = st.columns([1, 2, 2])

with leg_col:
    st.markdown("### Legend")
    legend_rows = [
        ("Position",     "#4db8ff", "●"),
        ("Loot",         "#ffd700", "◆"),
        ("Kill",         "#ff4d4d", "★"),
        ("Killed",       "#ff6b6b", "✖"),
        ("BotPosition",  "#00e676", "○"),
        ("BotKill",      "#ff9100", "▲"),
        ("BotKilled",    "#ce93d8", "▼"),
        ("Storm Death",  "#b0bec5", "■"),
    ]
    html = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:0.88rem">'
        f'<span style="color:{c};font-size:1.1rem">{s}</span><span>{n}</span></div>'
        for n, c, s in legend_rows
    )
    st.markdown(html, unsafe_allow_html=True)
    st.markdown("**●** Human &nbsp;&nbsp; **✖** Bot")

    if player_sel != "All":
        pdata = view_df[view_df["user_id"] == player_sel]
        pk  = int(pdata["event"].isin(KILL_EVENTS).sum())
        pd_ = int(pdata["event"].isin(DEATH_EVENTS).sum())
        st.markdown(f"---\n### {player_sel[:12]}")
        st.markdown(f"""
| Stat | Value |
|------|-------|
| Events | {len(pdata)} |
| Kills | {pk} |
| Deaths | {pd_} |
| K/D | {"inf" if pd_ == 0 else f"{pk/pd_:.2f}"} |
| Loot | {int((pdata["event"] == "Loot").sum())} |
""")

with bar_col:
    st.markdown("### Event Breakdown")
    ev_df = view_df["event"].value_counts().reset_index()
    ev_df.columns = ["event", "count"]
    fig_bar = px.bar(
        ev_df.sort_values("count"),
        x="count", y="event", orientation="h",
        color="event",
        color_discrete_map=safe_color_map(ev_df["event"].tolist()),
        template="plotly_dark",
    )
    fig_bar.update_layout(
        height=320, showlegend=False,
        margin=dict(l=0, r=0, t=5, b=0),
        paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
        xaxis=dict(gridcolor="#1e2d40"), yaxis_title="",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with pie_col:
    st.markdown("### Event Share")
    fig_pie = px.pie(
        ev_df, values="count", names="event",
        color="event",
        color_discrete_map=safe_color_map(ev_df["event"].tolist()),
        hole=0.4, template="plotly_dark",
    )
    fig_pie.update_layout(
        height=320, showlegend=True,
        margin=dict(l=0, r=0, t=5, b=0),
        paper_bgcolor="#0a0d14",
        legend=dict(bgcolor="rgba(13,19,32,0.85)", font=dict(size=11)),
    )
    st.plotly_chart(fig_pie, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# HEATMAP
# ─────────────────────────────────────────────────────────────
if show_heatmap:
    st.markdown("---")
    st.markdown(f"### Heatmap — {heatmap_layer}")

    layer_events = {
        "All Traffic": None,
        "Kill Zones":  KILL_EVENTS,
        "Death Zones": DEATH_EVENTS,
        "Loot Zones":  ["Loot"],
    }
    ef = layer_events[heatmap_layer]
    heat_df = view_df if ef is None else view_df[view_df["event"].isin(ef)]

    if heat_df.empty:
        st.info("No events for this heatmap layer.")
    else:
        hc1, hc2 = st.columns([3, 1])
        with hc1:
            fig_h = px.density_heatmap(
                heat_df, x="x", y="z",
                nbinsx=50, nbinsy=50,
                color_continuous_scale="hot",
                template="plotly_dark",
            )
            attach_minimap(fig_h, opacity=0.12)
            fig_h.update_layout(
                height=750, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(range=[x_min, x_max], gridcolor="#1e2d40"),
                yaxis=dict(range=[z_min, z_max], gridcolor="#1e2d40"),
            )
            st.plotly_chart(fig_h, use_container_width=True)

        with hc2:
            st.markdown(f"**{heatmap_layer}**")
            st.markdown(f"Events: **{len(heat_df)}**")
            try:
                hot = heat_df.groupby(
                    [pd.cut(heat_df["x"], 8), pd.cut(heat_df["z"], 8)]
                ).size().idxmax()
                st.markdown(f"Hotspot: `{hot}`")
            except Exception:
                pass

            lyr_c = heat_df["event"].value_counts().reset_index()
            lyr_c.columns = ["event", "count"]
            fig_lc = px.bar(
                lyr_c, x="event", y="count",
                color="event",
                color_discrete_map=safe_color_map(lyr_c["event"].tolist()),
                template="plotly_dark",
            )
            fig_lc.update_layout(
                height=220, showlegend=False,
                margin=dict(l=0, r=0, t=5, b=0),
                paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
                xaxis_title="", yaxis_title="",
            )
            st.plotly_chart(fig_lc, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# INSIGHTS TABS
# ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## Match Insights")

tab1, tab2, tab3, tab4 = st.tabs([
    "Player Leaderboard",
    "Kill Timeline",
    "Zone Analysis",
    "Human vs Bot",
])

# ── Tab 1: Leaderboard ──────────────────────────────────────
with tab1:
    rows = []
    for uid, grp in view_df.groupby("user_id"):
        k  = int(grp["event"].isin(KILL_EVENTS).sum())
        d  = int(grp["event"].isin(DEATH_EVENTS).sum())
        lo = int((grp["event"] == "Loot").sum())
        pt = grp["player_type"].iloc[0]
        rows.append(dict(player=uid, kills=k, deaths=d,
                         kd=round(k / d, 2) if d > 0 else float(k),
                         loot=lo, type=pt))
    lb = pd.DataFrame(rows).sort_values("kills", ascending=False)

    lc1, lc2 = st.columns([2, 1])
    with lc1:
        fig_lb = px.bar(
            lb.head(20), x="player", y=["kills", "deaths"],
            barmode="group",
            color_discrete_map={"kills": "#ff4d4d", "deaths": "#4db8ff"},
            template="plotly_dark",
            title="Kills vs Deaths (top 20 players)",
        )
        fig_lb.update_layout(
            height=360, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(gridcolor="#1e2d40", tickangle=-45),
            yaxis=dict(gridcolor="#1e2d40"),
            legend=dict(bgcolor="rgba(13,19,32,0.85)"),
        )
        st.plotly_chart(fig_lb, use_container_width=True)
    with lc2:
        st.markdown("**Top 10 by K/D**")
        st.dataframe(
            lb[["player", "kills", "deaths", "kd", "loot", "type"]]
              .head(10)
              .rename(columns={"player": "Player", "kills": "K", "deaths": "D",
                               "kd": "K/D", "loot": "Loot", "type": "Type"}),
            use_container_width=True, hide_index=True,
        )

# ── Tab 2: Kill Timeline + Survival ─────────────────────────
with tab2:
    kill_ts = view_df[view_df["event"].isin(KILL_EVENTS)].copy()
    if kill_ts.empty:
        st.info("No kill events in current view.")
    else:
        kill_ts["elapsed_min"] = ((kill_ts["ts"] - ts_min).dt.total_seconds() / 60).round(1)

        fig_tl = px.histogram(
            kill_ts, x="elapsed_min", color="event",
            nbins=30,
            color_discrete_map=safe_color_map(kill_ts["event"].unique().tolist()),
            template="plotly_dark",
            title="Kill frequency over match time",
            labels={"elapsed_min": "Minutes into match"},
        )
        fig_tl.update_layout(
            height=340, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(gridcolor="#1e2d40"),
            yaxis=dict(gridcolor="#1e2d40"),
            legend=dict(bgcolor="rgba(13,19,32,0.85)"),
            bargap=0.05,
        )
        st.plotly_chart(fig_tl, use_container_width=True)

    # Survival times
    surv = []
    for uid, g in view_df.groupby("user_id"):
        deaths_g = g[g["event"].isin(DEATH_EVENTS)]
        ft = (deaths_g["ts"].min() - ts_min).total_seconds() / 60 if not deaths_g.empty \
             else (view_df["ts"].max() - ts_min).total_seconds() / 60
        surv.append(dict(player=uid, survived_min=round(ft, 1),
                         type=g["player_type"].iloc[0]))
    surv_df = pd.DataFrame(surv).sort_values("survived_min", ascending=False)

    fig_surv = px.bar(
        surv_df.head(20), x="player", y="survived_min",
        color="type",
        color_discrete_map={"Human": "#4db8ff", "Bot": "#00e676"},
        template="plotly_dark",
        title="Survival time per player (top 20)",
        labels={"survived_min": "Minutes survived", "player": ""},
    )
    fig_surv.update_layout(
        height=320, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(gridcolor="#1e2d40", tickangle=-45),
        yaxis=dict(gridcolor="#1e2d40"),
        legend=dict(bgcolor="rgba(13,19,32,0.85)"),
    )
    st.plotly_chart(fig_surv, use_container_width=True)

# ── Tab 3: Zone Analysis ─────────────────────────────────────
with tab3:
    zc1, zc2 = st.columns(2)
    with zc1:
        loot_df = view_df[view_df["event"] == "Loot"]
        if not loot_df.empty:
            fig_lz = px.density_heatmap(
                loot_df, x="x", y="z", nbinsx=30, nbinsy=30,
                color_continuous_scale="YlOrBr",
                template="plotly_dark", title="Loot Density",
            )
            attach_minimap(fig_lz, opacity=0.1)
            fig_lz.update_layout(
                height=600, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis=dict(range=[x_min, x_max], gridcolor="#1e2d40"),
                yaxis=dict(range=[z_min, z_max], gridcolor="#1e2d40"),
            )
            st.plotly_chart(fig_lz, use_container_width=True)
        else:
            st.info("No loot events.")

    with zc2:
        kill_df = view_df[view_df["event"].isin(KILL_EVENTS)]
        if not kill_df.empty:
            fig_kz = px.density_heatmap(
                kill_df, x="x", y="z", nbinsx=30, nbinsy=30,
                color_continuous_scale="Reds",
                template="plotly_dark", title="Kill Density",
            )
            attach_minimap(fig_kz, opacity=0.1)
            fig_kz.update_layout(
                height=600, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis=dict(range=[x_min, x_max], gridcolor="#1e2d40"),
                yaxis=dict(range=[z_min, z_max], gridcolor="#1e2d40"),
            )
            st.plotly_chart(fig_kz, use_container_width=True)
        else:
            st.info("No kill events.")

# ── Tab 4: Human vs Bot ──────────────────────────────────────
with tab4:
    hb = view_df.groupby(["player_type", "event"]).size().reset_index(name="count")

    tc1, tc2 = st.columns(2)
    with tc1:
        fig_hb = px.bar(
            hb, x="event", y="count", color="player_type",
            barmode="group",
            color_discrete_map={"Human": "#4db8ff", "Bot": "#00e676"},
            template="plotly_dark",
            title="Event counts — Human vs Bot",
        )
        fig_hb.update_layout(
            height=380, paper_bgcolor="#0a0d14", plot_bgcolor="#0d1320",
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(gridcolor="#1e2d40", tickangle=-30),
            yaxis=dict(gridcolor="#1e2d40"),
            legend=dict(bgcolor="rgba(13,19,32,0.85)"),
        )
        st.plotly_chart(fig_hb, use_container_width=True)

    with tc2:
        type_summary = view_df.groupby("player_type").agg(
            Players=("user_id", "nunique"),
            Kills=("event", lambda s: s.isin(KILL_EVENTS).sum()),
            Deaths=("event", lambda s: s.isin(DEATH_EVENTS).sum()),
            Loot=("event", lambda s: (s == "Loot").sum()),
            Events=("event", "count"),
        ).reset_index()
        type_summary["K/D"] = type_summary.apply(
            lambda r: "inf" if r.Deaths == 0 else f"{r.Kills/r.Deaths:.2f}", axis=1
        )
        st.markdown("**Summary Table**")
        st.dataframe(type_summary, use_container_width=True, hide_index=True)

        fig_tp = px.pie(
            view_df, names="player_type",
            color="player_type",
            color_discrete_map={"Human": "#4db8ff", "Bot": "#00e676"},
            hole=0.45, template="plotly_dark",
            title="Player type split",
        )
        fig_tp.update_layout(
            height=260, paper_bgcolor="#0a0d14",
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(bgcolor="rgba(13,19,32,0.85)"),
        )
        st.plotly_chart(fig_tp, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# RAW EVENT LOG
# ─────────────────────────────────────────────────────────────
with st.expander("Raw Event Log", expanded=False):
    show_cols = [c for c in ["ts", "user_id", "event", "x", "z", "player_type", "match_id"]
                 if c in view_df.columns]
    st.dataframe(
        view_df[show_cols].sort_values("ts", ascending=False).head(500),
        use_container_width=True, hide_index=True,
    )