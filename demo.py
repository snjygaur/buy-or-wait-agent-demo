#!/usr/bin/env python3
"""Interactive manual-input demo for the Buy or Wait financial agent.

The original validated engine in code/main.py is reused.  This demo builds a
small temporary financial profile + recurring transaction history in memory
from the values entered by the user, then sends that synthetic state through
Agent.decide(). Nothing is written to the challenge dataset.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))
from main import Agent, fmt_money  # noqa: E402

import pandas as pd


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else (str(default) if default is not None else "")


def money_input(prompt, default=None):
    while True:
        try:
            v = float(ask(prompt, default))
            if v < 0:
                raise ValueError
            return v
        except ValueError:
            print("Please enter a valid non-negative number.")


def date_input(prompt, default):
    while True:
        v = ask(prompt, default)
        try:
            return pd.Timestamp(v).normalize()
        except Exception:
            print("Please use YYYY-MM-DD.")


def yes_no(prompt, default="yes"):
    while True:
        v = ask(f"{prompt} (yes/no)", default).lower()
        if v in {"yes", "y"}:
            return True
        if v in {"no", "n"}:
            return False
        print("Please enter yes or no.")


def csv_names(prompt, default):
    raw = ask(prompt, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def build_manual_agent(balance, income, minimum, essentials, flexible,
                       payment_preference, request_date):
    """Create temporary in-memory profile/events for the existing Agent."""
    # Bypass Agent.__init__ here: it loads/OCRs the full challenge dataset.
    # We only need the existing Agent methods for the temporary manual state.
    agent = Agent.__new__(Agent)
    agent.rates = pd.read_csv(ROOT / "dataset" / "exchange_rates.csv")
    agent.rates["rate_date"] = pd.to_datetime(agent.rates.rate_date)

    uid = "manual_user"
    cur = "INR"

    # Keep the exact profile schema expected by the existing engine.
    reduce_categories = [x[0] for x in flexible if x[2] == "reduce"]
    stop_categories = [x[0] for x in flexible if x[2] == "stop"]
    flexible_categories = set(reduce_categories + stop_categories)

    profile = {
        "user_id": uid,
        "home_currency": cur,
        "current_available_balance": balance,
        "minimum_balance_to_keep": minimum,
        "financial_priorities": "",
        "expense_categories_to_protect": "|".join(x[0] for x in essentials),
        "expense_categories_user_is_willing_to_reduce": "|".join(reduce_categories),
        "expense_categories_user_is_willing_to_stop": "|".join(stop_categories),
        "payment_methods_user_will_consider": payment_preference,
        "max_installment_months": 12,
    }
    agent.profiles = pd.DataFrame([profile])

    # Create three months of history. The existing engine uses this history to
    # infer recurring salary/expense patterns for the 90-day forecast.
    rows = []
    event_no = 1
    for months_back in (3, 2, 1):
        d = request_date - pd.DateOffset(months=months_back)
        salary_date = d.replace(day=1)
        rows.append({
            "event_id": f"manual_salary_{event_no}", "user_id": uid,
            "event_type": "income", "description": "Monthly salary",
            "category": "salary", "direction": "credit", "amount": income,
            "currency": cur, "event_date": salary_date, "settlement_date": salary_date,
            "status": "settled", "linked_event_id": None, "flexibility": "fixed",
            "minimum_allowed_amount": None,
        })
        event_no += 1

        for category, amount in essentials:
            ed = d.replace(day=5)
            rows.append({
                "event_id": f"manual_essential_{event_no}", "user_id": uid,
                "event_type": "expense", "description": f"Monthly {category}",
                "category": category, "direction": "debit", "amount": amount,
                "currency": cur, "event_date": ed, "settlement_date": ed,
                "status": "settled", "linked_event_id": None, "flexibility": "fixed",
                "minimum_allowed_amount": None,
            })
            event_no += 1

        for category, amount, mode in flexible:
            ed = d.replace(day=15)
            min_allowed = amount / 2 if mode == "reduce" else None
            rows.append({
                "event_id": f"manual_flexible_{event_no}", "user_id": uid,
                "event_type": "expense", "description": f"Monthly {category}",
                "category": category, "direction": "debit", "amount": amount,
                "currency": cur, "event_date": ed, "settlement_date": ed,
                "status": "settled", "linked_event_id": None,
                "flexibility": "reducible" if mode == "reduce" else "stoppable",
                "minimum_allowed_amount": min_allowed,
            })
            event_no += 1

    agent.events = pd.DataFrame(rows)
    for c in ["event_date", "settlement_date"]:
        agent.events[c] = pd.to_datetime(agent.events[c])
    agent.events["amount_raw"] = agent.events["amount"]

    # No supplied messages/images are needed for the manual scenario.
    agent.messages = pd.DataFrame(columns=["user_id", "message_text", "sent_at"])
    agent.images = pd.DataFrame(columns=["related_event_id", "image_id"])
    agent._normalize_events()
    agent._message_state = agent._parse_messages()

    # The existing engine's installment logic is based on supplied options.
    # Manual mode deliberately supports full payment / partial payment / wait;
    # no invented financing offer is created.
    agent.options = pd.DataFrame(columns=[
        "payment_option_id", "request_id", "payment_method", "payment_amount",
        "number_of_payments", "first_payment_date", "payment_frequency_days",
        "financing_fee", "total_payable_amount"
    ])

    return agent


def main():
    print("\n" + "=" * 68)
    print("             BUY OR WAIT - FINANCIAL AGENT")
    print("=" * 68)
    print("MANUAL USER MODE - enter a completely new financial scenario.\n")
    print("Your values are kept in memory for this run; the supplied dataset is not changed.\n")

    balance = money_input("Current balance (INR)", 80000)
    income = money_input("Monthly income (INR)", 40000)
    minimum = money_input("Minimum balance to maintain (INR)", 20000)

    print("\nEnter essential monthly expenses. Use comma-separated categories.")
    essential_names = csv_names("Essential categories", "rent,food,transport")
    essentials = []
    for cat in essential_names:
        essentials.append((cat, money_input(f"Monthly {cat} expense (INR)", 5000 if cat != "rent" else 15000)))

    print("\nEnter flexible monthly expenses. These can be reduced/stopped by the engine.")
    flexible_names = csv_names("Flexible categories", "entertainment,streaming")
    flexible = []
    for cat in flexible_names:
        amount = money_input(f"Monthly {cat} expense (INR)", 2000 if cat == "entertainment" else 500)
        mode = ask(f"For {cat}, allow reduce or stop", "reduce").lower()
        mode = "stop" if mode.startswith("s") else "reduce"
        flexible.append((cat, amount, mode))

    pref = ask("Payment preference (full_payment/partial_payment)", "full_payment").lower()
    if pref not in {"full_payment", "partial_payment"}:
        pref = "full_payment"

    request_date = date_input("Purchase/request date (YYYY-MM-DD)", "2026-10-05")
    deadline = date_input("Deadline (YYYY-MM-DD)", "2026-11-05")
    requested = money_input("Requested purchase amount (INR)", 35000)
    request_type = ask("Request type", "purchase")
    allows_partial = yes_no("Allow partial payment", "yes")
    question = ask("User question", f"Can I safely afford INR {requested:,.2f} by {deadline.date().isoformat()}?")

    agent = build_manual_agent(
        balance, income, minimum, essentials, flexible, pref, request_date
    )

    request = SimpleNamespace(
        request_id="manual_request",
        user_id="manual_user",
        request_date=request_date,
        request_type=request_type,
        requested_amount=requested,
        desired_completion_date=deadline,
        allows_partial_payment=allows_partial,
        request_text=question,
    )

    print("\n" + "-" * 68)
    print("                    ANALYZING NEW USER...")
    print("-" * 68)

    result = agent.decide(request)

    print("\n" + "=" * 68)
    print("                     AGENT RESULT")
    print("=" * 68)
    print(f"Safe amount today       : INR {result['amount_safe_to_pay']}")
    print(f"Affordability           : {result['affordability_status']}")
    print(f"Recommended method      : {result['recommended_payment_method']}")
    print(f"Payment plan            : {result['payment_plan']}")
    print(f"Earliest full payment   : {result['earliest_date_for_full_payment'] or 'Not within forecast'}")
    print(f"Spending changes        : {result['spending_changes_needed']}")
    print(f"\nDecision explanation:\n{result['decision_explanation']}")
    print("=" * 68)
    print("\nRun another completely new scenario with: python demo.py")


if __name__ == "__main__":
    main()
