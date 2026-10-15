# Draft claims

These claims are technical drafting material and require patent counsel review.

1. **Method.** A computer-implemented method comprising: transactionally recording, by database triggers, changes to watched assistance-system entities in an event outbox; claiming outbox rows with skip-locked row locking; selecting, from a changed entity and a spatially bounded neighborhood, only affected signal, need, volunteer, and resource records; calculating a need score from reliability-weighted signal contributions decayed by signal age and comparing the score with versioned need rules; calculating fairness-aware assignment costs for compatible candidates; and reserving selected resources with an expiry time in a serializable transaction that updates a need state and appends a hash-linked audit record.
2. **System.** A system comprising a PostgreSQL database with spatial indexes, trigger functions, versioned need-rule and signal catalogs, an event outbox, temporal need history, a worker that evaluates affected deltas, and an assignment service configured to lock inventory and volunteer records and persist explainable assignments and expiring reservations.
3. **Computer-readable medium.** A non-transitory computer-readable medium storing instructions which, when executed by a database server and service processor, cause the method of claim 1 to be performed.

4. The method of claim 1 wherein a contribution includes a signal-type weight, source reliability and an exponential half-life decay factor.
5. The method of claim 1 wherein need thresholds and minimum evidence counts are stored as editable, versioned data.
6. The method of claim 1 wherein neighborhood anomaly scores compare an area's signal rate with a signal-type baseline using a z-score.
7. The method of claim 1 wherein need state transitions are stored with valid-from and valid-to times.
8. The method of claim 1 wherein linked needs are allocated as a household assistance bundle.
9. The method of claim 1 wherein candidate cost includes geographic distance, skill overlap, language compatibility, expiry urgency and availability-window travel penalty.
10. The system of claim 2 wherein a Hungarian assignment optimizer selects a global one-to-one allocation.
11. The system of claim 2 wherein a min-cost-flow optimizer models a shared resource pool.
12. The method of claim 1 wherein a starvation-age bonus and zone service ratio modify the allocation objective.
13. The method of claim 1 wherein perishable resources nearing expiry receive an anti-wastage objective term.
14. The system of claim 2 wherein reservation expiry releases inventory and emits a delta event for rematching.
15. The method of claim 1 wherein each assignment stores factor contributions and ranked rejected alternatives.
16. The system of claim 2 wherein a simulator executes a matching projection in a transaction that is rolled back.
17. The method of claim 1 further comprising bounded feedback updates to versioned match weights after a minimum sample count.
18. The method of claim 17 wherein a weight audit retains prior versions and supports rollback.
19. The system of claim 2 wherein an SLA worker increases priority for overdue unresolved needs.
20. The method of claim 1 wherein an exclusion constraint prevents overlapping volunteer booking ranges.
21. The system of claim 2 wherein local imported records are mapped by configuration into staging relations and validated with provenance.
22. The method of claim 21 wherein entity resolution uses exact keys and fuzzy phonetic or trigram similarity and routes ambiguous pairs to a review queue.
23. The method of claim 21 wherein a repeated file hash and natural key make an import idempotent.
24. The system of claim 2 wherein consent gates inference and an emergency override stores a justification.
25. The method of claim 1 wherein beneficiary identifiers are pseudonymized and personal contact fields are encrypted.
