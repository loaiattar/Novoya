"""HTTP endpoints, one module per resource.

Keep them thin: parse the request, call one use case, map the result or the domain
error to a response.

Done: health.py. Planned: auth.py, me.py, destinations.py, wishes.py, plans.py,
quotes.py, agent.py (/agent/*, agent role only), admin.py (/admin/partners, /admin/offers).
"""
