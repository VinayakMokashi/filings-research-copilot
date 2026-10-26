"""The copilot's web UI (step 6.3): a Streamlit chat over the API, with each answer's sources,
query, chart and steps, and a page of evaluation results.

`copilot.ui.client` talks to the API and holds everything worth testing; `copilot.ui.app` is
the Streamlit script, served by `poe ui`.
"""
