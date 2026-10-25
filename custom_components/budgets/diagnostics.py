"""Diagnostics without the token, account numbers, names or transaction texts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import BudgetsConfigEntry

TO_REDACT = {CONF_TOKEN, "iban", "owner", "name", "slug", "description", "counterparty", "label", "last_error"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: BudgetsConfigEntry) -> dict[str, Any]:
    """The entry and the latest summary from Budgets, redacted."""
    coordinator = entry.runtime_data

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "summary": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
