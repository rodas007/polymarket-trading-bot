"""Smoke tests to catch syntax/import regressions in flash crash modules."""

import importlib


def test_import_flash_crash_module():
    module = importlib.import_module("strategies.flash_crash")
    assert hasattr(module, "DemoFlashCrashStrategy")
    assert hasattr(module, "DemoFlashCrashConfig")


def test_import_run_flash_crash_module():
    module = importlib.import_module("apps.run_flash_crash")
    assert hasattr(module, "main")
    assert hasattr(module, "parse_args")
