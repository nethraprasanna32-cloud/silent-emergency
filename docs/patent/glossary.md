# Glossary

- **Delta:** the changed entity and bounded related records selected for reevaluation.
- **ECA:** event-condition-action, implemented with transactional database triggers and worker processing.
- **Need:** a versioned inferred assistance state for a person or household.
- **Signal:** a timestamped observation that contributes evidence to one or more needs.
- **Soft reservation:** a temporary hold on volunteer/resource capacity that expires unless accepted.
- **Outbox:** database table written in the same transaction as the originating change.
- **Hash chain:** audit rows whose digest includes the prior row's digest, enabling tamper detection.
