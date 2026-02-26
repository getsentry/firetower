from enum import StrEnum


class IncidentStatus(StrEnum):
    ACTIVE = "Active"
    MITIGATED = "Mitigated"
    POSTMORTEM = "Postmortem"
    DONE = "Done"
    CANCELLED = "Cancelled"


class IncidentSeverity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ServiceTier(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
