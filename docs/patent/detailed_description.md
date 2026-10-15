# Detailed description

## Components

PostgreSQL stores entity and catalog relations, temporal need history, signal events, rules, resource inventory and workflow state. PostGIS stores area polygons and point locations. Triggers append change rows in the same transaction as entity writes. Workers claim bounded event batches without waiting on rows claimed by another worker. Signal scoring applies weight, reliability and exponential half-life decay. Need rules supply thresholds and minimum evidence counts. Needs retain state transitions in `need_history`.

The initial worker handles signal/person inference and area or resource-related deltas. Spatial matching uses `ST_DWithin` against the changed area's geometry and a bounded local radius. It does not yet have a compatibility-aware global optimizer. The table model supports need bundles and explainable matches, but automatic bundle construction is unfinished.

The assignment function locks records, checks available quantity, decrements stock, inserts a proposed match and TTL reservation, changes need state and writes a hash-chained audit event in one transaction. A caller must begin a SERIALIZABLE transaction and retry serialization/deadlock SQLSTATEs. Release of expired reservations restores stock and emits a rematch event. Verify SQL syntax and isolation behavior against a running target before deployment.

## Variants

An installation may use H3 cells instead of PostGIS radius search, plug in an offline routing matrix for ETA, or use a min-cost-flow optimizer for shared pools. Those are design variants, not claims of current implementation. The shipped stack has no mandatory external API.
