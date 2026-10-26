"""The copilot's web UI (step 6.3): a Streamlit chat over the API, with each answer's sources,
query, chart and steps, and a page of evaluation results.

`copilot.ui.app` is the Streamlit script, served by `poe ui`; it talks to the API through
`copilot.api.client`, which the MCP server shares.
"""
