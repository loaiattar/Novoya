# 0017. The advisors on the home page: a public profile with the agent's agreement, no photo

- **Status:** Proposed
- **Date:** 2026-10-23
- **Issue / PR:** #167

## Context

The home page must show that real people look after each trip: the agency's advisors, with a
name, a picture or initials, and the services they handle. Advisors are users with the `agent`
role. Their account (email, first and last name) is private, and showing a staff member's name
in public is personal data: each agent must agree to it (GDPR, [ARCHITECTURE §9](../ARCHITECTURE.md#9-privacy-gdpr)).
The app stores no file today: no bucket, no upload of images.

## Decision

An agent gets a separate **public profile** (`advisor_profiles`, accounts module): a public name,
a title, a one-line summary (140 characters at most) and up to 6 services. The admin fills it in
from the back office (`PUT /admin/advisors/{user_id}`).

- Each service is typed in French, in English or both: one language at least. The home page
  shows the visitor's language, else the other one (marked with `lang` for screen readers).
  The name, title and summary are typed once, as the agent wants to be presented.
- The profile is shown only once the admin recorded the agent's agreement (when, and which
  admin). Unticking the agreement hides it at once. `GET /advisors` (public) returns only shown,
  agreed profiles of active agents, with their public fields and the profile's own id: never an
  email or an account id. A demoted or disabled agent drops out, and the profile is deleted
  with the account (`ON DELETE CASCADE`).
- **No photo.** The card shows the initials of the public name. Storing pictures needs a file
  store the app does not have, and more personal data than the story needs.

## Options considered

- Columns on `users`: mixes the private account and the public profile, and the home page
  would have to be careful never to expose the account id. Rejected.
- Services picked from the catalog (destinations, offer kinds): translated for free, but too
  rigid ("Weekends for two" is not in the catalog) and offer kinds describe partners, not trips.
- Photos stored in the database (bytea): grows the database and every backup with images,
  for a handful of pictures. Rejected for now.

## Consequences

- A possible improvement, if the agency asks for it: **photos of the advisors in an S3 bucket**
  (or any S3-compatible store). The admin uploads the picture through the API, which checks
  its type and size and stores only its key on the profile; the home page reads it through a
  CDN or a short-lived signed URL. It needs the agent's agreement for the picture too, deleting
  the object with the profile or the account, and a line on the privacy page.
- The privacy page lists the public profile (`privacy.json`, "Our advisors' public profile").
- Code: `accounts/domain/advisor_profile.py`, `accounts/application/use_cases/advisor_profiles.py`,
  the migration `b3f6d2a8c417`, the web's `Advisors` section (`LandingSections.tsx`) and the
  back office page `/admin/advisors`.
