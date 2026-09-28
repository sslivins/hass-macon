# Real controller responses

Captured from a production controller (firmware 2.11.37) driving a real heat
pump, idle in hot water + cooling mode. Only identifying values were replaced
(device id, name, boot id, address, hostname and Wi-Fi network); everything
else is exactly what the firmware sent.

`tests/test_real_controller.py` feeds these through the real `pymacon`
parsers, so a firmware or pymacon change that breaks an entity shows up
here. Recapture after firmware changes the API:

    GET /api/v1/capabilities
    GET /api/v1/state
    GET /api/v1/diagnostics
