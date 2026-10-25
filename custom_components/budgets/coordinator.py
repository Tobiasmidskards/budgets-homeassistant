"""Poll Budgets and turn new transactions and salaries into events."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BudgetsApi, BudgetsAuthError, BudgetsError
from .const import (
    CONF_HOUSEHOLD_ID,
    DOMAIN,
    EVENT_SALARY,
    EVENT_TRANSACTION,
    STORAGE_VERSION,
    TRANSACTIONS_PAGE,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type BudgetsConfigEntry = ConfigEntry[BudgetsCoordinator]


class BudgetsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the household's summary from Budgets and fire an event for each new transaction.

    Where the events got to (the last transaction id and the last salary) is stored, so a restart neither repeats
    nor misses events. The first run only notes where things are: history is never replayed as events.
    """

    config_entry: BudgetsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BudgetsConfigEntry, api: BudgetsApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api
        self.household_id: int = entry.data[CONF_HOUSEHOLD_ID]
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._position: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        self._position = await self._store.async_load() or {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            summary = await self.api.summary(self.household_id)
            position = dict(self._position)
            await self._fire_transactions(summary, position)
            self._fire_salary(summary, position)
        except BudgetsAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except BudgetsError as error:
            raise UpdateFailed(str(error)) from error

        if position != self._position:
            self._position = position
            await self._store.async_save(position)

        return summary

    async def _fire_transactions(self, summary: dict[str, Any], position: dict[str, Any]) -> None:
        latest = summary.get("latest_transaction_id")

        if "transaction_id" not in position:
            position["transaction_id"] = latest or 0
            return

        after: int = position["transaction_id"]
        if latest is None or latest <= after:
            return

        accounts = {account["id"]: account for account in summary["accounts"]}
        while True:
            page = await self.api.transactions(self.household_id, after, TRANSACTIONS_PAGE)
            for transaction in page["transactions"]:
                after = max(after, transaction["id"])
                # Rows Budgets keeps itself on accounts without a bank connection mirror a transfer that already fired.
                if transaction.get("mirrors_transaction_id") is None and transaction.get("set_balance") is None:
                    self.hass.bus.async_fire(
                        EVENT_TRANSACTION, transaction_event(self.household_id, transaction, accounts)
                    )
            if not page.get("has_more") or not page["transactions"]:
                break

        position["transaction_id"] = after

    def _fire_salary(self, summary: dict[str, Any], position: dict[str, Any]) -> None:
        salary = (summary.get("payday") or {}).get("last_salary")
        salary_id = salary["transaction_id"] if salary else None

        if "salary_id" not in position:
            position["salary_id"] = salary_id
            return

        if salary is None or salary_id == position["salary_id"]:
            return

        position["salary_id"] = salary_id
        account = next((account for account in summary["accounts"] if account["id"] == salary["account_id"]), None)
        self.hass.bus.async_fire(
            EVENT_SALARY,
            {
                "household_id": self.household_id,
                "transaction_id": salary_id,
                "date": salary["date"],
                "amount": salary["amount"]["value"],
                "currency": salary["amount"]["currency"],
                "account_id": salary["account_id"],
                "account_name": account["name"] if account else None,
                "balance": account["balance"]["value"] if account else None,
            },
        )


def transaction_event(
    household_id: int, transaction: dict[str, Any], accounts: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """The data of a `budgets_transaction` event: plain values automations can compare."""
    account = accounts.get(transaction["account"]["id"], {})
    category = transaction.get("category") or {}
    base = transaction.get("base_amount") or transaction["amount"]

    return {
        "household_id": household_id,
        "transaction_id": transaction["id"],
        "booked_on": transaction["booked_on"],
        "status": transaction["status"],
        "description": transaction["description"],
        "counterparty": transaction.get("counterparty"),
        "amount": transaction["amount"]["value"],
        "currency": transaction["amount"]["currency"],
        "household_amount": base["value"],
        "account_id": transaction["account"]["id"],
        "account_name": transaction["account"]["name"],
        "account_role": account.get("role"),
        "account_balance": (account.get("balance") or {}).get("value"),
        "category": category.get("path"),
        "category_type": category.get("type"),
        "is_salary": transaction.get("is_salary", False),
        "counts_in_budget": transaction.get("counts_in_budget"),
    }
