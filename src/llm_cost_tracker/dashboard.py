from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from llm_cost_tracker.dashboard_queries import DashboardData, fetch_dashboard_data


st.set_page_config(page_title="LLM Cost Tracker", page_icon="💸", layout="wide")
st.title("LLM Cost Tracker")
st.caption("Monitoring biaya dan volume penggunaan LLM tanpa menyimpan isi percakapan.")


@st.cache_data(ttl=30, show_spinner=False)
def load_data(
    database_url: str,
    start_date: date,
    end_date: date,
    provider: Optional[str],
) -> DashboardData:
    return asyncio.run(
        fetch_dashboard_data(database_url, start_date, end_date, provider)
    )


def normalize_range(value: object) -> Tuple[date, date]:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return value[0], value[1]
    if isinstance(value, date):
        return value, value
    today = date.today()
    return today - timedelta(days=29), today


database_url = os.getenv("DATABASE_URL")
if not database_url:
    st.error("DATABASE_URL belum dikonfigurasi. Isi variabel tersebut lalu muat ulang.")
    st.stop()

today = date.today()
selected_range = st.sidebar.date_input(
    "Rentang tanggal",
    value=(today - timedelta(days=29), today),
    max_value=today,
)
start_date, end_date = normalize_range(selected_range)

try:
    initial_data = load_data(database_url, start_date, end_date, None)
except Exception as exc:
    st.error("Dashboard tidak dapat membaca Postgres. Pastikan database dan migrasi aktif.")
    st.caption(f"Detail teknis: {type(exc).__name__}")
    st.stop()

provider_options = ["Semua provider"] + initial_data.providers
selected_provider = st.sidebar.selectbox("Provider", provider_options)
provider = None if selected_provider == "Semua provider" else selected_provider
data = (
    initial_data
    if provider is None
    else load_data(database_url, start_date, end_date, provider)
)

summary = data.summary
request_count = int(summary.get("request_count", 0))
total_cost = Decimal(summary.get("total_cost_usd", 0))
total_tokens = int(summary.get("total_tokens", 0))
unpriced_count = int(summary.get("unpriced_request_count", 0))

cost_col, requests_col, tokens_col, coverage_col = st.columns(4)
cost_col.metric("Estimasi biaya", f"${total_cost:,.4f}")
requests_col.metric("Request", f"{request_count:,}")
tokens_col.metric("Token", f"{total_tokens:,}")
priced_percentage = (
    ((request_count - unpriced_count) / request_count) * 100 if request_count else 0
)
coverage_col.metric("Cakupan harga", f"{priced_percentage:.1f}%")

st.subheader("Biaya harian")
if not data.daily_costs:
    st.info("Belum ada data pada rentang dan provider yang dipilih.")
else:
    chart_data = pd.DataFrame(data.daily_costs)
    chart_data["cost_usd"] = chart_data["cost_usd"].astype(float)
    st.line_chart(
        chart_data,
        x="day",
        y="cost_usd",
        color="provider",
        x_label="Tanggal",
        y_label="Biaya (USD)",
        use_container_width=True,
    )
    with st.expander("Lihat data agregat"):
        display_data = chart_data.rename(
            columns={
                "day": "Tanggal",
                "provider": "Provider",
                "cost_usd": "Biaya (USD)",
                "request_count": "Request",
            }
        )
        st.dataframe(display_data, use_container_width=True, hide_index=True)

if unpriced_count:
    st.warning(
        f"{unpriced_count:,} request belum memiliki harga model dan tidak masuk total biaya."
    )

st.caption("Data diperbarui maksimal setiap 30 detik.")
