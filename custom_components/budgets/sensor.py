"""Sensors: each account's balance and month, and the household's month, payday, sync and key figures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BudgetsConfigEntry, BudgetsCoordinator
from .entity import BudgetsAccountEntity, BudgetsEntity

PARALLEL_UPDATES = 0

type Data = dict[str, Any]


def value(money: Data | None) -> float | None:
    """The decimal amount of a Budgets money object."""
    return None if money is None else money["value"]


def parse_date(text: str | None) -> date | None:
    return None if text is None else date.fromisoformat(text)


def parse_time(text: str | None) -> datetime | None:
    return None if text is None else dt_util.parse_datetime(text)


@dataclass(frozen=True, kw_only=True)
class BudgetsSensorDescription(SensorEntityDescription):
    """A household sensor: its value and attributes from the summary."""

    value_fn: Callable[[Data], Any]
    attributes_fn: Callable[[Data], dict[str, Any]] | None = None
    exists_fn: Callable[[Data], bool] = lambda data: True
    money: bool = False


@dataclass(frozen=True, kw_only=True)
class BudgetsAccountSensorDescription(SensorEntityDescription):
    """An account sensor: its value and attributes from the account."""

    value_fn: Callable[[Data], Any]
    attributes_fn: Callable[[Data], dict[str, Any]] | None = None
    exists_fn: Callable[[Data], bool] = lambda account: True


def month(data: Data) -> Data:
    return data.get("my_month") or {}


def money_sensor(key: str, value_fn: Callable[[Data], Any], **kwargs: Any) -> BudgetsSensorDescription:
    return BudgetsSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=value_fn,
        money=True,
        **kwargs,
    )


HOUSEHOLD_SENSORS: tuple[BudgetsSensorDescription, ...] = (
    money_sensor("total_balance", lambda data: value(data["total_balance"])),
    money_sensor(
        "left_this_month",
        lambda data: value(month(data).get("left")),
        attributes_fn=lambda data: {
            "room": value(month(data).get("room")),
            "spent": value(month(data).get("spent")),
            "income_expected": value((month(data).get("income") or {}).get("expected")),
            "income_received": value((month(data).get("income") or {}).get("received")),
            "transfers": value(month(data).get("transfers_total")),
            "bills_still_due": value((month(data).get("bills") or {}).get("still_due")),
            "room_used_up": month(data).get("room_used_up"),
            "room_runs_out_on": month(data).get("room_runs_out_on"),
            "month": month(data).get("month"),
            "month_start": month(data).get("start"),
            "month_end": month(data).get("end"),
        },
        exists_fn=lambda data: data.get("my_month") is not None,
    ),
    money_sensor(
        "spent_this_month",
        lambda data: value(month(data).get("spent")),
        exists_fn=lambda data: data.get("my_month") is not None,
    ),
    money_sensor(
        "room_this_month",
        lambda data: value(month(data).get("room")),
        exists_fn=lambda data: data.get("my_month") is not None,
    ),
    money_sensor(
        "per_day",
        lambda data: value(month(data).get("per_day")),
        attributes_fn=lambda data: {"days_left": month(data).get("days_left")},
        exists_fn=lambda data: data.get("my_month") is not None,
    ),
    money_sensor(
        "month_end_forecast",
        lambda data: value((month(data).get("month_end") or {}).get("expected")),
        attributes_fn=lambda data: {
            "date": (month(data).get("month_end") or {}).get("date"),
            "low": value((month(data).get("month_end") or {}).get("low")),
            "high": value((month(data).get("month_end") or {}).get("high")),
            "projected_spending": value(month(data).get("projected_spending")),
        },
        exists_fn=lambda data: data.get("my_month") is not None,
    ),
    BudgetsSensorDescription(
        key="days_until_payday",
        translation_key="days_until_payday",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["payday"]["days_until"],
        attributes_fn=lambda data: {"payday": data["payday"]["date"]},
    ),
    BudgetsSensorDescription(
        key="payday",
        translation_key="payday",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: parse_date(data["payday"]["date"]),
    ),
    BudgetsSensorDescription(
        key="last_salary",
        translation_key="last_salary",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: parse_date((data["payday"].get("last_salary") or {}).get("date")),
        attributes_fn=lambda data: {
            "amount": value((data["payday"].get("last_salary") or {}).get("amount")),
            "account_id": (data["payday"].get("last_salary") or {}).get("account_id"),
            "transaction_id": (data["payday"].get("last_salary") or {}).get("transaction_id"),
        },
    ),
    BudgetsSensorDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: parse_time(data["sync"]["last_synced_at"]),
    ),
    BudgetsSensorDescription(
        key="next_sync",
        translation_key="next_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: parse_time(data["sync"]["next_sync_at"]),
    ),
    BudgetsSensorDescription(
        key="consent_days_remaining",
        translation_key="consent_days_remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: min(
            (
                c["consent_days_remaining"]
                for c in data["sync"]["connections"]
                if c["consent_days_remaining"] is not None
            ),
            default=None,
        ),
        attributes_fn=lambda data: {
            "consent_expires_at": min(
                (c["valid_until"] for c in data["sync"]["connections"] if c["valid_until"]), default=None
            ),
        },
        exists_fn=lambda data: bool(data["sync"]["connections"]),
    ),
    money_sensor(
        "left_over_per_month",
        lambda data: value(
            data["key_figures"]["left_over"]["planned_per_month"]
            or data["key_figures"]["left_over"]["actual_per_month"]
        ),
        attributes_fn=lambda data: {
            "planned": value(data["key_figures"]["left_over"]["planned_per_month"]),
            "actual": value(data["key_figures"]["left_over"]["actual_per_month"]),
            "actual_share_of_income": data["key_figures"]["left_over"]["actual_share_of_income"],
            "counted_months": data["key_figures"]["left_over"]["counted_months"],
        },
    ),
    BudgetsSensorDescription(
        key="buffer_months",
        translation_key="buffer_months",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data["key_figures"]["buffer"]["months"],
        attributes_fn=lambda data: {"at_hand": value(data["key_figures"]["buffer"]["at_hand"])},
    ),
    BudgetsSensorDescription(
        key="fixed_expenses_share",
        translation_key="fixed_expenses_share",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: (
            None
            if data["key_figures"]["fixed_expenses"]["share_of_income"] is None
            else round(data["key_figures"]["fixed_expenses"]["share_of_income"] * 100, 1)
        ),
        attributes_fn=lambda data: {"monthly": value(data["key_figures"]["fixed_expenses"]["monthly"])},
    ),
)


def connection_of(account: Data, data: Data) -> Data:
    return next((c for c in data["sync"]["connections"] if c["id"] == account.get("bank_connection_id")), {})


ACCOUNT_SENSORS: tuple[BudgetsAccountSensorDescription, ...] = (
    BudgetsAccountSensorDescription(
        key="balance",
        name=None,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda account: value(account["balance"]),
    ),
    BudgetsAccountSensorDescription(
        key="spent_this_month",
        translation_key="account_spent_this_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda account: value(account["this_month"]["spent"]),
        attributes_fn=lambda account: {
            "income": value(account["this_month"]["income"]),
            "money_in": value(account["this_month"]["money_in"]),
            "money_out": value(account["this_month"]["money_out"]),
        },
    ),
    BudgetsAccountSensorDescription(
        key="money_in_this_month",
        translation_key="money_in_this_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda account: value(account["this_month"]["money_in"]),
    ),
    BudgetsAccountSensorDescription(
        key="change_today",
        translation_key="change_today",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda account: value(account["today_change"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BudgetsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add the household's sensors, and an account's when it shows up in Budgets."""
    coordinator = entry.runtime_data
    async_add_entities(
        BudgetsSensor(coordinator, description)
        for description in HOUSEHOLD_SENSORS
        if description.exists_fn(coordinator.data)
    )

    known: set[int] = set()

    @callback
    def add_accounts() -> None:
        new = [account for account in coordinator.data["accounts"] if account["id"] not in known]
        known.update(account["id"] for account in new)
        async_add_entities(
            BudgetsAccountSensor(coordinator, account, description)
            for account in new
            for description in ACCOUNT_SENSORS
            if description.exists_fn(account)
        )

    add_accounts()
    entry.async_on_unload(coordinator.async_add_listener(add_accounts))


class BudgetsSensor(BudgetsEntity, SensorEntity):
    """A figure for the household, or for the token's user within it ("my month")."""

    entity_description: BudgetsSensorDescription

    def __init__(self, coordinator: BudgetsCoordinator, description: BudgetsSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.money:
            self._attr_native_unit_of_measurement = coordinator.data["household"]["currency"]

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)


class BudgetsAccountSensor(BudgetsAccountEntity, SensorEntity):
    """A figure for one account. The balance is in the account's currency, the month's sums in the household's."""

    entity_description: BudgetsAccountSensorDescription

    def __init__(
        self, coordinator: BudgetsCoordinator, account: Data, description: BudgetsAccountSensorDescription
    ) -> None:
        super().__init__(coordinator, account, description.key)
        self.entity_description = description
        self._attr_native_unit_of_measurement = (
            account["balance"]["currency"]
            if description.key == "balance"
            else coordinator.data["household"]["currency"]
        )

    @property
    def native_value(self) -> Any:
        account = self.account
        return None if account is None else self.entity_description.value_fn(account)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        account = self.account
        if account is None:
            return None
        if self.entity_description.key == "balance":
            connection = connection_of(account, self.coordinator.data)
            return {
                "account_id": account["id"],
                "role": account["role"],
                "owner": (account.get("owner") or {}).get("name"),
                "bank": account.get("bank"),
                "tracked": account["tracked"],
                "include_in_totals": account["include_in_totals"],
                "balance_updated_at": account["balance_updated_at"],
                "change_today": value(account["today_change"]),
                "change_yesterday": value(account.get("yesterday_change")),
                "stale": account["stale"],
                "last_error": account["last_error"],
                "consent_days_remaining": account["consent_days_remaining"],
                "consent_expires_at": connection.get("valid_until"),
                "last_synced_at": connection.get("last_synced_at"),
                "next_sync_at": connection.get("next_sync_at"),
            }
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(account)
