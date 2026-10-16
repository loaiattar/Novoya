"""Planning module: the plan built from partner offers, and its life until it is quoted.

Owns the Plan and its status machine: proposed -> requested -> negotiating -> quoted ->
accepted or rejected. Agents negotiate here: take a plan, set the price of each item.
Issues: #29 (generate a plan), #50 (ask for a quote), #51 (agent queue and prices).
"""
