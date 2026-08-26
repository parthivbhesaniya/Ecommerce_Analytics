from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Olist Commerce Pulse",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"


@st.cache_data(show_spinner="Loading commerce data...")
def load_data():
    orders = pd.read_csv(
        DATA_DIR / "orders.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    customers = pd.read_csv(DATA_DIR / "customers.csv", dtype={"customer_zip_code_prefix": str})
    payments = pd.read_csv(DATA_DIR / "order_payments.csv")
    items = pd.read_csv(DATA_DIR / "order_items.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    translations = pd.read_csv(DATA_DIR / "product_category_name_translation.csv")
    reviews = pd.read_csv(DATA_DIR / "order_reviews.csv")

    payments_by_order = payments.groupby("order_id", as_index=False).agg(
        revenue=("payment_value", "sum"),
        payment_type=("payment_type", lambda values: values.mode().iat[0]),
    )
    item_sales = items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    item_sales = item_sales.merge(translations, on="product_category_name", how="left")
    item_sales["category"] = item_sales["product_category_name_english"].fillna(
        item_sales["product_category_name"]
    ).fillna("unknown")
    item_sales["item_sales"] = item_sales["price"]
    item_sales["freight_pct"] = item_sales["freight_value"] / item_sales["price"].replace(0, pd.NA) * 100

    data = orders.merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
    data = data.merge(payments_by_order, on="order_id", how="left")
    data = data.merge(
        reviews.groupby("order_id", as_index=False).agg(review_score=("review_score", "mean")),
        on="order_id",
        how="left",
    )
    data["revenue"] = data["revenue"].fillna(0)
    data["purchase_date"] = data["order_purchase_timestamp"].dt.date
    data["month"] = data["order_purchase_timestamp"].dt.to_period("M").astype(str)
    data["delivery_status"] = "Unknown"
    delivered = data["order_delivered_customer_date"].notna() & data["order_estimated_delivery_date"].notna()
    data.loc[delivered, "delivery_status"] = "On time"
    data.loc[delivered & (data["order_delivered_customer_date"] > data["order_estimated_delivery_date"]), "delivery_status"] = "Delayed"
    return data, item_sales


def money(value):
    return f"R$ {value:,.0f}"


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; }
    [data-testid="stMetric"] { background: #f4f0e8; border-left: 4px solid #e56b4a; padding: 14px 16px; }
    [data-testid="stSidebar"] { background: #132a2f; }
    [data-testid="stSidebar"] * { color: #f6f1e8; }
    </style>
    """,
    unsafe_allow_html=True,
)


data, item_sales = load_data()

st.title("Olist Commerce Pulse")
st.caption("A practical view of sales momentum, customer experience, and operational pressure")

with st.sidebar:
    st.header("Explore the data")
    min_date = data["purchase_date"].min()
    max_date = data["purchase_date"].max()
    date_range = st.date_input("Purchase date", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    states = st.multiselect("Customer state", sorted(data["customer_state"].dropna().unique()))
    statuses = st.multiselect("Order status", sorted(data["order_status"].dropna().unique()), default=["delivered"])
    if st.button("Reset filters", use_container_width=True):
        st.rerun()

start_date, end_date = date_range if isinstance(date_range, tuple) else (date_range, date_range)
filtered = data[data["purchase_date"].between(start_date, end_date)].copy()
if states:
    filtered = filtered[filtered["customer_state"].isin(states)]
if statuses:
    filtered = filtered[filtered["order_status"].isin(statuses)]

filtered_ids = set(filtered["order_id"])
filtered_items = item_sales[item_sales["order_id"].isin(filtered_ids)].copy()

orders_count = filtered["order_id"].nunique()
revenue = filtered["revenue"].sum()
customers_count = filtered["customer_id"].nunique()
cancelled = (filtered["order_status"] == "canceled").sum()
avg_order_value = revenue / orders_count if orders_count else 0

metric_columns = st.columns(5)
metric_columns[0].metric("Revenue", money(revenue))
metric_columns[1].metric("Orders", f"{orders_count:,}")
metric_columns[2].metric("Average order value", money(avg_order_value))
metric_columns[3].metric("Customers", f"{customers_count:,}")
metric_columns[4].metric("Cancelled orders", f"{cancelled:,}")

if filtered.empty:
    st.warning("No orders match the selected filters.")
    st.stop()

sales_tab, customer_tab, operations_tab, payments_tab = st.tabs(["Sales", "Customers", "Operations", "Payments"])

with sales_tab:
    left, right = st.columns([1.35, 1])
    monthly = filtered.groupby("month", as_index=False).agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
    with left:
        st.subheader("Monthly revenue")
        st.plotly_chart(px.area(monthly, x="month", y="revenue", markers=True, labels={"revenue": "Revenue", "month": ""}, color_discrete_sequence=["#e56b4a"]), use_container_width=True)
    with right:
        st.subheader("Top categories")
        categories = filtered_items.groupby("category", as_index=False).agg(sales=("item_sales", "sum"), items=("order_id", "count"))
        categories = categories.nlargest(10, "sales").sort_values("sales")
        st.plotly_chart(px.bar(categories, x="sales", y="category", orientation="h", labels={"sales": "Item sales", "category": ""}, color_discrete_sequence=["#237c78"]), use_container_width=True)
    st.subheader("Revenue by customer state")
    state_revenue = filtered.groupby("customer_state", as_index=False).agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
    st.plotly_chart(px.bar(state_revenue.sort_values("revenue", ascending=False).head(15), x="customer_state", y="revenue", labels={"customer_state": "State", "revenue": "Revenue"}, color_discrete_sequence=["#f0a202"]), use_container_width=True)

with customer_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Customer order frequency")
        order_frequency = filtered.groupby("customer_id").size().rename("orders").reset_index()
        st.plotly_chart(px.histogram(order_frequency, x="orders", nbins=10, labels={"orders": "Orders per customer"}, color_discrete_sequence=["#237c78"]), use_container_width=True)
    with right:
        st.subheader("Review score distribution")
        scores = filtered.dropna(subset=["review_score"])
        st.plotly_chart(px.histogram(scores, x="review_score", nbins=5, labels={"review_score": "Score"}, color_discrete_sequence=["#e56b4a"]), use_container_width=True)
    repeat_rate = (order_frequency["orders"] > 1).mean() * 100
    st.metric("Repeat-customer rate", f"{repeat_rate:.1f}%")

with operations_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Delivery performance")
        delivery = filtered[filtered["delivery_status"] != "Unknown"]["delivery_status"].value_counts().rename_axis("status").reset_index(name="orders")
        st.plotly_chart(px.pie(delivery, names="status", values="orders", hole=0.55, color_discrete_sequence=["#237c78", "#e56b4a"]), use_container_width=True)
    with right:
        st.subheader("Freight burden by category")
        freight = filtered_items.groupby("category", as_index=False).agg(freight_pct=("freight_pct", "mean"))
        freight = freight.nlargest(12, "freight_pct").sort_values("freight_pct")
        st.plotly_chart(px.bar(freight, x="freight_pct", y="category", orientation="h", labels={"freight_pct": "Average freight % of item price", "category": ""}, color_discrete_sequence=["#f0a202"]), use_container_width=True)
    st.subheader("Review score: on-time vs delayed")
    review_by_delivery = filtered[filtered["delivery_status"].isin(["On time", "Delayed"])].groupby("delivery_status", as_index=False).agg(review_score=("review_score", "mean"))
    st.plotly_chart(px.bar(review_by_delivery, x="delivery_status", y="review_score", range_y=[0, 5], labels={"delivery_status": "", "review_score": "Average review score"}, color_discrete_sequence=["#237c78"]), use_container_width=True)

with payments_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by payment type")
        payment = filtered.groupby("payment_type", as_index=False).agg(revenue=("revenue", "sum"))
        st.plotly_chart(px.bar(payment.sort_values("revenue"), x="revenue", y="payment_type", orientation="h", labels={"payment_type": "", "revenue": "Revenue"}, color_discrete_sequence=["#237c78"]), use_container_width=True)
    with right:
        st.subheader("Orders by hour")
        hourly = filtered.assign(hour=filtered["order_purchase_timestamp"].dt.hour).groupby("hour", as_index=False).agg(orders=("order_id", "nunique"))
        st.plotly_chart(px.line(hourly, x="hour", y="orders", markers=True, labels={"hour": "Purchase hour", "orders": "Orders"}, color_discrete_sequence=["#e56b4a"]), use_container_width=True)

st.caption("Revenue uses one aggregated payment total per order. Category charts use item prices and may differ from payment-based revenue.")
