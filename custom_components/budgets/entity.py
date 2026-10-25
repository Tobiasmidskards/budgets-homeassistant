"""Shared entity bits: one device for the household and one per account."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BudgetsCoordinator

# Home Assistant 2026.8 links a device to its parent by device id; `via_device` (an identifier) is deprecated there.
LINKS_BY_DEVICE_ID = "via_device_id" in DeviceInfo.__annotations__

ROLE_MODELS = {
    "spending": "Everyday account",
    "budget": "Budget account",
    "shared": "Shared account",
    "savings": "Savings account",
    "investment": "Investment account",
    "credit_card": "Credit card",
    "loan": "Loan",
}


def household_device_info(coordinator: BudgetsCoordinator) -> DeviceInfo:
    """The household's device, which the accounts' devices hang under."""
    household = coordinator.data["household"]
    return DeviceInfo(
        identifiers={(DOMAIN, household_identifier(coordinator))},
        name=household["name"],
        manufacturer="Budgets",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=coordinator.config_entry.data[CONF_URL],
    )


class BudgetsEntity(CoordinatorEntity[BudgetsCoordinator]):
    """An entity on the household's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BudgetsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{key}"
        self._attr_device_info = household_device_info(coordinator)


class BudgetsAccountEntity(CoordinatorEntity[BudgetsCoordinator]):
    """An entity on an account's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BudgetsCoordinator, account: dict[str, Any], key: str) -> None:
        super().__init__(coordinator)
        self.account_id: int = account["id"]
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-account-{account['id']}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{household_identifier(coordinator)}-account-{account['id']}")},
            name=account["name"],
            manufacturer=account.get("bank") or "Budgets",
            model=ROLE_MODELS.get(account.get("role") or "", "Account"),
            entry_type=DeviceEntryType.SERVICE,
        )
        if LINKS_BY_DEVICE_ID:
            self._attr_device_info["via_device_id"] = coordinator.household_device_id
        else:
            self._attr_device_info["via_device"] = (DOMAIN, household_identifier(coordinator))

    @property
    def account(self) -> dict[str, Any] | None:
        """The account in the latest data, or None when it is gone from Budgets."""
        return next((a for a in self.coordinator.data["accounts"] if a["id"] == self.account_id), None)

    @property
    def available(self) -> bool:
        return super().available and self.account is not None


def household_identifier(coordinator: BudgetsCoordinator) -> str:
    """The household device's identifier: the config entry's unique id (URL and household id)."""
    return str(coordinator.config_entry.unique_id)
