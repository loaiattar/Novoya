"""Domain: User, Role (client, agent, admin), sessions, passwords, one-time tokens. Pure Python.

Rules: a new account is a client; only an admin changes a role, never their own, and only
for a verified email; signing in never changes the role.
"""
