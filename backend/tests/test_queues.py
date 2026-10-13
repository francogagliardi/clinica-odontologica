"""RED: reserved queue-name contract (constants only, no stub workers).

Seam: app.core.queues public constants.
"""

from app.core import queues


def test_reserved_queue_names_match_spec() -> None:
    assert queues.WHATSAPP_SEND == "whatsapp:send"
    assert queues.RECORDATORIOS_DUE == "recordatorios:due"
    assert queues.ARCA_EMITIR == "arca:emitir"


def test_reserved_names_are_exclusive() -> None:
    assert set(queues.ALL_QUEUES) == {
        "whatsapp:send",
        "recordatorios:due",
        "arca:emitir",
    }
    assert len(queues.ALL_QUEUES) == 3
