"""Exit-code reward (#14). Episode shape: graduate/contracts.md §10."""


def reward(ep) -> float:
    raise NotImplementedError


def parse_pytest_summary(output: str) -> tuple[int, int]:
    raise NotImplementedError
