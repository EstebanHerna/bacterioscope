"""Entry point for running BacterioScope as a Python module.

Python executes this file when you run::

    python -m bacterioscope <command> [options]

The ``-m`` flag tells Python to look for a ``__main__.py`` file inside the
``bacterioscope`` package and run it. This file simply imports the Typer CLI
application from ``cli.py`` and calls it, which makes all commands available.

Available commands
------------------
``analyze``  Run the full pipeline on a plate image.
``version``  Print the installed package version.

Example
-------
::

    python -m bacterioscope analyze docs/plate_original.png
    python -m bacterioscope analyze plate.jpg --output annotated.jpg
    python -m bacterioscope version
"""

from bacterioscope.cli import app

app()
