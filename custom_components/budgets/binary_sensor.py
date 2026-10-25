"""A problem sensor per bank connection: Budgets can't fetch from the bank, or the consent runs out soon."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BudgetsConfigEntry, BudgetsCoordinator
from .entity import BudgetsEntity

PARALLEL_UPDATES = 0

# A consent this close to running out needs renewing in Budgets.
CONSENT_WARNING_DAYS = 14


async def async_setup_entry(
    hass: HomeAssistant, entry: BudgetsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add a problem sensor for each bank connection, also ones added later."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def add_connections() -> None:
        new = [c for c in coordinator.data["sync"]["connections"] if c["id"] not in known]
        known.update(c["id"] for c in new)
        async_add_entities(BankConnectionProblem(coordinator, connection) for connection in new)

    add_connections()
    entry.async_on_unload(coordinator.async_add_listener(add_connections))


class BankConnectionProblem(BudgetsEntity, BinarySensorEntity):
    """On when Budgets' data from the bank is stale or failing, or the consent expires within two weeks.

    A bank that has reached its daily limit is not a problem until the data goes stale: Budgets waits for the next window.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "bank_connection"

    def __init__(self, coordinator: BudgetsCoordinator, connection: dict[str, Any]) -> None:
        super().__init__(coordinator, f"connection-{connection['id']}")
        self.connection_id: int = connection["id"]
        self._attr_translation_placeholders = {"bank": connection["bank"]}

    @property
    def connection(self) -> dict[str, Any] | None:
        return next((c for c in self.coordinator.data["sync"]["connections"] if c["id"] == self.connection_id), None)

    @property
    def available(self) -> bool:
        return super().available and self.connection is not None

    @property
    def is_on(self) -> bool | None:
        connection = self.connection
        if connection is None:
            return None
        days = connection["consent_days_remaining"]
        return bool(
            connection["stale"]
            or (connection["last_error"] and not connection["rate_limited_until"])
            or connection["status"] != "active"
            or (days is not None and days <= CONSENT_WARNING_DAYS)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        connection = self.connection
        if connection is None:
            return None
        return {
            "bank": connection["bank"],
            "status": connection["status"],
            "stale": connection["stale"],
            "last_error": connection["last_error"],
            "consent_days_remaining": connection["consent_days_remaining"],
            "consent_expires_at": connection["valid_until"],
            "last_synced_at": connection["last_synced_at"],
            "next_sync_at": connection["next_sync_at"],
            "fetches_today": connection["fetches_today"],
            "fetches_per_day": connection["fetches_per_day"],
            "rate_limited_until": connection["rate_limited_until"],
        }
