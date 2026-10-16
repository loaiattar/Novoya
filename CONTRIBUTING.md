# Contributing to Novoya

This page covers git and pull requests. For sprints, the backlog and our XP practices, read [How we work](docs/PROCESS.md) first.

## Branches

| Branch | Purpose | Who writes to it |
|---|---|---|
| `main` | Released, stable code | Only pull requests from `dev` or `hotfix/<name>` |
| `dev` | Integration branch the team works on | Only pull requests from work branches |
| `feature/<name>`, `fix/<name>`, ... | One isolated branch per feature or fix | You |

Nobody pushes directly to `main` or `dev`. Both are protected on GitHub.

## Workflow

1. Start from the latest `dev`:

   ```bash
   git switch dev
   git pull
   git switch -c feature/trip-planner
   ```

2. Commit your work on that branch and push it:

   ```bash
   git push -u origin feature/trip-planner
   ```

3. Open a pull request into `dev` and turn on auto-merge:

   ```bash
   gh pr create --base dev --fill
   gh pr merge --auto --squash
   ```

   The PR merges by itself once `Check branch rules` passes, one teammate approves and every conversation is resolved. You don't need to update your branch with the latest `dev` first.
4. After the merge, GitHub deletes the branch. Pull `dev` again before you start the next feature.
5. To release, open a pull request from `dev` into `main`.

## Hotfixes

Use a hotfix only for an urgent bug in `main` that can't wait for the next release.

1. Branch from `main`, not `dev`:

   ```bash
   git switch main
   git pull
   git switch -c hotfix/payment-crash
   ```

2. Open a pull request from the hotfix branch into `main`.
3. After it merges, open a pull request from `main` into `dev`, so the fix isn't lost at the next release.

## Avoiding conflicts

- Keep pull requests small and merge at least once a day. The longer a branch lives, the bigger its conflicts.
- If GitHub says your PR has a conflict, merge `dev` into your branch (`git merge origin/dev`), fix the files, and push.
- **`apps/api/openapi.json`** is generated. Never fix a conflict in it by hand: take either version, then regenerate it from `apps/api` with `uv run python -m novoya_api.openapi > openapi.json` and commit.
- **Alembic migrations**: if two PRs each add a migration, `dev` ends up with two heads. Before merging, run `uv run alembic heads`. If it shows two, change your migration's `down_revision` to the other head.

## Branch names

Allowed prefixes: `feature/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`. Use `hotfix/` only for branches that go into `main`.
After the prefix use lowercase letters, digits, `.`, `_` or `-`. Example: `feature/hotel-search`.
