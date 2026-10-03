"""Host port allocation for proxy listeners."""


class PortExhausted(Exception):
    pass


def parse_range(spec: str) -> range:
    try:
        lo, hi = (int(x) for x in spec.split("-", 1))
    except ValueError as exc:
        raise ValueError(f"Invalid port range '{spec}', expected 'start-end'") from exc
    if not (1 <= lo <= hi <= 65535):
        raise ValueError(f"Invalid port range '{spec}'")
    return range(lo, hi + 1)


def allocate(port_range: range, used: set[int]) -> int:
    for port in port_range:
        if port not in used:
            return port
    raise PortExhausted(f"No free port in {port_range.start}-{port_range.stop - 1}")
