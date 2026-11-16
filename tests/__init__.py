"""Shared test-suite markers."""


def integration_test(test):
    """Mark a test method or class as requiring a live HydraDB instance."""
    test.hydradb_integration = True
    return test
