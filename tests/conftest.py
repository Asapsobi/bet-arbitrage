from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures'


@pytest.fixture
def fixtures():
    return FIXTURES
