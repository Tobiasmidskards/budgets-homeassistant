"""Diagnostics leave out the token and personal data."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import API, TOKEN


async def test_redacts_the_token_and_personal_data(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    aioclient_mock.get(f"{API}/households/7", json=summary)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    text = str(diagnostics)

    assert diagnostics["entry"]["token"] == "**REDACTED**"
    assert TOKEN not in text
    assert "DK0000000000000001" not in text
    assert "Min konto" not in text
    assert diagnostics["summary"]["accounts"][0]["balance"]["value"] == 1830.5
