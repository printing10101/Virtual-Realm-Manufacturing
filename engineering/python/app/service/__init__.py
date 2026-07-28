"""Service layer package.

This package hosts business-logic services that sit between the API layer
(``app.api.v1``) and the data-access layer (``app.repository`` /
``app.database``).  Services perform database operations and return plain
data structures (dicts / lists); they never return HTTP response objects.
"""
