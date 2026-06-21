"""Pytest hooks for the JSONC-driven test runner.

Adds a per-source-file header to the terminal report so that the
parametrized cases emitted by ``test_runner.py`` (one per ``.jsonc``
case) are visually grouped by their originating file.
"""

import pytest

_current_file: str | None = None
_config = None


def pytest_configure(config):
    """Capture the active pytest config for later terminal access.

    Args:
        config: The pytest ``Config`` object for this session.
    """
    global _config
    _config = config


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_logreport(report):
    """Emit a one-line header the first time each source file's cases run.

    Inspects the parametrized node id (``[file::case]``) and, whenever
    the source ``.jsonc`` file changes, writes its name to the terminal
    reporter to group the cases visually.

    Args:
        report: The pytest ``TestReport`` for the current phase.
    """
    global _current_file
    if report.when == "call" and _config is not None:
        nodeid = report.nodeid
        if "[" in nodeid:
            param = nodeid.split("[", 1)[1].rstrip("]")
            file = param.split("::")[0] if "::" in param else ""
            if file and file != _current_file:
                _current_file = file
                tr = _config.pluginmanager.get_plugin("terminalreporter")
                if tr:
                    tr._tw.line()
                    tr._tw.write(file + " ")
    yield
