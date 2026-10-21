"""Import of the DÉTOUR export (#83, #119): partners, offers, publishable reviews and extras.

    uv run python -m novoya_api.catalog.infrastructure.detour --source path/to/detour.sqlite

read.py opens the file read-only, mapping.py turns rows into catalog entities, run.py writes
them in one transaction. See ADR 0014.
"""
