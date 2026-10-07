"""The core install (no ``web`` extra) imports and runs the CLI without FastAPI."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_cli_imports_and_designs_without_the_web_stack():
    probe = textwrap.dedent(
        """
        import sys
        for name in ("fastapi", "starlette", "uvicorn", "jinja2"):
            sys.modules[name] = None
        import filter_lib.cli
        import filter_lib.web
        from filter_lib.web.settings import WebSettings
        assert WebSettings().port == 8765
        sys.argv = ["filter-calc", "lp", "bw", "pi", "10MHz", "-q"]
        filter_lib.cli.main()
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
