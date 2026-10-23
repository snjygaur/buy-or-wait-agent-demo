from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))
from main import Agent  # noqa: E402

st.set_page_config(
    page_title="Buy or Wait | Purchase Safety Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1180px;}
      .hero {padding: 1.35rem 1.5rem; border: 1px solid rgba(128,128,128,.25); border-radius: 18px; margin-bottom: 1.1rem;}
      .muted {color: #7b8190; font-size: .92rem;}
      div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: 1rem; border-radius: 14px;}
      .small-note {font-size:.82rem; color:#7b8190;}
    </style>
    """,
    unsafe_allow_html=True,
)


def parse_categories(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        name = item.strip().lower()
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def category_key(prefix: str, index: int, name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name)
    return f"{prefix}_{index}_{safe}"


def build_agent(balance, income, minimum, essentials, flexible, preference, request_date):
    # Reuse the existing engine methods with an in-memory profile/history.
    agent = Agent.__new__(Agent)
    agent.rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
    agent.rates["rate_date"] = pd.to_datetime(agent.rates.rate_date)

    uid = "manual_user"
    reduce_categories = [name for name, _, mode in flexible if mode == "reduce"]
    stop_categories = [name for name, _, mode in flexible if mode == "stop"]
    profile = {
        "user_id": uid,
        "home_currency": "INR",
        "current_available_balance": balance,
        "minimum_balance_to_keep": minimum,
        "financial_priorities": "",
        "expense_categories_to_protect": "|".join(name for name, _ in essentials),
        "expense_categories_user_is_willing_to_reduce": "|".join(reduce_categories),
        "expense_categories_user_is_willing_to_stop": "|".join(stop_categories),
        "payment_methods_user_will_consider": preference,
        "max_installment_months": 12,
    }
    agent.profiles = pd.DataFrame([profile])

    rows = []
    event_no = 1
    for months_back in (3, 2, 1):
        anchor = request_date - pd.DateOffset(months=months_back)
        salary_date = anchor.replace(day=1)
        rows.append({
            "event_id": f"manual_salary_{event_no}", "user_id": uid,
            "event_type": "income", "description": "Monthly salary", "category": "salary",
            "direction": "credit", "amount": income, "currency": "INR",
            "event_date": salary_date, "settlement_date": salary_date, "status": "settled",
            "linked_event_id": None, "flexibility": "fixed", "minimum_allowed_amount": None,
        })
        event_no += 1
        for name, amount in essentials:
            event_date = anchor.replace(day=5)
            rows.append({
                "event_id": f"manual_essential_{event_no}", "user_id": uid,
                "event_type": "expense", "description": f"Monthly {name}", "category": name,
                "direction": "debit", "amount": amount, "currency": "INR",
                "event_date": event_date, "settlement_date": event_date, "status": "settled",
                "linked_event_id": None, "flexibility": "fixed", "minimum_allowed_amount": None,
            })
            event_no += 1
        for name, amount, mode in flexible:
            event_date = anchor.replace(day=15)
            rows.append({
                "event_id": f"manual_flexible_{event_no}", "user_id": uid,
                "event_type": "expense", "description": f"Monthly {name}", "category": name,
                "direction": "debit", "amount": amount, "currency": "INR",
                "event_date": event_date, "settlement_date": event_date, "status": "settled",
                "linked_event_id": None,
                "flexibility": "reducible" if mode == "reduce" else "stoppable",
                "minimum_allowed_amount": amount / 2 if mode == "reduce" else None,
            })
            event_no += 1

    agent.events = pd.DataFrame(rows)
    for col in ("event_date", "settlement_date"):
        agent.events[col] = pd.to_datetime(agent.events[col])
    agent.events["amount_raw"] = agent.events["amount"]
    agent.messages = pd.DataFrame(columns=["user_id", "message_text", "sent_at"])
    agent.images = pd.DataFrame(columns=["related_event_id", "image_id"])
    agent._normalize_events()
    agent._message_state = agent._parse_messages()
    agent.options = pd.DataFrame(columns=[
        "payment_option_id", "request_id", "payment_method", "payment_amount",
        "number_of_payments", "first_payment_date", "payment_frequency_days",
        "financing_fee", "total_payable_amount",
    ])
    return agent


st.markdown(
    """
    <div class="hero">
      <div class="muted">PERSONAL FINANCE • DECISION SUPPORT</div>
      <h1 style="margin:.25rem 0 .4rem 0;">🛡️ Buy or Wait?</h1>
      <div>Check whether a purchase fits your cash flow before committing to it.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.warning("Demo only: uses the financial inputs you provide and a simulated recurring history. It is not connected to a bank and is not professional financial advice.")

with st.sidebar:
    st.subheader("How it works")
    st.write("1. Enter balance, income and monthly expenses.")
    st.write("2. Set the purchase price and deadline.")
    st.write("3. Review the engine's recommendation and 90-day baseline forecast.")
    st.divider()
    st.caption("No paid LLM/API calls. Manual scenarios remain in memory for the current session.")

st.subheader("1 · Your financial position")
col1, col2, col3 = st.columns(3)
with col1:
    balance = st.number_input("Current balance (₹)", min_value=0.0, value=80000.0, step=1000.0)
with col2:
    income = st.number_input("Confirmed monthly income (₹)", min_value=0.0, value=40000.0, step=1000.0)
with col3:
    minimum = st.number_input("Minimum balance to protect (₹)", min_value=0.0, value=20000.0, step=1000.0)

st.subheader("2 · Monthly expenses")
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Essential expenses**")
    essential_raw = st.text_input("Categories, comma-separated", value="rent,food,transport", key="essential_names", help="Example: rent,food,transport,electricity,medical")
    essential_names = parse_categories(essential_raw)
    essentials = []
    defaults = {"rent": 15000.0, "food": 5000.0, "transport": 3000.0}
    if len(essential_names) > 12:
        st.error("Please keep each category list to 12 or fewer items for this demo.")
    for i, name in enumerate(essential_names[:12]):
        amount = st.number_input(
            f"Monthly {name} (₹)", min_value=0.0, value=defaults.get(name, 500.0), step=500.0,
            key=category_key("essential", i, name),
        )
        essentials.append((name, amount))
with right:
    st.markdown("**Flexible expenses**")
    flexible_raw = st.text_input("Categories, comma-separated", value="entertainment,streaming", key="flexible_names", help="Example: entertainment,streaming,dining,gym")
    flexible_names = parse_categories(flexible_raw)
    flexible = []
    flexible_defaults = {"entertainment": 2000.0, "streaming": 500.0}
    if len(flexible_names) > 12:
        st.error("Please keep each category list to 12 or fewer items for this demo.")
    for i, name in enumerate(flexible_names[:12]):
        f1, f2 = st.columns([1, 1])
        with f1:
            amount = st.number_input(
                f"Monthly {name} (₹)", min_value=0.0, value=flexible_defaults.get(name, 500.0), step=250.0,
                key=category_key("flex_amount", i, name),
            )
        with f2:
            mode_label = st.selectbox(
                f"Adjustment: {name}", ["Reduce", "Stop"], index=0 if name != "streaming" else 1,
                key=category_key("flex_mode", i, name),
            )
        flexible.append((name, amount, mode_label.lower()))

st.subheader("3 · Purchase request")
p1, p2, p3 = st.columns([1.3, 1, 1])
with p1:
    item_name = st.text_input("What do you plan to buy?", value="Laptop")
with p2:
    requested = st.number_input("Purchase amount (₹)", min_value=0.01, value=35000.0, step=1000.0)
with p3:
    pref_label = st.selectbox("Preferred payment method", ["Pay in full", "Allow partial payment"])
preference = "full_payment" if pref_label == "Pay in full" else "partial_payment"

p4, p5, p6 = st.columns(3)
today = date.today()
with p4:
    request_date = st.date_input("Decision date", value=today)
with p5:
    deadline = st.date_input("Latest acceptable payment date", value=today + timedelta(days=30))
with p6:
    allow_partial = st.checkbox("Allow splitting into two payments", value=(preference == "partial_payment"))
question = st.text_input("Your question", value=f"Can I safely afford this {item_name.lower()}?")

analyse = st.button("Analyze purchase safety", type="primary", use_container_width=True)
if analyse:
    all_names = [name for name, _ in essentials] + [name for name, _, _ in flexible]
    duplicate_names = len(all_names) != len(set(all_names))
    if len(essential_names) > 12 or len(flexible_names) > 12:
        st.error("Use no more than 12 essential and 12 flexible categories.")
    elif duplicate_names:
        st.error("A category appears more than once or in both lists. Please use each category only once.")
    elif not item_name.strip():
        st.error("Enter the item you want to buy.")
    elif deadline < request_date:
        st.error("Deadline must be on or after the decision date.")
    elif minimum > balance:
        st.warning("Your current balance is already below the minimum reserve. The agent will run, but a purchase may not be safe.")
    else:
        try:
            rd = pd.Timestamp(request_date).normalize()
            dd = pd.Timestamp(deadline).normalize()
            agent = build_agent(balance, income, minimum, essentials, flexible, preference, rd)
            request = SimpleNamespace(
                request_id="manual_request", user_id="manual_user", request_date=rd,
                request_type="purchase", requested_amount=requested,
                desired_completion_date=dd, allows_partial_payment=allow_partial,
                request_text=question,
            )
            result = agent.decide(request)
            st.session_state["buy_wait_result"] = result
            st.session_state["buy_wait_context"] = {
                "item": item_name, "balance": balance, "income": income,
                "minimum": minimum, "requested": requested,
                "request_date": request_date.isoformat(), "deadline": deadline.isoformat(),
                "essentials": essentials, "flexible": flexible,
            }
            st.session_state["buy_wait_agent"] = agent
            st.session_state["buy_wait_request"] = request
        except Exception as exc:
            st.error("The scenario could not be analyzed. Check the inputs and try again.")
            st.exception(exc)

if "buy_wait_result" in st.session_state:
    result = st.session_state["buy_wait_result"]
    context = st.session_state["buy_wait_context"]
    agent = st.session_state["buy_wait_agent"]
    request = st.session_state["buy_wait_request"]
    status = result["affordability_status"]
    status_map = {
        "affordable_now": ("Affordable now", "success"),
        "affordable_with_plan": ("Affordable with a plan", "success"),
        "affordable_later": ("Wait until a safer date", "warning"),
        "not_affordable": ("Not affordable within the plan", "error"),
    }
    status_label, tone = status_map.get(status, (status, "info"))
    st.info("Showing the latest completed analysis. If you change any inputs above, click Analyze purchase safety again to refresh the result.")
    st.divider()
    st.subheader(f"Decision receipt · {context['item']}")
    if tone == "success":
        st.success(status_label)
    elif tone == "warning":
        st.warning(status_label)
    elif tone == "error":
        st.error(status_label)
    else:
        st.info(status_label)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Safe amount today", f"₹{float(result['amount_safe_to_pay']):,.2f}")
    m2.metric("Requested purchase", f"₹{context['requested']:,.2f}")
    m3.metric("Recommended method", result["recommended_payment_method"].replace("_", " ").title())
    m4.metric("Earliest full-payment date", result["earliest_date_for_full_payment"] or "Not found")

    st.markdown("#### Recommended payment plan")
    plan = result["payment_plan"]
    if plan == "none":
        st.write("No eligible safe payment plan was found by the deadline.")
    else:
        for entry in plan.split("|"):
            dt_text, amount_text = entry.split(":", 1)
            st.write(f"**{dt_text}** — ₹{float(amount_text):,.2f}")
    st.markdown("#### Why the agent decided this")
    st.write(result["decision_explanation"])

    st.markdown("#### 90-day baseline cash-flow forecast")
    st.caption("This chart shows the forecast before applying the proposed purchase payment. It is based on the synthetic recurring history generated from the inputs above.")
    rd = request.request_date.date()
    end = rd + timedelta(days=89)
    forecast_rows = agent._forecast(request.user_id, rd, end)
    daily, min_balance = agent._daily_balance(request.user_id, rd, end, forecast_rows)
    chart = pd.DataFrame({
        "Date": pd.to_datetime([d for d, _ in daily]),
        "Projected balance (before purchase)": [float(v) for _, v in daily],
        "Minimum reserve": [float(min_balance)] * len(daily),
    }).set_index("Date")
    st.line_chart(chart, height=280)
    breach_days = [d for d, value in daily if value < min_balance]
    if breach_days:
        st.warning(f"The baseline forecast falls below the minimum reserve on {breach_days[0].isoformat()} (and potentially later dates). Review the recommendation carefully.")
    else:
        st.info("The baseline forecast stays at or above the minimum reserve before accounting for the proposed purchase. The decision engine separately checks the proposed plan.")

    st.markdown("#### Scenario summary")
    summary = {
        "item": context["item"],
        "current_balance_inr": context["balance"],
        "monthly_income_inr": context["income"],
        "minimum_reserve_inr": context["minimum"],
        "purchase_amount_inr": context["requested"],
        "decision_date": context["request_date"],
        "deadline": context["deadline"],
        **result,
    }
    st.download_button(
        "Download decision receipt (JSON)",
        data=__import__("json").dumps(summary, indent=2, default=str),
        file_name="buy_or_wait_decision_receipt.json",
        mime="application/json",
    )

with st.expander("Assumptions and limits"):
    st.write("• This is a prototype for decision support, not regulated financial advice.")
    st.write("• No bank account or live transaction feed is connected.")
    st.write("• Three months of synthetic recurring history are generated from the values entered, so the engine can use its existing forecasting logic.")
    st.write("• The manual demo does not invent installment offers; no real financing provider or lender is connected.")
    st.write("• The displayed baseline chart is separate from the engine's recommended-plan decision and does not apply flexible-spending changes to the chart.")
