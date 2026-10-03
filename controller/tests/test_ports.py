"""Unit tests for the port allocator."""

import pytest

from app.core import ports


def test_parse_range_valid():
    r = ports.parse_range("1080-1090")
    assert r.start == 1080
    assert r.stop == 1091
    assert list(r) == list(range(1080, 1091))


def test_parse_range_invalid_format():
    with pytest.raises(ValueError, match="Invalid port range"):
        ports.parse_range("invalid")
    with pytest.raises(ValueError, match="Invalid port range"):
        ports.parse_range("1080:1090")


def test_parse_range_out_of_bounds():
    with pytest.raises(ValueError, match="Invalid port range"):
        ports.parse_range("0-100")
    with pytest.raises(ValueError, match="Invalid port range"):
        ports.parse_range("5000-4000")
    with pytest.raises(ValueError, match="Invalid port range"):
        ports.parse_range("65530-65540")


def test_allocate_sequential():
    r = range(11000, 11005)
    used = set()
    p1 = ports.allocate(r, used)
    assert p1 == 11000
    used.add(p1)

    p2 = ports.allocate(r, used)
    assert p2 == 11001


def test_allocate_skips_used():
    r = range(11000, 11005)
    used = {11000, 11001}
    p = ports.allocate(r, used)
    assert p == 11002


def test_allocate_exhausted():
    r = range(11000, 11002)
    used = {11000, 11001}
    with pytest.raises(ports.PortExhausted, match="No free port"):
        ports.allocate(r, used)
