"""OSINT data source adapters.

PRD §5.1 / decision Q5: pipeline.py is the source of truth in W1; this
package owns the per-adapter modules in W2. Each adapter will export a
``collect()`` callable that returns ``(list[OsintEvidence], OsintSourceStatus)``.

W1 ships only ``base.py`` so type hints and tests can already import from
backend.football_osint.adapters without breaking.
"""
