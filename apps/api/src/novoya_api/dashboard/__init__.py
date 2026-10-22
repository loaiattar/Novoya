"""Dashboard module: the key numbers on the admin home.

It has no table: each module counts its own rows through its public.py, and this module
puts the counts together. Endpoint: GET /admin/stats (admins only). Counts only, never a
name or an email.
"""
