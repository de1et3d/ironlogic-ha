"""Options flow for IronLogic Z-5R."""

from homeassistant import config_entries


class IronLogicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for IronLogic Z-5R."""

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        return self.async_abort(reason="no_options")