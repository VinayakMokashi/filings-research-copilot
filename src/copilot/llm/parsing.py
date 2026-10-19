"""Reading a JSON object out of a model reply.

Models in JSON mode usually return a bare object, but some wrap it in a code fence or add
a sentence before or after it. `json_object` strips fences, takes the text from the first
"{" to the last "}", and decodes that.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def json_object(text: str) -> Any:
    """The JSON object in `text`.

    Raises ValueError when there is no object, and json.JSONDecodeError (a ValueError)
    when the object isn't valid JSON.
    """
    body = _FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The reply has no JSON object.")
    return json.loads(body[start : end + 1])
