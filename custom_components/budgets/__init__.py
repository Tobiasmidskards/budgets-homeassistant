"""The Budgets integration: a household's finances from Budgets, which is the only thing that talks to the bank."""

from __future__ import annotations

from homeassistant.const import CONF_TOKEN, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import BudgetsApi
from .const import DOMAIN, STORAGE_VERSION
from .coordinator import BudgetsConfigEntry, BudgetsCoordinator
from .entity import household_device_info

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BudgetsConfigEntry) -> bool:
    """Set up Budgets from a config entry."""
    api = BudgetsApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = BudgetsCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    # The accounts' devices link to the household's by its id, so it has to exist before their entities are added.
    household = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **household_device_info(coordinator)
    )
    coordinator.household_device_id = household.id
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BudgetsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BudgetsConfigEntry) -> None:
    """Forget where the events got to when the entry is deleted."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
