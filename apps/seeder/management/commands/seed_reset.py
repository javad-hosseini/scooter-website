"""
Alias command for seed_clear.
Usage:
    python manage.py seed-reset --all --yes
"""

from apps.seeder.management.commands.seed_clear import Command  # noqa: F401
