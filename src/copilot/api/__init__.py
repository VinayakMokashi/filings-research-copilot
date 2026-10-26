"""The copilot over HTTP (step 6.1): questions answered as a stream of server-sent events,
feedback on the answers, the filing pages they cite, and health checks.

`copilot.api.app.create_app` builds the FastAPI application; `poe api` serves it with
uvicorn on 127.0.0.1:8000, with its OpenAPI documentation at /docs.
"""
