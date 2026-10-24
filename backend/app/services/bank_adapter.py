"""Bank verification adapters.

Only a SIMULATED adapter exists in this prototype. It does NOT contact any bank. A future real
integration (e.g. a bank's FD status API or NeSL e-BG) would implement `BankVerificationAdapter`
and be selected with BANK_ADAPTER in .env - no workflow code needs to change.
"""
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..config import settings
from ..models import FDRRecord

OUTCOMES = ("confirmed", "mismatch", "pending", "failed")


@dataclass
class BankVerificationResult:
    outcome: str
    reference: str
    is_simulated: bool
    adapter: str
    summary: str


class BankVerificationAdapter(ABC):
    name: str = "abstract"
    is_simulated: bool = True

    @abstractmethod
    def verify(self, fdr: FDRRecord, requested_outcome: str | None = None) -> BankVerificationResult:
        ...


class SimulatedBankAdapter(BankVerificationAdapter):
    """Returns whatever outcome the officer chooses, so every scenario can be demonstrated."""
    name = "simulated-demo"
    is_simulated = True

    def verify(self, fdr: FDRRecord, requested_outcome: str | None = None) -> BankVerificationResult:
        outcome = requested_outcome if requested_outcome in OUTCOMES else "pending"
        ref = f"SIM-{datetime.now():%Y%m%d}-{secrets.token_hex(3).upper()}"
        text = {
            "confirmed": "DEMO / SIMULATED: bank confirmation recorded. No real bank was contacted.",
            "mismatch": "DEMO / SIMULATED: bank reported details that do not match the submitted FDR.",
            "pending": "DEMO / SIMULATED: verification request is pending with the bank.",
            "failed": "DEMO / SIMULATED: verification could not be completed.",
        }[outcome]
        return BankVerificationResult(outcome, ref, True, self.name, text)


_ADAPTERS = {"simulated": SimulatedBankAdapter}


def get_adapter() -> BankVerificationAdapter:
    return _ADAPTERS.get(settings.bank_adapter, SimulatedBankAdapter)()
