# 0015. Four roles: a super admin acts on admins, and super admins are managed on the server

- **Status:** Accepted
- **Date:** 2026-10-22
- **Issue / PR:** #35, after #128

## Context

[0009](0009-roles.md) has three roles, and any admin changes any role but their own. With the
account status from #128, an admin could then demote and disable the other admins and keep the
back office for themselves. #128 stopped it with a temporary rule: no admin acts on another
admin, so nobody could disable an admin through the API at all.

## Decision

`users.role` is one of `client`, `agent`, `admin` or `super_admin`. The other rules of 0009 stay:
fixed roles, one per user, the role in the database is the only source of truth, and every
change goes to `role_changes`.

- The super admin is an admin: `require_client`, `require_agent` and `require_admin` let them
  through.
- **The super admin role is managed on the server only.** Only
  `grant-role --email ... --role super_admin` gives it, and only `grant-role` with another role
  takes it. Through the API, nobody gives it, takes it, or disables or enables a super admin's
  account, a super admin included: 403 `super_admin_server_only`. The web page never offers
  the role and locks the super admin rows.
- Only a super admin gives or takes the `admin` role (`PATCH /admin/users/{id}/role`) and
  disables or enables an admin (`PATCH /admin/users/{id}/status`). A plain admin gets 403
  `cannot_change_admin_role` or `cannot_change_admin_status`, and still manages clients and
  agents.
- Nobody changes their own role or status (409).
- There is always at least one active super admin (`last_super_admin_required`, which only the
  command can now meet). The last plain admin may lose the role: the super admin can still
  manage everything.
- The database checks the role: `ck_users_role`, plus `ck_role_changes_old_role` and
  `ck_role_changes_new_role` on the log. Downgrading the migration fails while a `super_admin`
  row exists.

## Options considered

- **A super admin manages the other super admins through the API:** one stolen or rogue super
  admin session could then hand the role out, or demote and disable every other super admin
  and keep the back office. Only someone with access to the server can do either now.
- **A plain admin may still name admins:** they could then name accomplices that only a super
  admin could demote. One simple rule is easier to check: the admin role belongs to the super
  admin.
- **Keep "at least one admin" too:** a super admin passes `require_admin`, so the rule protects
  nothing once a super admin exists.

## Consequences

- The rules live in `User.change_role` and `User.change_status`. They take the caller as
  `by`: an `AdminActor` (id and role) or `GRANT_ROLE_COMMAND` (`domain/actor.py`), never a
  missing value that would mean the command. An `AdminActor` that is not an admin is refused
  there too (`forbidden`), whatever the route let through. The count stays in
  `ChangeUserRole` and locks the rows (`FOR UPDATE`), as in 0009.
- To disable a super admin, demote them on the server first (`grant-role --role admin`), then a
  super admin disables the account from the users page. There is no server command for the
  status.
- Until someone runs `grant-role --role super_admin`, nobody acts on admins through the API,
  as with #128.
- The web users page reads the viewer's role from `GET /me`: a plain admin sees the admin rows
  locked and the Admin role greyed out, everybody sees the super admin rows locked, and nobody
  sees Super admin among the roles to give. That is only display: the API checks every change.
