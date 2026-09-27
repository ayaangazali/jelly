"""registry.json state machine (#18). Shape: graduate/contracts.md §1, §5."""


class IllegalTransition(Exception):
    pass


def load() -> dict:
    raise NotImplementedError


def save(reg: dict) -> None:
    raise NotImplementedError


def transition(task_type: str, to_state: str, **fields) -> dict:
    raise NotImplementedError


def set_consent(task_type: str, consent: bool) -> None:
    raise NotImplementedError


def add_event(kind: str, task_type: str, text: str) -> None:
    raise NotImplementedError
