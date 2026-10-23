"""Print the OpenAPI schema. The frontend generates its client from it.

Usage: uv run python -m novoya_api.openapi > openapi.json
"""

import json

from novoya_api.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2, sort_keys=True))
