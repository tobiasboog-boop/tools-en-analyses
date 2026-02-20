from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class DWHReader(Protocol):
    """Interface for reading data from client Data Warehouse.

    Current implementation: direct PostgreSQL connection via VPN.
    Future: Core App API calls.
    """

    def get_hoofdprojecten(self, klantnummer: int) -> list[dict]:
        """Get top-level projects."""
        ...

    def get_deelprojecten(self, klantnummer: int, hoofdproject_key: int) -> list[dict]:
        """Get sub-projects for a hoofdproject."""
        ...

    def get_bestekparagrafen(self, klantnummer: int, project_key: int, niveau: int) -> list[dict]:
        """Get bestekparagrafen at specified hierarchy level."""
        ...

    def get_projectdata(
        self,
        klantnummer: int,
        hoofdproject_key: int,
        start_boekdatum: date | None = None,
        einde_boekdatum: date | None = None,
    ) -> list[dict]:
        """Get full project cost/hour data from DWH.

        Returns one row per bestekparagraaf/deelproject with all cost columns.
        """
        ...
