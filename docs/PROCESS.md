# How we work

Novoya is built with Scrum to organise the work and Extreme Programming (XP) to keep the code healthy. This page is the agreement the whole team follows. If something here stops working for us, we change it at a retrospective.

## Roles

| Role | Responsibility | Who |
|---|---|---|
| Product Owner | Owns the product backlog, writes and orders the stories, accepts finished work | _to be decided_ |
| Scrum Master | Runs the ceremonies, removes blockers, protects the sprint | _to be decided_ |
| Developers | Estimate, build, test and review the work. Everyone, including the two roles above | @loaiattar, @Nabibouch, @Noumouni |

On a team of three, the Product Owner and Scrum Master also write code. They are two different people.

## The board

All work lives in the **Novoya** GitHub Project. If it is not on the board, it does not exist.

| Status | Meaning |
|---|---|
| Backlog | Ideas and stories not yet ready to work on |
| Ready | Refined: clear acceptance criteria and an estimate. Can enter a sprint |
| In progress | Someone is working on it, on a branch |
| In review | Pull request open into `dev` |
| Done | Meets the Definition of Done and is merged into `dev` |

Board fields:

- **Sprint**: the two-week iteration the item belongs to. Empty means it is still in the backlog.
- **Points**: the estimate, on the Fibonacci scale 1, 2, 3, 5, 8, 13. Anything bigger than 8 gets split.
- **Priority**: High, Medium or Low. The Product Owner sets it and keeps the backlog ordered.

## Backlog items

Open every item with one of the issue templates:

- **User story**: a feature seen from the user's side. "As a traveller, I want to save a trip draft, so that I can finish it later." It must have acceptance criteria.
- **Bug**: something that worked differently than expected, with steps to reproduce.
- **Task**: technical work with no visible user feature (setup, refactoring, upgrades).
- **Spike**: time-boxed research to answer one question before we can estimate a story.

A story is **Ready** when it is small enough for one sprint, has testable acceptance criteria, has an estimate, and has no open questions for the Product Owner.

## Sprints

Sprints last **two weeks**, Monday to Friday of the following week.

| Ceremony | When | Length | Output |
|---|---|---|---|
| Sprint planning | First Monday of the sprint | 1 hour | Sprint goal and the items moved into the sprint |
| Daily stand-up | Every working day | 15 minutes | Each person: what I did, what I'll do, what blocks me |
| Backlog refinement | Middle of the sprint | 45 minutes | Upcoming stories become Ready, with estimates |
| Sprint review | Last Friday of the sprint | 30 minutes | Demo of the Done work to the Product Owner |
| Retrospective | Right after the review | 30 minutes | One or two concrete changes for the next sprint |

At planning, only take what fits the team's recent velocity, which is the average points finished in the last three sprints. Until we have three sprints, start low and adjust.

At the end of the sprint, open a pull request from `dev` into `main`. That is the sprint's release.

## XP practices

- **Small steps.** One story per branch, one branch per pull request. Keep a pull request small enough to review in 20 minutes.
- **Test first.** Write a failing test, make it pass, then clean up. A bug fix starts with a test that reproduces the bug.
- **Continuous integration.** Merge into `dev` at least every couple of days. Long-lived branches are not allowed. CI must stay green; a red `dev` is the team's first priority.
- **Pair programming.** Pair on hard stories, risky changes and anything one person alone doesn't know well. Swap the keyboard often.
- **Code review.** Every pull request needs one approval. Review for correctness and clarity, not personal taste.
- **Refactor all the time.** Leave the code cleaner than you found it, as part of the story, not as a separate project.
- **Simple design.** Build what the current story needs, nothing for "maybe later".
- **Collective ownership.** Anyone may change any part of the code. Nobody owns a module alone.
- **Coding standard.** Follow the formatter and linter configured in the repo. Style is not debated in reviews.
- **Sustainable pace.** We plan for normal working hours. If a sprint needs overtime, we planned it wrong.

## Definition of Done

An item is Done only when all of these are true:

- [ ] Acceptance criteria are met
- [ ] Tests cover the new behaviour and they pass
- [ ] CI is green
- [ ] Code is reviewed and approved by a teammate
- [ ] Docs are updated if behaviour or setup changed
- [ ] Merged into `dev`, and the issue is closed

The pull request template repeats this checklist.

## Git workflow

See [CONTRIBUTING.md](../CONTRIBUTING.md) for branches, naming and pull requests. Name the branch after the issue and link it in the pull request with `Closes #<number>`, so the issue moves to Done when it merges.
