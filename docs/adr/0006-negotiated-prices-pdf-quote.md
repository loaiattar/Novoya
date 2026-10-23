# 0006. No fixed prices: a human agent negotiates and sends a PDF quote

- **Status:** Accepted. Partly replaced by [0014](0014-indicative-prices-and-detour-import.md) (indicative prices on the offer page)
- **Date:** 2026-10-16
- **Issue / PR:** #55 (Architecture 0.3)

## Context

Novoya sells only what its partners offer, and partners do not have fixed prices: the price
of a hotel, a guide or a transfer is negotiated for each trip. An AI that showed prices
would invent them.

## Decision

Offers have no price. The catalog stores what a partner offers, with person limits, dates
and tags, never a price. The AI builds a plan without prices, from real offers only: every
item points to an active `offer_id`.

A human travel agent (role `agent`) takes the plan from a queue, negotiates with each partner
outside Novoya, and enters the negotiated price of each item. Novoya then computes the total
and sends a PDF quote in English or French, valid 7 days. The client gets an email with a
button to log in and see it, then accepts or rejects it.

## Consequences

- The plan moves through `proposed → requested → negotiating → quoted → accepted/rejected`
  (ARCHITECTURE §5).
- The client's budget is saved on the wish and shown to the agent, who negotiates within it.
  It is never a filter on offers.
- Quoting needs the agent pages (queue and pricing), the PDF (WeasyPrint and Jinja2) and
  email (SMTP, Mailpit locally).
- The email carries no PDF, price or partner name; the PDF shows no partner name.
