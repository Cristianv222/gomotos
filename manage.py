#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Agregar directorio apps al sys.path
    import sys
    import os
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    sys.path.insert(0, os.path.join(base_dir, 'apps'))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vpmotos.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
