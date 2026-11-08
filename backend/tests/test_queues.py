"""RED: reserved queue-name contract (constants only, no stub workers).

Seam: app.core.queues public constants.
"""

import asyncio

import pytest

from app.core import queues


def test_reserved_queue_names_match_spec() -> None:
    assert queues.WHATSAPP_SEND == "whatsapp:send"
    assert queues.RECORDATORIOS_DUE == "recordatorios:due"
    assert queues.ARCA_EMITIR == "arca:emitir"
    assert queues.REPORTES_GENERAR == "reportes:generar"


def test_reserved_names_are_exclusive() -> None:
    assert set(queues.ALL_QUEUES) == {
        "whatsapp:send",
        "recordatorios:due",
        "arca:emitir",
        "reportes:generar",
    }
    assert len(queues.ALL_QUEUES) == 4


def test_unknown_queue_is_rejected_before_redis() -> None:
    """C-15/platform: an undeclared queue fails explicitly, not silently."""
    with pytest.raises(ValueError, match="Unknown queue"):
        asyncio.run(queues.try_enqueue(object(), "otra:cola", "x"))
