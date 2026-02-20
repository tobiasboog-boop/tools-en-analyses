"""Service to fetch werkbon chains (keten) with all related data for LLM classification.

A werkbon "keten" consists of:
- Hoofdwerkbon (main workorder)
- Vervolgbonnen (follow-up workorders, linked via ParentWerkbonDocumentKey)
- Werkbonparagrafen per werkbon (work paragraphs)
- Kosten per paragraaf (costs)
- Opbrengsten per paragraaf (revenue = billed = "buiten contract")

The service builds a complete JSON structure and narrative ("verhaal") for LLM input.
"""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.models.database import SessionLocal


@dataclass
class KostenRegel:
    """A single cost line within a werkbonparagraaf (from financieel.Kosten)."""
    omschrijving: str
    aantal: float
    verrekenprijs: float
    kostprijs: float
    kostenbron: str  # e.g., "Inkoop", "Urenstaat", "Materiaaluitgifte"
    categorie: str  # "Arbeid", "Materiaal", "Overig", "Materieel"
    factureerstatus: str
    kostenstatus: str
    boekdatum: Optional[str] = None
    medewerker: Optional[str] = None  # Medewerker naam (voor urenregels)
    taak: Optional[str] = None  # Taak naam (voor urenregels)

    def get_volledige_omschrijving(self) -> str:
        """Geeft omschrijving inclusief medewerker/taak voor arbeidsregels."""
        parts = [self.omschrijving]
        if self.medewerker:
            parts.append(f"Medewerker: {self.medewerker}")
        if self.taak:
            parts.append(f"Taak: {self.taak}")
        return " | ".join(parts) if len(parts) > 1 else self.omschrijving


@dataclass
class OpbrengstRegel:
    """A revenue/billed line (indicates work was billed = buiten contract)."""
    omschrijving: str
    bedrag: float
    kostensoort: str
    tarief: str
    factuurdatum: Optional[str]


@dataclass
class Opvolging:
    """An opvolging (follow-up action) on a werkbon paragraaf."""
    opvolgsoort: str
    beschrijving: str
    status: str
    aanmaakdatum: Optional[str]
    laatste_wijzigdatum: Optional[str]


@dataclass
class Oplossing:
    """An oplossing (solution) for a werkbon paragraaf."""
    oplossing: str
    oplossing_uitgebreid: Optional[str]
    aanmaakdatum: Optional[str]


@dataclass
class WerkbonParagraaf:
    """A paragraph within a werkbon containing work details."""
    werkbonparagraaf_key: int
    naam: str
    type: str
    factureerwijze: str  # Key field: "Vaste prijs (binnen contract)", "Regie", etc.
    storing: Optional[str]
    oorzaak: Optional[str]
    uitvoeringstatus: str

    # Datetime fields
    plandatum: Optional[str] = None
    uitgevoerd_op: Optional[str] = None
    tijdstip_uitgevoerd: Optional[str] = None

    # Aggregated from database
    totaal_kosten: float = 0.0
    totaal_arbeid_kosten: float = 0.0
    totaal_materiaal_kosten: float = 0.0
    totaal_opbrengsten: float = 0.0  # If > 0, this work was billed (buiten contract)

    # Detail lines (optional, for deep inspection)
    kosten: List[KostenRegel] = field(default_factory=list)
    opbrengsten: List[OpbrengstRegel] = field(default_factory=list)
    opvolgingen: List[Opvolging] = field(default_factory=list)
    oplossingen: List[Oplossing] = field(default_factory=list)


@dataclass
class Werkbon:
    """A single werkbon (work order) in the chain."""
    werkbon_key: int
    werkbon_nummer: str
    type: str  # e.g., "Losse regiebon", "Storingsbon"
    status: str
    documentstatus: str
    administratieve_fase: Optional[str]
    klant: str
    debiteur: str
    postcode: str
    plaats: str
    melddatum: Optional[str]
    meldtijd: Optional[str]
    afspraakdatum: Optional[str]
    opleverdatum: Optional[str]
    monteur: Optional[str]
    niveau: int  # Position in chain (1 = hoofdwerkbon)
    is_hoofdwerkbon: bool

    # Aggregated totals
    totaal_kosten: float = 0.0
    totaal_opbrengsten: float = 0.0

    # Paragrafen
    paragrafen: List[WerkbonParagraaf] = field(default_factory=list)


@dataclass
class WerkbonKeten:
    """Complete werkbon chain: hoofdwerkbon + all vervolgbonnen."""
    hoofdwerkbon_key: int
    relatie_key: int
    relatie_code: str
    relatie_naam: str

    # All werkbonnen in the chain
    werkbonnen: List[Werkbon] = field(default_factory=list)

    # Chain-level aggregations
    totaal_kosten: float = 0.0
    totaal_opbrengsten: float = 0.0
    aantal_werkbonnen: int = 0
    aantal_paragrafen: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WerkbonKetenService:
    """Service to fetch complete werkbon chains for LLM classification."""

    def __init__(self):
        self.db = SessionLocal()

    def _ensure_fresh_connection(self):
        """Ensure database connection is fresh and session is clean."""
        # Always create a fresh session to avoid stale connection issues
        try:
            self.db.close()
        except Exception:
            pass
        self.db = SessionLocal()

    def get_werkbon_keten(
        self,
        hoofdwerkbon_key: int,
        include_kosten_details: bool = False,
        include_opbrengsten_details: bool = False,
        include_opvolgingen: bool = False,
        include_oplossingen: bool = False
    ) -> Optional[WerkbonKeten]:
        """
        Fetch a complete werkbon chain by hoofdwerkbon key.

        Args:
            hoofdwerkbon_key: The WerkbonDocumentKey of the main werkbon
            include_kosten_details: Include individual cost lines (more data)
            include_opbrengsten_details: Include individual revenue lines
            include_opvolgingen: Include opvolgingen (follow-up actions)
            include_oplossingen: Include oplossingen (solutions)

        Returns:
            WerkbonKeten object with all related data, or None if not found
        """
        # Ensure fresh connection
        self._ensure_fresh_connection()

        # Ensure key is an integer
        hoofdwerkbon_key = int(hoofdwerkbon_key)

        # Step 1: Get all werkbonnen in the chain
        werkbonnen_data = self._fetch_werkbonnen_in_keten(hoofdwerkbon_key)
        if not werkbonnen_data:
            return None

        # Build werkbon objects
        werkbonnen = []
        werkbon_keys = []

        for wb_data in werkbonnen_data:
            werkbon = Werkbon(
                werkbon_key=wb_data["werkbon_key"],
                werkbon_nummer=wb_data["werkbon_nummer"] or "",
                type=wb_data["type"] or "",
                status=wb_data["status"] or "",
                documentstatus=wb_data["documentstatus"] or "",
                administratieve_fase=wb_data.get("administratieve_fase"),
                klant=wb_data["klant"] or "",
                debiteur=wb_data["debiteur"] or "",
                postcode=wb_data["postcode"] or "",
                plaats=wb_data["plaats"] or "",
                melddatum=self._format_date(wb_data.get("melddatum")),
                meldtijd=self._format_time(wb_data.get("meldtijd")),
                afspraakdatum=self._format_date(wb_data.get("afspraakdatum")),
                opleverdatum=self._format_date(wb_data.get("opleverdatum")),
                monteur=wb_data.get("monteur"),
                niveau=wb_data.get("niveau") or 1,
                is_hoofdwerkbon=(wb_data["werkbon_key"] == hoofdwerkbon_key)
            )
            werkbonnen.append(werkbon)
            werkbon_keys.append(wb_data["werkbon_key"])

        # Step 2: Get paragrafen with aggregated kosten/opbrengsten
        paragrafen_data = self._fetch_paragrafen_with_totals(werkbon_keys)

        # Map paragrafen to werkbonnen
        paragraaf_map = {}  # werkbon_key -> list of paragrafen
        for p_data in paragrafen_data:
            wb_key = p_data["werkbon_key"]
            if wb_key not in paragraaf_map:
                paragraaf_map[wb_key] = []

            paragraaf = WerkbonParagraaf(
                werkbonparagraaf_key=p_data["werkbonparagraaf_key"],
                naam=p_data["naam"] or "",
                type=p_data["type"] or "",
                factureerwijze=p_data["factureerwijze"] or "",
                storing=p_data.get("storing"),
                oorzaak=p_data.get("oorzaak"),
                uitvoeringstatus=p_data.get("uitvoeringstatus") or "",
                plandatum=self._format_date(p_data.get("plandatum")),
                uitgevoerd_op=self._format_date(p_data.get("uitgevoerd_op")),
                tijdstip_uitgevoerd=self._format_time(p_data.get("tijdstip_uitgevoerd")),
                totaal_kosten=float(p_data.get("totaal_kosten") or 0),
                totaal_arbeid_kosten=float(p_data.get("totaal_arbeid_kosten") or 0),
                totaal_materiaal_kosten=float(p_data.get("totaal_materiaal_kosten") or 0),
                totaal_opbrengsten=float(p_data.get("totaal_opbrengsten") or 0)
            )
            paragraaf_map[wb_key].append(paragraaf)

        # Assign paragrafen to werkbonnen and calculate totals
        for werkbon in werkbonnen:
            werkbon.paragrafen = paragraaf_map.get(werkbon.werkbon_key, [])
            werkbon.totaal_kosten = sum(p.totaal_kosten for p in werkbon.paragrafen)
            werkbon.totaal_opbrengsten = sum(p.totaal_opbrengsten for p in werkbon.paragrafen)

        # Optionally load detail lines
        if include_kosten_details:
            self._load_kosten_details(werkbonnen)
        if include_opbrengsten_details:
            self._load_opbrengsten_details(werkbonnen)
        if include_opvolgingen:
            self._load_opvolgingen(werkbonnen)
        if include_oplossingen:
            self._load_oplossingen(werkbonnen)

        # Get relatie info from first werkbon
        first_wb = werkbonnen_data[0]

        # Build the keten
        keten = WerkbonKeten(
            hoofdwerkbon_key=hoofdwerkbon_key,
            relatie_key=first_wb.get("debiteur_relatie_key") or 0,
            relatie_code=self._extract_code(first_wb.get("debiteur") or ""),
            relatie_naam=self._extract_name(first_wb.get("debiteur") or ""),
            werkbonnen=werkbonnen,
            totaal_kosten=sum(w.totaal_kosten for w in werkbonnen),
            totaal_opbrengsten=sum(w.totaal_opbrengsten for w in werkbonnen),
            aantal_werkbonnen=len(werkbonnen),
            aantal_paragrafen=sum(len(w.paragrafen) for w in werkbonnen)
        )

        return keten

    def get_werkbon_ketens_by_relatie(
        self,
        relatie_key: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[WerkbonKeten]:
        """
        Get all werkbon chains for a specific relatie (client).

        Returns only hoofdwerkbonnen; use get_werkbon_keten() to load full chain.
        """
        query = text("""
            SELECT DISTINCT
                w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
                w."Werkbon" as werkbon_nummer,
                w."MeldDatum" as melddatum,
                w."Status" as status
            FROM werkbonnen."Werkbonnen" w
            WHERE w."DebiteurRelatieKey" = :relatie_key
              AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"  -- Only hoofdwerkbonnen
              AND (:start_date IS NULL OR w."MeldDatum" >= :start_date)
              AND (:end_date IS NULL OR w."MeldDatum" <= :end_date)
            ORDER BY w."MeldDatum" DESC
            LIMIT :limit
        """)

        try:
            result = self.db.execute(query, {
                "relatie_key": relatie_key,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            })
            rows = result.fetchall()

            ketens = []
            for row in rows:
                keten = self.get_werkbon_keten(row[0])
                if keten:
                    ketens.append(keten)

            return ketens
        except Exception as e:
            print(f"Error fetching werkbon ketens: {e}")
            return []

    def _fetch_werkbonnen_in_keten(self, hoofdwerkbon_key: int) -> List[Dict]:
        """Fetch all werkbonnen belonging to a chain."""
        query = text("""
            SELECT
                w."WerkbonDocumentKey" as werkbon_key,
                w."Werkbon" as werkbon_nummer,
                w."Type" as type,
                w."Status" as status,
                w."Documentstatus" as documentstatus,
                w."Administratieve fase" as administratieve_fase,
                w."Klant" as klant,
                w."Debiteur" as debiteur,
                w."DebiteurRelatieKey" as debiteur_relatie_key,
                w."Postcode" as postcode,
                w."Plaats" as plaats,
                w."MeldDatum" as melddatum,
                w."MeldTijd" as meldtijd,
                w."AfspraakDatum" as afspraakdatum,
                w."Opleverdatum" as opleverdatum,
                w."Monteur" as monteur,
                w."Niveau" as niveau
            FROM werkbonnen."Werkbonnen" w
            WHERE w."HoofdwerkbonDocumentKey" = :hoofdwerkbon_key
            ORDER BY w."Niveau", w."WerkbonDocumentKey"
        """)

        result = self.db.execute(query, {"hoofdwerkbon_key": hoofdwerkbon_key})
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]

    def _fetch_paragrafen_with_totals(self, werkbon_keys: List[int]) -> List[Dict]:
        """Fetch paragrafen with aggregated kosten and opbrengsten."""
        if not werkbon_keys:
            return []

        # Build placeholder list for IN clause
        placeholders = ", ".join([f":wb_{i}" for i in range(len(werkbon_keys))])
        params = {f"wb_{i}": key for i, key in enumerate(werkbon_keys)}

        query = text(f"""
            SELECT
                p."WerkbonDocumentKey" as werkbon_key,
                p."WerkbonparagraafKey" as werkbonparagraaf_key,
                p."Werkbonparagraaf" as naam,
                p."Type" as type,
                p."Factureerwijze" as factureerwijze,
                p."Storing" as storing,
                p."Oorzaak" as oorzaak,
                p."Uitvoeringstatus" as uitvoeringstatus,
                p."Plandatum" as plandatum,
                p."Uitgevoerd op" as uitgevoerd_op,
                p."TijdstipUitgevoerd" as tijdstip_uitgevoerd,
                COALESCE(k.totaal_kosten, 0) as totaal_kosten,
                COALESCE(k.totaal_arbeid, 0) as totaal_arbeid_kosten,
                COALESCE(k.totaal_kosten, 0) - COALESCE(k.totaal_arbeid, 0) as totaal_materiaal_kosten,
                COALESCE(o.totaal_opbrengsten, 0) as totaal_opbrengsten
            FROM werkbonnen."Werkbonparagrafen" p
            LEFT JOIN (
                SELECT
                    "WerkbonparagraafKey",
                    SUM("Kostprijs") as totaal_kosten,
                    SUM(CASE WHEN "Arbeidregel Ja / Nee" = 'Ja'
                        THEN "Kostprijs" ELSE 0 END) as totaal_arbeid
                FROM werkbonnen."Werkbon kosten"
                GROUP BY "WerkbonparagraafKey"
            ) k ON k."WerkbonparagraafKey" = p."WerkbonparagraafKey"
            LEFT JOIN (
                SELECT
                    "WerkbonParagraafKey",
                    SUM("Bedrag") as totaal_opbrengsten
                FROM financieel."Opbrengsten"
                GROUP BY "WerkbonParagraafKey"
            ) o ON o."WerkbonParagraafKey" = p."WerkbonparagraafKey"
            WHERE p."WerkbonDocumentKey" IN ({placeholders})
            ORDER BY p."WerkbonDocumentKey", p."WerkbonparagraafKey"
        """)

        try:
            result = self.db.execute(query, params)
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"Error fetching paragrafen: {e}")
            return []

    def _load_kosten_details(self, werkbonnen: List[Werkbon]):
        """Load individual cost lines for all paragrafen from financieel.Kosten."""
        # Get all paragraaf keys
        paragraaf_keys = []
        paragraaf_map = {}  # key -> paragraaf object
        for wb in werkbonnen:
            for p in wb.paragrafen:
                paragraaf_keys.append(p.werkbonparagraaf_key)
                paragraaf_map[p.werkbonparagraaf_key] = p

        if not paragraaf_keys:
            return

        placeholders = ", ".join([f":p_{i}" for i in range(len(paragraaf_keys))])
        params = {f"p_{i}": key for i, key in enumerate(paragraaf_keys)}

        query = text(f"""
            SELECT
                k."WerkbonparagraafKey" as paragraaf_key,
                k."Omschrijving" as omschrijving,
                k."Aantal" as aantal,
                k."Verrekenprijs" as verrekenprijs,
                k."Kostprijs" as kostprijs,
                k."Kostenbron" as kostenbron,
                k."Categorie" as categorie,
                k."Factureerstatus" as factureerstatus,
                k."Kostenstatus" as kostenstatus,
                k."Boekdatum" as boekdatum,
                m."Medewerker" as medewerker,
                t."Taak" as taak
            FROM financieel."Kosten" k
            LEFT JOIN stam."Medewerkers" m ON k."MedewerkerKey" = m."MedewerkerKey"
            LEFT JOIN uren."Taken" t ON k."TaakKey" = t."TaakKey"
            WHERE k."WerkbonparagraafKey" IN ({placeholders})
            ORDER BY k."WerkbonparagraafKey", k."Boekdatum" DESC, k."RegelKey"
        """)

        try:
            result = self.db.execute(query, params)
            for row in result.fetchall():
                paragraaf_key = row[0]
                if paragraaf_key in paragraaf_map:
                    kosten_regel = KostenRegel(
                        omschrijving=row[1] or "",
                        aantal=float(row[2] or 0),
                        verrekenprijs=float(row[3] or 0),
                        kostprijs=float(row[4] or 0),
                        kostenbron=(row[5] or "").strip(),
                        categorie=(row[6] or "").strip(),
                        factureerstatus=row[7] or "",
                        kostenstatus=row[8] or "",
                        boekdatum=self._format_date(row[9]),
                        medewerker=row[10],
                        taak=row[11]
                    )
                    paragraaf_map[paragraaf_key].kosten.append(kosten_regel)
        except Exception as e:
            print(f"Error loading kosten details: {e}")

    def _load_opbrengsten_details(self, werkbonnen: List[Werkbon]):
        """Load individual revenue lines for all paragrafen."""
        paragraaf_keys = []
        paragraaf_map = {}
        for wb in werkbonnen:
            for p in wb.paragrafen:
                paragraaf_keys.append(p.werkbonparagraaf_key)
                paragraaf_map[p.werkbonparagraaf_key] = p

        if not paragraaf_keys:
            return

        placeholders = ", ".join([f":p_{i}" for i in range(len(paragraaf_keys))])
        params = {f"p_{i}": key for i, key in enumerate(paragraaf_keys)}

        query = text(f"""
            SELECT
                "WerkbonParagraafKey" as paragraaf_key,
                "Omschrijving" as omschrijving,
                "Bedrag" as bedrag,
                "Kostensoort" as kostensoort,
                "Tarief omschrijving" as tarief,
                "Factuurdatum" as factuurdatum
            FROM financieel."Opbrengsten"
            WHERE "WerkbonParagraafKey" IN ({placeholders})
            ORDER BY "WerkbonParagraafKey", "OpbrengstRegelKey"
        """)

        try:
            result = self.db.execute(query, params)
            for row in result.fetchall():
                paragraaf_key = row[0]
                if paragraaf_key in paragraaf_map:
                    opbrengst_regel = OpbrengstRegel(
                        omschrijving=row[1] or "",
                        bedrag=float(row[2] or 0),
                        kostensoort=row[3] or "",
                        tarief=row[4] or "",
                        factuurdatum=self._format_date(row[5])
                    )
                    paragraaf_map[paragraaf_key].opbrengsten.append(opbrengst_regel)
        except Exception as e:
            print(f"Error loading opbrengsten details: {e}")

    def _load_opvolgingen(self, werkbonnen: List[Werkbon]):
        """Load opvolgingen (follow-up actions) for all paragrafen."""
        paragraaf_keys = []
        paragraaf_map = {}
        for wb in werkbonnen:
            for p in wb.paragrafen:
                paragraaf_keys.append(p.werkbonparagraaf_key)
                paragraaf_map[p.werkbonparagraaf_key] = p

        if not paragraaf_keys:
            return

        placeholders = ", ".join([f":p_{i}" for i in range(len(paragraaf_keys))])
        params = {f"p_{i}": key for i, key in enumerate(paragraaf_keys)}

        query = text(f"""
            SELECT
                "WerkbonparagraafKey" as paragraaf_key,
                "Opvolgsoort" as opvolgsoort,
                "Beschrijving" as beschrijving,
                "Status" as status,
                "Aanmaakdatum" as aanmaakdatum,
                "Laatste wijzigdatum" as laatste_wijzigdatum
            FROM werkbonnen."Opvolgingen"
            WHERE "WerkbonparagraafKey" IN ({placeholders})
            ORDER BY "WerkbonparagraafKey", "Aanmaakdatum" DESC
        """)

        try:
            result = self.db.execute(query, params)
            for row in result.fetchall():
                paragraaf_key = row[0]
                if paragraaf_key in paragraaf_map:
                    opvolging = Opvolging(
                        opvolgsoort=row[1] or "",
                        beschrijving=row[2] or "",
                        status=row[3] or "",
                        aanmaakdatum=self._format_datetime(row[4]),
                        laatste_wijzigdatum=self._format_datetime(row[5])
                    )
                    paragraaf_map[paragraaf_key].opvolgingen.append(opvolging)
        except Exception as e:
            print(f"Error loading opvolgingen: {e}")

    def _load_oplossingen(self, werkbonnen: List[Werkbon]):
        """Load oplossingen (solutions) for all paragrafen."""
        paragraaf_keys = []
        paragraaf_map = {}
        for wb in werkbonnen:
            for p in wb.paragrafen:
                paragraaf_keys.append(p.werkbonparagraaf_key)
                paragraaf_map[p.werkbonparagraaf_key] = p

        if not paragraaf_keys:
            return

        placeholders = ", ".join([f":p_{i}" for i in range(len(paragraaf_keys))])
        params = {f"p_{i}": key for i, key in enumerate(paragraaf_keys)}

        query = text(f"""
            SELECT
                "WerkbonparagraafKey" as paragraaf_key,
                "Oplossing" as oplossing,
                "Oplossing uitgebreid" as oplossing_uitgebreid,
                "Aanmaakdatum" as aanmaakdatum
            FROM werkbonnen."Oplossingen"
            WHERE "WerkbonparagraafKey" IN ({placeholders})
            ORDER BY "WerkbonparagraafKey", "Aanmaakdatum" DESC
        """)

        try:
            result = self.db.execute(query, params)
            for row in result.fetchall():
                paragraaf_key = row[0]
                if paragraaf_key in paragraaf_map:
                    oplossing = Oplossing(
                        oplossing=row[1] or "",
                        oplossing_uitgebreid=row[2],
                        aanmaakdatum=self._format_datetime(row[3])
                    )
                    paragraaf_map[paragraaf_key].oplossingen.append(oplossing)
        except Exception as e:
            print(f"Error loading oplossingen: {e}")

    def _format_date(self, dt) -> Optional[str]:
        """Format datetime to string."""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d")
        if isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
        return str(dt)

    def _format_time(self, t) -> Optional[str]:
        """Format time to string."""
        if t is None:
            return None
        if hasattr(t, 'strftime'):
            return t.strftime("%H:%M")
        return str(t)

    def _format_datetime(self, dt) -> Optional[str]:
        """Format datetime with time to string."""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
        return str(dt)

    def _extract_code(self, value: str) -> str:
        """Extract code from 'CODE - Name' format."""
        if " - " in value:
            return value.split(" - ")[0].strip()
        return value

    def _extract_name(self, value: str) -> str:
        """Extract name from 'CODE - Name' format."""
        if " - " in value:
            return value.split(" - ", 1)[1].strip()
        return value

    def close(self):
        """Close database connection."""
        self.db.close()


class WerkbonVerhaalBuilder:
    """Builds a narrative description of a werkbon chain for LLM input."""

    def build_verhaal(self, keten: WerkbonKeten, chronological: bool = True) -> str:
        """
        Build a narrative description of the werkbon chain.

        This narrative is optimized for LLM classification:
        - Clear structure with timestamps
        - Key facts highlighted
        - Financial indicators for binnen/buiten contract
        - Chronological order (newest first by default)

        Args:
            keten: The werkbon chain to describe
            chronological: If True, sort events newest first (default)
        """
        lines = []

        # Header
        lines.append(f"# Werkbonketen voor {keten.relatie_naam}")
        lines.append(f"Relatiecode: {keten.relatie_code}")
        lines.append("")

        # Summary (geen gefactureerd/opbrengsten = spieken voorkomen)
        lines.append("## Samenvatting")
        lines.append(f"- Aantal werkbonnen in keten: {keten.aantal_werkbonnen}")
        lines.append(f"- Totaal aantal paragrafen: {keten.aantal_paragrafen}")
        lines.append(f"- Totale kosten: {keten.totaal_kosten:,.2f}")
        lines.append("")

        # Sort werkbonnen by melddatum (newest first if chronological)
        werkbonnen = sorted(
            keten.werkbonnen,
            key=lambda w: w.melddatum or "",
            reverse=chronological
        )

        # Each werkbon
        for i, wb in enumerate(werkbonnen, 1):
            if wb.is_hoofdwerkbon:
                lines.append(f"## Hoofdwerkbon: {wb.werkbon_nummer}")
            else:
                lines.append(f"## Vervolgbon (niveau {wb.niveau}): {wb.werkbon_nummer}")

            # Status indicators
            lines.append(f"- **Status: {wb.status}** | Documentstatus: {wb.documentstatus}")
            if wb.administratieve_fase:
                lines.append(f"- Administratieve fase: {wb.administratieve_fase}")

            # Timestamps
            lines.append(f"- Type: {wb.type}")
            if wb.melddatum:
                melding = wb.melddatum
                if wb.meldtijd:
                    melding += f" {wb.meldtijd}"
                lines.append(f"- Melding: {melding}")
            if wb.afspraakdatum:
                lines.append(f"- Afspraakdatum: {wb.afspraakdatum}")
            if wb.opleverdatum:
                lines.append(f"- Opleverdatum: {wb.opleverdatum}")

            # Monteur and location
            if wb.monteur:
                lines.append(f"- Monteur: {wb.monteur}")
            lines.append(f"- Locatie: {wb.postcode} {wb.plaats}")

            # Paragrafen (kosten liggen op paragraaf-niveau, niet op werkbon)
            if wb.paragrafen:
                lines.append("### Werkbonparagrafen")
                for p in wb.paragrafen:
                    lines.append(f"\n**{p.naam}** ({p.type})")
                    # Factureerwijze niet tonen (bevat "binnen contract" = spieken)
                    lines.append(f"- Uitvoeringstatus: {p.uitvoeringstatus}")

                    # Timestamps
                    if p.plandatum:
                        lines.append(f"- Plandatum: {p.plandatum}")
                    if p.uitgevoerd_op:
                        uitvoering = p.uitgevoerd_op
                        if p.tijdstip_uitgevoerd:
                            uitvoering += f" {p.tijdstip_uitgevoerd}"
                        lines.append(f"- Uitgevoerd: {uitvoering}")

                    # Codes
                    if p.storing:
                        lines.append(f"- Storingscode: {p.storing}")
                    if p.oorzaak:
                        lines.append(f"- Oorzaakcode: {p.oorzaak}")

                    # Kostenregels per paragraaf (totalen staan onderaan het verhaal)
                    if p.kosten:
                        lines.append("")
                        lines.append("**Kostenregels:**")
                        for k in p.kosten:
                            # Verrekenprijs en Kostprijs zijn al totalen (aantal × eenheidsprijs)
                            cat = k.categorie.upper() if k.categorie else "ONBEKEND"
                            lines.append(f"- [{cat}] {k.omschrijving}")
                            lines.append(f"  Aantal: {k.aantal} | Verrekenprijs: {k.verrekenprijs:,.2f} | Kostprijs: {k.kostprijs:,.2f}")
                            # Extra info voor urenregels: alleen taak (medewerker niet tonen ivm AVG)
                            if k.taak:
                                lines.append(f"  Taak: {k.taak}")
                            # Alleen boekdatum tonen, geen kostenstatus/factureerstatus (spieken)
                            if k.boekdatum:
                                lines.append(f"  Boekdatum: {k.boekdatum}")

                    # Opbrengsten en facturatie-info bewust NIET tonen (spieken voorkomen)

                    # Oplossingen (solutions)
                    if p.oplossingen:
                        lines.append("")
                        lines.append("**Oplossingen:**")
                        # Sort by aanmaakdatum newest first
                        oplossingen = sorted(
                            p.oplossingen,
                            key=lambda o: o.aanmaakdatum or "",
                            reverse=chronological
                        )
                        for opl in oplossingen:
                            datum = f"[{opl.aanmaakdatum}] " if opl.aanmaakdatum else ""
                            lines.append(f"- {datum}{opl.oplossing}")
                            if opl.oplossing_uitgebreid:
                                lines.append(f"  > {opl.oplossing_uitgebreid}")

                    # Opvolgingen (follow-up actions)
                    if p.opvolgingen:
                        lines.append("")
                        lines.append("**Opvolgingen:**")
                        # Sort by aanmaakdatum newest first
                        opvolgingen = sorted(
                            p.opvolgingen,
                            key=lambda o: o.aanmaakdatum or "",
                            reverse=chronological
                        )
                        for opv in opvolgingen:
                            datum = f"[{opv.aanmaakdatum}] " if opv.aanmaakdatum else ""
                            status = f"({opv.status})" if opv.status else ""
                            lines.append(f"- {datum}**{opv.opvolgsoort}** {status}")
                            if opv.beschrijving:
                                lines.append(f"  > {opv.beschrijving}")

                lines.append("")

        return "\n".join(lines)

    def build_json_summary(self, keten: WerkbonKeten) -> Dict[str, Any]:
        """
        Build a compact JSON summary for LLM input.

        This is an alternative to the full narrative, providing
        structured data that can be combined with contract info.

        Note: gefactureerd/binnen_contract/factureerwijze bewust NIET opgenomen
        om spieken te voorkomen tijdens classificatie.
        """
        summary = {
            "keten_id": keten.hoofdwerkbon_key,
            "relatie": {
                "code": keten.relatie_code,
                "naam": keten.relatie_naam
            },
            "totalen": {
                "kosten": keten.totaal_kosten
                # gefactureerd/binnen_contract niet tonen (spieken)
            },
            "werkbonnen": []
        }

        for wb in keten.werkbonnen:
            wb_summary = {
                "nummer": wb.werkbon_nummer,
                "type": wb.type,
                "status": wb.status,
                "documentstatus": wb.documentstatus,
                "administratieve_fase": wb.administratieve_fase,
                "melddatum": wb.melddatum,
                "meldtijd": wb.meldtijd,
                "afspraakdatum": wb.afspraakdatum,
                "opleverdatum": wb.opleverdatum,
                "monteur": wb.monteur,
                "niveau": wb.niveau,
                "is_hoofdwerkbon": wb.is_hoofdwerkbon,
                "kosten": wb.totaal_kosten,
                # gefactureerd niet tonen (spieken)
                "paragrafen": []
            }

            for p in wb.paragrafen:
                p_summary = {
                    "naam": p.naam,
                    "type": p.type,
                    # factureerwijze niet tonen (bevat "binnen contract" = spieken)
                    "uitvoeringstatus": p.uitvoeringstatus,
                    "storing": p.storing,
                    "oorzaak": p.oorzaak,
                    "plandatum": p.plandatum,
                    "uitgevoerd_op": p.uitgevoerd_op,
                    "tijdstip_uitgevoerd": p.tijdstip_uitgevoerd,
                    "kosten": {
                        "totaal": p.totaal_kosten,
                        "arbeid": p.totaal_arbeid_kosten,
                        "materiaal": p.totaal_materiaal_kosten
                    },
                    # gefactureerd niet tonen (spieken)
                    "opvolgingen": [
                        {
                            "opvolgsoort": o.opvolgsoort,
                            "beschrijving": o.beschrijving,
                            "status": o.status,
                            "aanmaakdatum": o.aanmaakdatum
                        } for o in p.opvolgingen
                    ],
                    "oplossingen": [
                        {
                            "oplossing": o.oplossing,
                            "oplossing_uitgebreid": o.oplossing_uitgebreid,
                            "aanmaakdatum": o.aanmaakdatum
                        } for o in p.oplossingen
                    ]
                }
                wb_summary["paragrafen"].append(p_summary)

            summary["werkbonnen"].append(wb_summary)

        return summary
