"""Service to fetch relaties (clients) from Syntess datawarehouse and match to contracts."""
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
import re
from sqlalchemy import text
from src.models.database import SessionLocal


class RelatieService:
    """Service to fetch relaties from Syntess and match them to contracts.

    Syntess schema: stam."Relaties"
    Key columns:
    - RelatieKey: Database ID (for internal linking, e.g. to werkbonnen)
    - Relatie Code: Client identifier that WVC uses/recognizes
    - Relatie: Full client name/description (used for matching)
    - Korte naam: Short name (alternative for matching)
    """

    RELATIES_QUERY = """
        SELECT
            "RelatieKey" AS relatie_key,
            "Relatie Code" AS client_id,
            "Relatie" AS client_name,
            "Korte naam" AS short_name,
            "Status" AS status
        FROM stam."Relaties"
        WHERE "Relatie Code" IS NOT NULL
          AND "Relatie" IS NOT NULL
        ORDER BY "Relatie"
    """

    def __init__(self):
        self.db = SessionLocal()
        self._relaties_cache: Optional[List[Dict[str, Any]]] = None

    def get_relaties(self, force_refresh: bool = False, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all relaties from Syntess datawarehouse.

        Returns list of dicts with:
        - relatie_key: Database ID (for linking to werkbonnen)
        - client_id: Relatie Code (identifier that WVC uses)
        - client_name: Full name/description
        - short_name: Korte naam (alternative name)
        - status: Active/inactive status

        Args:
            force_refresh: Force reload from database
            active_only: Only return active relaties (status check)
        """
        if self._relaties_cache is not None and not force_refresh:
            relaties = self._relaties_cache
            if active_only:
                # Filter for common active statuses
                relaties = [r for r in relaties if r.get("status") in (None, "", "Actief", "Actueel", "A", "1")]
            return relaties

        query = text(self.RELATIES_QUERY)

        try:
            result = self.db.execute(query)
            rows = result.fetchall()
            columns = result.keys()
            self._relaties_cache = [dict(zip(columns, row)) for row in rows]

            relaties = self._relaties_cache
            if active_only:
                relaties = [r for r in relaties if r.get("status") in (None, "", "Actief", "Actueel", "A", "1")]

            return relaties
        except Exception as e:
            print(f"Error fetching relaties: {e}")
            print("Check database connection and stam.\"Relaties\" table access")
            return []

    def search_relaties(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search relaties by name (case-insensitive contains)."""
        relaties = self.get_relaties()
        search_lower = search_term.lower()

        matches = [
            r for r in relaties
            if search_lower in r["client_name"].lower()
        ]
        return matches[:limit]

    def close(self):
        """Close database connection."""
        self.db.close()


class ContractMatcher:
    """Fuzzy matching service to suggest client_id for contract files.

    Uses multiple strategies to match contract filenames to relaties:
    1. Exact match (normalized)
    2. Contains match
    3. Fuzzy similarity (SequenceMatcher)

    Also matches against short_name (Korte naam) as alternative.
    """

    def __init__(self, relaties: List[Dict[str, Any]]):
        """
        Initialize matcher with list of relaties.

        Args:
            relaties: List of dicts with:
                - relatie_key: Database ID (for linking)
                - client_id: Relatie Code
                - client_name: Full name
                - short_name: Korte naam (optional)
        """
        self.relaties = relaties
        # Pre-compute normalized names for faster matching
        self._normalized_relaties = [
            {
                **r,
                "_normalized": self._normalize(r.get("client_name", "")),
                "_normalized_short": self._normalize(r.get("short_name", "") or "")
            }
            for r in relaties
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for matching: lowercase, remove special chars, etc."""
        if not text:
            return ""
        # Lowercase
        text = text.lower()
        # Remove common suffixes
        text = re.sub(r'\b(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|eenmanszaak|stichting)\b', '', text)
        # Remove special characters, keep only alphanumeric and spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.strip()

    @staticmethod
    def _extract_name_from_filename(filename: str) -> str:
        """Extract potential client name from contract filename.

        Tries to extract meaningful name parts from filenames like:
        - "Contract_BedrijfX_2024.docx" -> "BedrijfX"
        - "ServiceOvereenkomst - Klant ABC.docx" -> "Klant ABC"
        - "20240101_ContractNaam_ClientName.xlsx" -> "ClientName"
        """
        # Remove extension
        name = re.sub(r'\.(docx|xlsx|pdf|doc|xls)$', '', filename, flags=re.IGNORECASE)

        # Remove common prefixes
        prefixes = [
            r'^contract[_\s-]*',
            r'^serviceovereenkomst[_\s-]*',
            r'^onderhoudscontract[_\s-]*',
            r'^overeenkomst[_\s-]*',
            r'^\d{6,8}[_\s-]*',  # Date prefixes like 20240101
        ]
        for prefix in prefixes:
            name = re.sub(prefix, '', name, flags=re.IGNORECASE)

        # Remove common suffixes
        suffixes = [
            r'[_\s-]*\d{4}$',  # Year suffix
            r'[_\s-]*v\d+$',   # Version suffix
            r'[_\s-]*definitief$',
            r'[_\s-]*final$',
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        # Replace separators with spaces
        name = re.sub(r'[_-]+', ' ', name)

        return name.strip()

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1, s2).ratio()

    def find_matches(
        self,
        filename: str,
        top_n: int = 5,
        min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find best matching relaties for a contract filename.

        Args:
            filename: Contract filename to match
            top_n: Number of top matches to return
            min_score: Minimum similarity score (0.0-1.0)

        Returns:
            List of matches with scores, sorted by score descending.
            Each match has: relatie_key, client_id, client_name, short_name, score, match_type
        """
        extracted_name = self._extract_name_from_filename(filename)
        normalized_name = self._normalize(extracted_name)

        if not normalized_name:
            return []

        matches = []
        seen_client_ids = set()  # Avoid duplicates

        for relatie in self._normalized_relaties:
            rel_normalized = relatie["_normalized"]
            rel_short_normalized = relatie["_normalized_short"]

            best_score = 0.0
            best_type = None
            matched_on = None

            # Try matching on full name
            if rel_normalized:
                # Strategy 1: Exact match (normalized)
                if normalized_name == rel_normalized:
                    best_score = 1.0
                    best_type = "exact"
                    matched_on = "name"
                # Strategy 2: One contains the other
                elif normalized_name in rel_normalized or rel_normalized in normalized_name:
                    len_ratio = min(len(normalized_name), len(rel_normalized)) / max(len(normalized_name), len(rel_normalized))
                    score = 0.7 + (0.2 * len_ratio)
                    if score > best_score:
                        best_score = score
                        best_type = "contains"
                        matched_on = "name"
                # Strategy 3: Fuzzy similarity
                else:
                    similarity = self._similarity(normalized_name, rel_normalized)
                    if similarity > best_score and similarity >= min_score:
                        best_score = similarity
                        best_type = "fuzzy"
                        matched_on = "name"

            # Also try matching on short name (Korte naam)
            if rel_short_normalized and best_score < 1.0:
                if normalized_name == rel_short_normalized:
                    if 1.0 > best_score:
                        best_score = 1.0
                        best_type = "exact"
                        matched_on = "short_name"
                elif normalized_name in rel_short_normalized or rel_short_normalized in normalized_name:
                    len_ratio = min(len(normalized_name), len(rel_short_normalized)) / max(len(normalized_name), len(rel_short_normalized))
                    score = 0.7 + (0.2 * len_ratio)
                    if score > best_score:
                        best_score = score
                        best_type = "contains"
                        matched_on = "short_name"
                else:
                    similarity = self._similarity(normalized_name, rel_short_normalized)
                    if similarity > best_score and similarity >= min_score:
                        best_score = similarity
                        best_type = "fuzzy"
                        matched_on = "short_name"

            # Add match if score meets threshold and not a duplicate
            if best_score >= min_score and relatie["client_id"] not in seen_client_ids:
                seen_client_ids.add(relatie["client_id"])
                matches.append({
                    "relatie_key": relatie.get("relatie_key"),
                    "client_id": relatie["client_id"],
                    "client_name": relatie.get("client_name", ""),
                    "short_name": relatie.get("short_name", ""),
                    "score": best_score,
                    "match_type": best_type,
                    "matched_on": matched_on
                })

        # Sort by score descending and return top N
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:top_n]

    def match_contracts(
        self,
        contract_filenames: List[str],
        top_n: int = 3,
        min_score: float = 0.4
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Match multiple contract filenames to relaties.

        Args:
            contract_filenames: List of contract filenames
            top_n: Number of suggestions per contract
            min_score: Minimum similarity score

        Returns:
            Dict mapping filename -> list of match suggestions
        """
        results = {}
        for filename in contract_filenames:
            matches = self.find_matches(filename, top_n=top_n, min_score=min_score)
            results[filename] = matches
        return results


def match_contracts_to_relaties(
    contract_filenames: List[str],
    relaties: List[Dict[str, Any]] = None,
    top_n: int = 3,
    min_score: float = 0.4
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function to match contract files to relaties.

    If relaties not provided, fetches from database.

    Args:
        contract_filenames: List of contract filenames to match
        relaties: Optional list of relaties (fetched if not provided)
        top_n: Number of suggestions per contract
        min_score: Minimum similarity score

    Returns:
        Dict mapping filename -> list of match suggestions
    """
    if relaties is None:
        service = RelatieService()
        try:
            relaties = service.get_relaties()
        finally:
            service.close()

    if not relaties:
        print("Warning: No relaties found. Check database connection and query.")
        return {f: [] for f in contract_filenames}

    matcher = ContractMatcher(relaties)
    return matcher.match_contracts(contract_filenames, top_n=top_n, min_score=min_score)
