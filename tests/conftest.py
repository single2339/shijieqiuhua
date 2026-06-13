import os

def pytest_configure(config):
    os.environ.setdefault("JWT_SECRET", "pytest-test-secret")
