from enum import Enum


class MemoryType(str, Enum):
    decision = "decision"
    task = "task"
    artifact = "artifact"
    event = "event"
    note = "note"


class MemoryLinkType(str, Enum):
    depends_on = "depends_on"
    related_to = "related_to"
    created_after = "created_after"
    affects = "affects"
    derived_from = "derived_from"
    blocks = "blocks"
    resolves = "resolves"

