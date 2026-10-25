"""Config flow for Budgets: the URL of the Budgets app and a read-only API token from its settings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from yarl import URL

from .api import BudgetsApi, BudgetsAuthError, BudgetsError
from .const import CONF_HOUSEHOLD_ID, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))})


def normalize_url(url: str) -> str:
    """The app's base URL without a trailing slash or path, so the same app is one URL."""
    parsed = URL(url.strip())
    return str(parsed.with_path("").with_query(None).with_fragment(None)).rstrip("/")


class BudgetsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a household from Budgets."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str = ""
        self._token: str = ""
        self._households: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the URL and the token, and check them by listing the households."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._url = normalize_url(user_input[CONF_URL])
            self._token = user_input[CONF_TOKEN].strip()
            error = await self._load_households()

            if error is not None:
                errors["base"] = error
            elif not self._households:
                return self.async_abort(reason="no_households")
            elif len(self._households) == 1:
                return await self._create(self._households[0])
            else:
                return await self.async_step_household()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or {}),
            errors=errors,
        )

    async def async_step_household(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the household when the user is in more than one."""
        if user_input is not None:
            household = next(h for h in self._households if str(h["id"]) == user_input[CONF_HOUSEHOLD_ID])
            return await self._create(household)

        options = [SelectOptionDict(value=str(h["id"]), label=h["name"]) for h in self._households]
        current = next((h for h in self._households if h.get("is_current")), self._households[0])

        return self.async_show_form(
            step_id="household",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOUSEHOLD_ID, default=str(current["id"])): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The token expired or was deleted in Budgets."""
        self._url = entry_data[CONF_URL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for a new token for the same household."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            self._token = user_input[CONF_TOKEN].strip()
            error = await self._load_households()

            if error is not None:
                errors["base"] = error
            elif not any(h["id"] == entry.data[CONF_HOUSEHOLD_ID] for h in self._households):
                errors["base"] = "household_missing"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: self._token})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"url": self._url},
        )

    async def _load_households(self) -> str | None:
        api = BudgetsApi(async_get_clientsession(self.hass), self._url, self._token)
        try:
            self._households = await api.households()
        except BudgetsAuthError:
            return "invalid_auth"
        except BudgetsError:
            return "cannot_connect"
        return None

    async def _create(self, household: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{self._url}#{household['id']}")
        self._abort_if_unique_id_configured(updates={CONF_TOKEN: self._token})

        return self.async_create_entry(
            title=household["name"],
            data={CONF_URL: self._url, CONF_TOKEN: self._token, CONF_HOUSEHOLD_ID: household["id"]},
        )
