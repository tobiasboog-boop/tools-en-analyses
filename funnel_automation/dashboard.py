"""Streamlit Dashboard voor Lead Scoring."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import glob
import os

# Page config
st.set_page_config(
    page_title="Lead Scoring Dashboard",
    page_icon="🎯",
    layout="wide"
)

# Title
st.title("🎯 Lead Scoring Dashboard")
st.markdown("---")

# Load latest CSV
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_latest_data():
    """Load most recent lead scoring CSV."""
    csv_files = glob.glob("c:/projects/tools_en_analyses/funnel_automation/leads_*.csv")

    if not csv_files:
        return None

    # Get most recent file
    latest_file = max(csv_files, key=os.path.getctime)

    # Load data
    df = pd.read_csv(latest_file)

    # Parse datetime if exists
    file_time = datetime.fromtimestamp(os.path.getctime(latest_file))

    return df, latest_file, file_time

data = load_latest_data()

if data is None:
    st.error("❌ No lead scoring data found!")
    st.info("Run: `python score_leads_complete.py` first")
    st.stop()

df, filename, file_time = data

# Header with refresh button
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.metric("Total Leads", len(df))
with col2:
    st.metric("Data Updated", file_time.strftime("%Y-%m-%d %H:%M"))
with col3:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# Segment statistics
col1, col2, col3 = st.columns(3)

warm_count = len(df[df['Segment'] == 'Warm'])
lauw_count = len(df[df['Segment'] == 'Lauw'])
koud_count = len(df[df['Segment'] == 'Koud'])

with col1:
    st.metric(
        "🔥 Warme Leads",
        warm_count,
        f"{warm_count/len(df)*100:.1f}%"
    )

with col2:
    st.metric(
        "🟡 Lauwe Leads",
        lauw_count,
        f"{lauw_count/len(df)*100:.1f}%"
    )

with col3:
    st.metric(
        "🧊 Koude Leads",
        koud_count,
        f"{koud_count/len(df)*100:.1f}%"
    )

st.markdown("---")

# Visualizations
col1, col2 = st.columns(2)

with col1:
    st.subheader("Lead Segmentatie")

    # Pie chart
    segment_counts = df['Segment'].value_counts()
    fig = px.pie(
        values=segment_counts.values,
        names=segment_counts.index,
        color=segment_counts.index,
        color_discrete_map={
            'Warm': '#FF6B6B',
            'Lauw': '#FFD93D',
            'Koud': '#6BCFFF'
        }
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Score Distributie")

    # Histogram
    fig = px.histogram(
        df,
        x='Total Score',
        nbins=20,
        color='Segment',
        color_discrete_map={
            'Warm': '#FF6B6B',
            'Lauw': '#FFD93D',
            'Koud': '#6BCFFF'
        }
    )
    fig.update_layout(bargap=0.1)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Filters
st.subheader("🔍 Filter Leads")

col1, col2, col3 = st.columns(3)

with col1:
    segment_filter = st.multiselect(
        "Segment",
        options=['Warm', 'Lauw', 'Koud'],
        default=['Warm', 'Lauw', 'Koud']
    )

with col2:
    min_score = st.slider(
        "Min Score",
        min_value=0,
        max_value=100,
        value=0
    )

with col3:
    search_term = st.text_input("Zoek op naam/email")

# Apply filters
filtered_df = df[df['Segment'].isin(segment_filter)]
filtered_df = filtered_df[filtered_df['Total Score'] >= min_score]

if search_term:
    filtered_df = filtered_df[
        filtered_df['Name'].str.contains(search_term, case=False, na=False) |
        filtered_df['Email'].str.contains(search_term, case=False, na=False)
    ]

st.markdown(f"**Showing {len(filtered_df)} of {len(df)} leads**")

# Lead table
st.subheader("📊 Lead Overview")

# Format dataframe for display
display_df = filtered_df[[
    'Name', 'Email', 'Total Score', 'Segment',
    'CRM Score', 'Email Score', 'Company'
]].copy()

# Color code rows by segment
def color_segment(row):
    if row['Segment'] == 'Warm':
        return ['background-color: #FFE5E5'] * len(row)
    elif row['Segment'] == 'Lauw':
        return ['background-color: #FFF8E1'] * len(row)
    else:
        return ['background-color: #E3F2FD'] * len(row)

styled_df = display_df.style.apply(color_segment, axis=1)

st.dataframe(
    styled_df,
    use_container_width=True,
    height=600
)

# Download button
csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 Download Filtered Data (CSV)",
    data=csv,
    file_name=f"filtered_leads_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

st.markdown("---")

# Score breakdown for top leads
st.subheader("🏆 Top 10 Leads - Score Breakdown")

top_10 = filtered_df.nlargest(10, 'Total Score')

fig = go.Figure()

fig.add_trace(go.Bar(
    name='CRM Score',
    y=top_10['Name'],
    x=top_10['CRM Score'],
    orientation='h',
    marker_color='#4ECDC4'
))

fig.add_trace(go.Bar(
    name='Email Score',
    y=top_10['Name'],
    x=top_10['Email Score'],
    orientation='h',
    marker_color='#FFD93D'
))

fig.update_layout(
    barmode='stack',
    height=400,
    xaxis_title="Score",
    yaxis_title="",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.caption(f"Last updated: {file_time.strftime('%Y-%m-%d %H:%M:%S')} | Data source: {os.path.basename(filename)}")
