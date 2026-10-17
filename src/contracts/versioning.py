from datetime import date

from .models import Contract, ContractVersion


def version_in_force(contract: Contract, on: date) -> ContractVersion | None:
    for version in contract.versions:
        if version.effective_from <= on and (
            version.effective_to is None or on < version.effective_to
        ):
            return version
    return None
