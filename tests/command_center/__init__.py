"""Command Center test suite.

Uses only :mod:`unittest` from the standard library. The build environment has
no package network, so a suite that needed ``pytest`` could not actually run --
and a test that does not run must never be reported as passing.
"""
