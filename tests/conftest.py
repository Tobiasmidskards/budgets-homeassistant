"""Fixtures: a Budgets summary like the API's, and a config entry for it."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.budgets.const import CONF_HOUSEHOLD_ID, DOMAIN

URL = "https://budgets.example.com"
API = f"{URL}/api/v1"
TOKEN = "read-only-token"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


def money(value: float, currency: str = "DKK") -> dict[str, Any]:
    minor = round(value * 100)
    return {"minor": minor, "currency": currency, "formatted": f"{currency} {value:,.2f}", "value": value}


SUMMARY: dict[str, Any] = {
    "api_version": 1,
    "generated_at": "2026-11-10T11:00:00+00:00",
    "household": {"id": 7, "slug": "home", "name": "Home", "currency": "DKK"},
    "total_balance": money(26946.25),
    "sync": {
        "timezone": "Europe/Copenhagen",
        "windows": ["06:00", "12:00", "17:00", "21:00"],
        "last_synced_at": "2026-11-10T11:00:05+00:00",
        "next_sync_at": "2026-11-10T16:00:00+00:00",
        "stale": False,
        "connections": [
            {
                "id": 3,
                "bank": "Jyske Bank",
                "status": "active",
                "stale": False,
                "last_error": None,
                "valid_until": "2027-04-20T10:00:00+00:00",
                "consent_days_remaining": 162,
                "last_synced_at": "2026-11-10T11:00:05+00:00",
                "next_sync_at": "2026-11-10T16:00:00+00:00",
                "next_manual_sync_at": "2026-11-10T16:00:00+00:00",
                "fetches_today": 2,
                "fetches_per_day": 4,
                "rate_limited_until": None,
            }
        ],
    },
    "accounts": [
        {
            "id": 3,
            "name": "Min konto",
            "role": "spending",
            "owner": {"id": 1, "name": "Alex"},
            "iban": "DK0000000000000001",
            "balance": money(1830.5),
            "base_balance": money(1830.5),
            "balance_updated_at": "2026-11-10T11:00:05+00:00",
            "include_in_totals": True,
            "tracked": False,
            "bank_connection_id": 3,
            "bank": "Jyske Bank",
            "stale": False,
            "last_error": None,
            "consent_days_remaining": 162,
            "today_change": money(-120.5),
            "yesterday_change": money(-310),
            "this_month": {
                "money_in": money(25000),
                "money_out": money(22000),
                "spent": money(2309.34),
                "income": money(25000),
            },
        },
        {
            "id": 2,
            "name": "Madkonto (fælles)",
            "role": "shared",
            "owner": None,
            "iban": "DK0000000000000002",
            "balance": money(615.75),
            "base_balance": money(615.75),
            "balance_updated_at": "2026-11-10T11:00:05+00:00",
            "include_in_totals": True,
            "tracked": False,
            "bank_connection_id": 3,
            "bank": "Jyske Bank",
            "stale": False,
            "last_error": None,
            "consent_days_remaining": 162,
            "today_change": money(0),
            "yesterday_change": None,
            "this_month": {
                "money_in": money(4000),
                "money_out": money(1373.23),
                "spent": money(1373.23),
                "income": money(0),
            },
        },
    ],
    "my_month": {
        "month": "2026-11",
        "start": "2026-10-30",
        "end": "2026-11-26",
        "today": "2026-11-10",
        "days_left": 17,
        "own_account_ids": [3],
        "balance": money(1830.5),
        "income": {"expected": money(25000), "received": money(25000), "still_coming": money(0)},
        "transfers_total": money(15000),
        "bills": {"paid": money(3000), "still_due": money(500)},
        "room": money(6500),
        "spent": money(2309.34),
        "left": money(4190.66),
        "per_day": money(246.51),
        "projected_spending": money(5500),
        "room_runs_out_on": None,
        "room_used_up": False,
        "month_end": {"date": "2026-11-26", "expected": money(1463), "low": money(900), "high": money(2000)},
    },
    "payday": {
        "date": "2026-11-27",
        "days_until": 17,
        "month": {"month": "2026-11", "start": "2026-10-30", "end": "2026-11-26"},
        "last_salary": {"transaction_id": 500, "date": "2026-10-30", "amount": money(25000), "account_id": 3},
    },
    "key_figures": {
        "plan": None,
        "left_over": {
            "planned_per_month": money(3000),
            "actual_per_month": None,
            "actual_share_of_income": None,
            "counted_months": 0,
        },
        "fixed_expenses": {"monthly": money(12000), "share_of_income": 0.48},
        "buffer": {"at_hand": money(39830.5), "months": 2.3},
        "budget_account": {"balance": money(24500), "needs": money(28000)},
    },
    "latest_transaction_id": 900,
}


def transaction(transaction_id: int, amount: float, **overrides: Any) -> dict[str, Any]:
    return {
        "id": transaction_id,
        "booked_on": "2026-11-10",
        "status": "booked",
        "description": "NETTO",
        "counterparty": None,
        "amount": money(amount),
        "base_amount": money(amount),
        "account": {"id": 3, "name": "Min konto"},
        "category": {"id": 12, "name": "Groceries", "path": "Food › Groceries", "type": "expense"},
        "one_off": False,
        "counts_in_budget": True,
        "is_salary": False,
        "mirrors_transaction_id": None,
        "set_balance": None,
        **overrides,
    }


@pytest.fixture
def summary() -> dict[str, Any]:
    return copy.deepcopy(SUMMARY)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=f"{URL}#7",
        data={"url": URL, "token": TOKEN, CONF_HOUSEHOLD_ID: 7},
    )
