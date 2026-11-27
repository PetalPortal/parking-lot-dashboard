"""Optional Oura adapter. Copy to oura_adapter.py (git-ignored) and point "oura_adapter" in config.json at it.

The dashboard only needs one function:

    api(path, params) -> dict

`path` is an Oura API v2 usercollection endpoint name ("daily_sleep", "daily_readiness", "sleep", "daily_activity")
and `params` is a dict like {"start_date": "2026-01-01", "end_date": "2026-01-10"}. Return the decoded JSON
({"data": [...]}). Keep your own tokens inside this file or a private file next to it. Never commit them.

Oura's developer docs: https://cloud.ouraring.com/v2/docs
"""


def api(path, params):
    raise NotImplementedError("Write your own Oura authentication here. See the docstring above.")
