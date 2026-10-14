from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CurrentUser:
    id: UUID


@dataclass(frozen=True)
class CurrentAthlete:
    id: UUID
