"""Data service die werkbonnen leest uit lokale Parquet bestanden.

Deze service vervangt de database-gebaseerde WerkbonKetenService voor de
publieke versie van de contract checker. Alle data wordt gelezen uit
vooraf geëxporteerde Parquet bestanden.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

import pandas as pd


@dataclass
class KostenRegel:
    """A single cost line within a werkbonparagraaf."""
    omschrijving: str
    aantal: float
    verrekenprijs: float
    kostprijs: float
    kostenbron: str
    categorie: str
    factureerstatus: str
    kostenstatus: str
    boekdatum: Optional[str] = None
    medewerker: Optional[str] = None
    taak: Optional[str] = None

    def get_volledige_omschrijving(self) -> str:
        """Geeft omschrijving inclusief medewerker/taak voor arbeidsregels."""
        parts = [self.omschrijving]
        if self.medewerker:
            parts.append(f"Medewerker: {self.medewerker}")
        if self.taak:
            parts.append(f"Taak: {self.taak}")
        return " | ".join(parts) if len(parts) > 1 else self.omschrijving


@dataclass
class KostenRegelExtra:
    """Extra kostenregel (in JSON 'opbrengsten' genoemd, maar zijn ook kosten)."""
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
    factureerwijze: str
    storing: Optional[str]
    oorzaak: Optional[str]
    uitvoeringstatus: str
    plandatum: Optional[str] = None
    uitgevoerd_op: Optional[str] = None
    tijdstip_uitgevoerd: Optional[str] = None
    totaal_kosten: float = 0.0
    totaal_arbeid_kosten: float = 0.0
    totaal_materiaal_kosten: float = 0.0
    totaal_kostenregels: float = 0.0
    kosten: List[KostenRegel] = field(default_factory=list)
    kostenregels: List[KostenRegelExtra] = field(default_factory=list)
    opvolgingen: List[Opvolging] = field(default_factory=list)
    oplossingen: List[Oplossing] = field(default_factory=list)


@dataclass
class Werkbon:
    """A single werkbon (work order) in the chain."""
    werkbon_key: int
    werkbon_nummer: str
    type: str
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
    niveau: int
    is_hoofdwerkbon: bool
    totaal_kosten: float = 0.0
    totaal_kostenregels: float = 0.0
    paragrafen: List[WerkbonParagraaf] = field(default_factory=list)


@dataclass
class WerkbonKeten:
    """Complete werkbon chain: hoofdwerkbon + all vervolgbonnen."""
    hoofdwerkbon_key: int
    relatie_key: int
    relatie_code: str
    relatie_naam: str
    werkbonnen: List[Werkbon] = field(default_factory=list)
    totaal_kosten: float = 0.0
    totaal_kostenregels: float = 0.0
    aantal_werkbonnen: int = 0
    aantal_paragrafen: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)


class ParquetDataService:
    """Service to read werkbon data from Parquet files."""

    def __init__(self, data_dir: str = "data"):
        """Initialize with path to data directory containing Parquet files."""
        self.data_dir = Path(data_dir)
        self._load_data()

    def _load_data(self):
        """Load all Parquet files into memory."""
        print(f"Loading data from {self.data_dir}...")

        self.df_werkbonnen = pd.read_parquet(self.data_dir / "werkbonnen.parquet")
        self.df_paragrafen = pd.read_parquet(self.data_dir / "werkbonparagrafen.parquet")
        self.df_kosten = pd.read_parquet(self.data_dir / "kosten.parquet")
        self.df_kostenregels = pd.read_parquet(self.data_dir / "kostenregels.parquet")
        self.df_oplossingen = pd.read_parquet(self.data_dir / "oplossingen.parquet")
        self.df_opvolgingen = pd.read_parquet(self.data_dir / "opvolgingen.parquet")

        # Index voor snelle lookups
        self._build_indices()

        print(f"Loaded: {len(self.df_werkbonnen)} werkbonnen, "
              f"{len(self.df_paragrafen)} paragrafen")

    def _build_indices(self):
        """Build indices for fast lookups."""
        # Hoofdwerkbon keys
        self.hoofdwerkbon_keys = set(
            self.df_werkbonnen[
                self.df_werkbonnen["werkbon_key"] == self.df_werkbonnen["hoofdwerkbon_key"]
            ]["werkbon_key"].tolist()
        )

        # Group dataframes by keys for fast access
        self._werkbonnen_by_hoofdwerkbon = self.df_werkbonnen.groupby("hoofdwerkbon_key")
        self._paragrafen_by_werkbon = self.df_paragrafen.groupby("werkbon_key")
        self._kosten_by_paragraaf = self.df_kosten.groupby("werkbonparagraaf_key")
        self._kostenregels_by_paragraaf = self.df_kostenregels.groupby("werkbonparagraaf_key")

        # Handle empty DataFrames (may not have columns if no data)
        if "werkbonparagraaf_key" in self.df_oplossingen.columns:
            self._oplossingen_by_paragraaf = self.df_oplossingen.groupby("werkbonparagraaf_key")
        else:
            self._oplossingen_by_paragraaf = None

        if "werkbonparagraaf_key" in self.df_opvolgingen.columns:
            self._opvolgingen_by_paragraaf = self.df_opvolgingen.groupby("werkbonparagraaf_key")
        else:
            self._opvolgingen_by_paragraaf = None

    def get_hoofdwerkbon_list(
        self,
        debiteur_codes: List[str] = None,
        melddatum_start: str = None,
        melddatum_end: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get list of hoofdwerkbonnen for selection UI."""
        df = self.df_werkbonnen[
            self.df_werkbonnen["werkbon_key"] == self.df_werkbonnen["hoofdwerkbon_key"]
        ].copy()

        # Filter op debiteur als opgegeven
        if debiteur_codes:
            mask = df["debiteur"].apply(
                lambda x: any(code in str(x) for code in debiteur_codes)
            )
            df = df[mask]

        # Filter op melddatum als opgegeven
        if melddatum_start or melddatum_end:
            df["melddatum_str"] = df["melddatum"].astype(str).str[:10]
            if melddatum_start:
                df = df[df["melddatum_str"] >= str(melddatum_start)]
            if melddatum_end:
                df = df[df["melddatum_str"] <= str(melddatum_end)]

        # Sorteer op melddatum (nieuwste eerst)
        df = df.sort_values("melddatum", ascending=False)

        # Limit
        df = df.head(limit)

        # Tel paragrafen per werkbon
        paragraaf_counts = self.df_paragrafen.groupby("werkbon_key").size()

        result = []
        for _, row in df.iterrows():
            werkbon_code = str(row["werkbon"]).split(" - ")[0] if row["werkbon"] else ""
            result.append({
                "hoofdwerkbon_key": int(row["werkbon_key"]),
                "werkbon_document_key": int(row["werkbon_key"]),
                "werkbon": row["werkbon"],
                "werkbon_code": werkbon_code,
                "aanmaakdatum": self._format_date(row.get("aanmaakdatum")),
                "melddatum": self._format_date(row.get("melddatum")),
                "status": str(row["status"]).strip() if row["status"] else "",
                "documentstatus": str(row["documentstatus"]).strip() if row["documentstatus"] else "",
                "admin_fase": row.get("administratieve_fase") or "",
                "klant": row["klant"],
                "debiteur": row["debiteur"],
                "paragraaf_count": paragraaf_counts.get(row["werkbon_key"], 0),
            })

        return result

    def get_werkbon_keten(
        self,
        hoofdwerkbon_key: int,
        include_kosten_details: bool = False,
        include_kostenregels_details: bool = False,
        include_opvolgingen: bool = False,
        include_oplossingen: bool = False
    ) -> Optional[WerkbonKeten]:
        """Fetch a complete werkbon chain by hoofdwerkbon key."""
        hoofdwerkbon_key = int(hoofdwerkbon_key)

        # Check of deze hoofdwerkbon bestaat
        if hoofdwerkbon_key not in self.hoofdwerkbon_keys:
            return None

        # Haal alle werkbonnen in de keten
        try:
            werkbonnen_df = self._werkbonnen_by_hoofdwerkbon.get_group(hoofdwerkbon_key)
        except KeyError:
            return None

        # Bouw werkbon objecten
        werkbonnen = []
        werkbon_keys = []

        for _, wb_row in werkbonnen_df.iterrows():
            werkbon = Werkbon(
                werkbon_key=int(wb_row["werkbon_key"]),
                werkbon_nummer=str(wb_row["werkbon"]) if wb_row["werkbon"] else "",
                type=str(wb_row["type"]) if wb_row["type"] else "",
                status=str(wb_row["status"]).strip() if wb_row["status"] else "",
                documentstatus=str(wb_row["documentstatus"]).strip() if wb_row["documentstatus"] else "",
                administratieve_fase=wb_row.get("administratieve_fase"),
                klant=str(wb_row["klant"]) if wb_row["klant"] else "",
                debiteur=str(wb_row["debiteur"]) if wb_row["debiteur"] else "",
                postcode=str(wb_row["postcode"]) if wb_row["postcode"] else "",
                plaats=str(wb_row["plaats"]) if wb_row["plaats"] else "",
                melddatum=self._format_date(wb_row.get("melddatum")),
                meldtijd=self._format_time(wb_row.get("meldtijd")),
                afspraakdatum=self._format_date(wb_row.get("afspraakdatum")),
                opleverdatum=self._format_date(wb_row.get("opleverdatum")),
                monteur=wb_row.get("monteur"),
                niveau=int(wb_row.get("niveau") or 1),
                is_hoofdwerkbon=(int(wb_row["werkbon_key"]) == hoofdwerkbon_key)
            )
            werkbonnen.append(werkbon)
            werkbon_keys.append(int(wb_row["werkbon_key"]))

        # Haal paragrafen per werkbon
        for werkbon in werkbonnen:
            try:
                paragrafen_df = self._paragrafen_by_werkbon.get_group(werkbon.werkbon_key)
            except KeyError:
                continue

            for _, p_row in paragrafen_df.iterrows():
                paragraaf_key = int(p_row["werkbonparagraaf_key"])

                # Bereken totalen uit kosten
                totaal_kosten = 0.0
                totaal_arbeid = 0.0

                try:
                    kosten_df = self._kosten_by_paragraaf.get_group(paragraaf_key)
                    totaal_kosten = kosten_df["kostprijs"].sum()
                    arbeid_mask = kosten_df["is_arbeid"] == "Ja"
                    totaal_arbeid = kosten_df.loc[arbeid_mask, "kostprijs"].sum()
                except KeyError:
                    pass

                # Bereken totaal opbrengsten
                totaal_kostenregels = 0.0
                try:
                    opbr_df = self._kostenregels_by_paragraaf.get_group(paragraaf_key)
                    totaal_kostenregels = opbr_df["bedrag"].sum()
                except KeyError:
                    pass

                paragraaf = WerkbonParagraaf(
                    werkbonparagraaf_key=paragraaf_key,
                    naam=str(p_row["naam"]) if p_row["naam"] else "",
                    type=str(p_row["type"]) if p_row["type"] else "",
                    factureerwijze=str(p_row["factureerwijze"]) if p_row["factureerwijze"] else "",
                    storing=p_row.get("storing"),
                    oorzaak=p_row.get("oorzaak"),
                    uitvoeringstatus=str(p_row.get("uitvoeringstatus") or ""),
                    plandatum=self._format_date(p_row.get("plandatum")),
                    uitgevoerd_op=self._format_date(p_row.get("uitgevoerd_op")),
                    tijdstip_uitgevoerd=self._format_time(p_row.get("tijdstip_uitgevoerd")),
                    totaal_kosten=float(totaal_kosten),
                    totaal_arbeid_kosten=float(totaal_arbeid),
                    totaal_materiaal_kosten=float(totaal_kosten - totaal_arbeid),
                    totaal_kostenregels=float(totaal_kostenregels)
                )

                # Laad details indien gevraagd
                if include_kosten_details:
                    self._load_kosten_details(paragraaf)
                if include_kostenregels_details:
                    self._load_kostenregels_details(paragraaf)
                if include_opvolgingen:
                    self._load_opvolgingen(paragraaf)
                if include_oplossingen:
                    self._load_oplossingen(paragraaf)

                werkbon.paragrafen.append(paragraaf)

            # Update werkbon totalen
            werkbon.totaal_kosten = sum(p.totaal_kosten for p in werkbon.paragrafen)
            werkbon.totaal_kostenregels = sum(p.totaal_kostenregels for p in werkbon.paragrafen)

        # Haal relatie info uit eerste werkbon
        first_wb = werkbonnen[0] if werkbonnen else None
        relatie_code = ""
        relatie_naam = ""

        if first_wb and first_wb.debiteur:
            if " - " in first_wb.debiteur:
                parts = first_wb.debiteur.split(" - ", 1)
                relatie_code = parts[0].strip()
                relatie_naam = parts[1].strip() if len(parts) > 1 else ""
            else:
                relatie_naam = first_wb.debiteur

        # Bouw de keten
        keten = WerkbonKeten(
            hoofdwerkbon_key=hoofdwerkbon_key,
            relatie_key=int(werkbonnen_df.iloc[0].get("debiteur_relatie_key") or 0),
            relatie_code=relatie_code,
            relatie_naam=relatie_naam,
            werkbonnen=werkbonnen,
            totaal_kosten=sum(w.totaal_kosten for w in werkbonnen),
            totaal_kostenregels=sum(w.totaal_kostenregels for w in werkbonnen),
            aantal_werkbonnen=len(werkbonnen),
            aantal_paragrafen=sum(len(w.paragrafen) for w in werkbonnen)
        )

        return keten

    def _load_kosten_details(self, paragraaf: WerkbonParagraaf):
        """Load kosten details for a paragraaf."""
        try:
            kosten_df = self._kosten_by_paragraaf.get_group(paragraaf.werkbonparagraaf_key)
        except KeyError:
            return

        for _, k_row in kosten_df.iterrows():
            kosten_regel = KostenRegel(
                omschrijving=str(k_row["omschrijving"]) if k_row["omschrijving"] else "",
                aantal=float(k_row["aantal"] or 0),
                verrekenprijs=float(k_row["verrekenprijs"] or 0),
                kostprijs=float(k_row["kostprijs"] or 0),
                kostenbron=str(k_row["kostenbron"]).strip() if k_row["kostenbron"] else "",
                categorie=str(k_row["categorie"]).strip() if k_row["categorie"] else "",
                factureerstatus=str(k_row["factureerstatus"]) if k_row["factureerstatus"] else "",
                kostenstatus=str(k_row["kostenstatus"]) if k_row["kostenstatus"] else "",
                boekdatum=self._format_date(k_row.get("boekdatum")),
                medewerker=k_row.get("medewerker"),
                taak=k_row.get("taak")
            )
            paragraaf.kosten.append(kosten_regel)

    def _load_kostenregels_details(self, paragraaf: WerkbonParagraaf):
        """Load opbrengsten details for a paragraaf."""
        try:
            opbr_df = self._kostenregels_by_paragraaf.get_group(paragraaf.werkbonparagraaf_key)
        except KeyError:
            return

        for _, o_row in opbr_df.iterrows():
            kostenregel_extra = KostenRegelExtra(
                omschrijving=str(o_row["omschrijving"]) if o_row["omschrijving"] else "",
                bedrag=float(o_row["bedrag"] or 0),
                kostensoort=str(o_row["kostensoort"]) if o_row["kostensoort"] else "",
                tarief=str(o_row["tarief"]) if o_row["tarief"] else "",
                factuurdatum=self._format_date(o_row.get("factuurdatum"))
            )
            paragraaf.kostenregels.append(kostenregel_extra)

    def _load_opvolgingen(self, paragraaf: WerkbonParagraaf):
        """Load opvolgingen for a paragraaf."""
        if self._opvolgingen_by_paragraaf is None:
            return
        try:
            opv_df = self._opvolgingen_by_paragraaf.get_group(paragraaf.werkbonparagraaf_key)
        except KeyError:
            return

        for _, o_row in opv_df.iterrows():
            opvolging = Opvolging(
                opvolgsoort=str(o_row["opvolgsoort"]) if o_row["opvolgsoort"] else "",
                beschrijving=str(o_row["beschrijving"]) if o_row["beschrijving"] else "",
                status=str(o_row["status"]) if o_row["status"] else "",
                aanmaakdatum=self._format_datetime(o_row.get("aanmaakdatum")),
                laatste_wijzigdatum=self._format_datetime(o_row.get("laatste_wijzigdatum"))
            )
            paragraaf.opvolgingen.append(opvolging)

    def _load_oplossingen(self, paragraaf: WerkbonParagraaf):
        """Load oplossingen for a paragraaf."""
        if self._oplossingen_by_paragraaf is None:
            return
        try:
            opl_df = self._oplossingen_by_paragraaf.get_group(paragraaf.werkbonparagraaf_key)
        except KeyError:
            return

        for _, o_row in opl_df.iterrows():
            oplossing = Oplossing(
                oplossing=str(o_row["oplossing"]) if o_row["oplossing"] else "",
                oplossing_uitgebreid=o_row.get("oplossing_uitgebreid"),
                aanmaakdatum=self._format_datetime(o_row.get("aanmaakdatum"))
            )
            paragraaf.oplossingen.append(oplossing)

    def _format_date(self, dt) -> Optional[str]:
        """Format datetime to date string."""
        if dt is None or pd.isna(dt):
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d")
        if isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
        if isinstance(dt, pd.Timestamp):
            return dt.strftime("%Y-%m-%d")
        return str(dt)

    def _format_time(self, t) -> Optional[str]:
        """Format time to string."""
        if t is None or pd.isna(t):
            return None
        if hasattr(t, 'strftime'):
            return t.strftime("%H:%M")
        return str(t)

    def _format_datetime(self, dt) -> Optional[str]:
        """Format datetime with time to string."""
        if dt is None or pd.isna(dt):
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(dt, pd.Timestamp):
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
        return str(dt)

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the loaded data."""
        import json
        metadata_file = self.data_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                return json.load(f)
        return {
            "aantal_hoofdwerkbonnen": len(self.hoofdwerkbon_keys),
            "aantal_werkbonnen": len(self.df_werkbonnen),
            "aantal_paragrafen": len(self.df_paragrafen),
        }

    def close(self):
        """Compatibility method (no-op for Parquet)."""
        pass


class WerkbonVerhaalBuilder:
    """Builds a narrative description of a werkbon chain for LLM input.

    This is a copy from the original werkbon_keten_service.py to maintain
    compatibility with the public version.
    """

    def build_verhaal(self, keten: WerkbonKeten, chronological: bool = True) -> str:
        """Build a narrative description of the werkbon chain."""
        lines = []

        # Header
        lines.append(f"# Werkbonketen voor {keten.relatie_naam}")
        lines.append(f"Relatiecode: {keten.relatie_code}")
        lines.append("")

        # Summary
        lines.append("## Samenvatting")
        lines.append(f"- Aantal werkbonnen in keten: {keten.aantal_werkbonnen}")
        lines.append(f"- Totaal aantal paragrafen: {keten.aantal_paragrafen}")
        lines.append(f"- Totale kosten: €{keten.totaal_kosten:,.2f}")
        lines.append("")

        # Sort werkbonnen by melddatum
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

            lines.append(f"- **Status: {wb.status}** | Documentstatus: {wb.documentstatus}")
            if wb.administratieve_fase:
                lines.append(f"- Administratieve fase: {wb.administratieve_fase}")

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

            if wb.monteur:
                lines.append(f"- Monteur: {wb.monteur}")
            lines.append(f"- Locatie: {wb.postcode} {wb.plaats}")

            # Paragrafen
            if wb.paragrafen:
                lines.append("### Werkbonparagrafen")
                for p in wb.paragrafen:
                    lines.append(f"\n**{p.naam}** ({p.type})")
                    lines.append(f"- Uitvoeringstatus: {p.uitvoeringstatus}")

                    if p.plandatum:
                        lines.append(f"- Plandatum: {p.plandatum}")
                    if p.uitgevoerd_op:
                        uitvoering = p.uitgevoerd_op
                        if p.tijdstip_uitgevoerd:
                            uitvoering += f" {p.tijdstip_uitgevoerd}"
                        lines.append(f"- Uitgevoerd: {uitvoering}")

                    if p.storing:
                        lines.append(f"- Storingscode: {p.storing}")
                    if p.oorzaak:
                        lines.append(f"- Oorzaakcode: {p.oorzaak}")

                    # Kostenregels
                    if p.kosten:
                        lines.append("")
                        lines.append("**Kostenregels:**")
                        for k in p.kosten:
                            cat = k.categorie.upper() if k.categorie else "ONBEKEND"
                            lines.append(f"- [{cat}] {k.omschrijving}")
                            lines.append(f"  Aantal: {k.aantal} | Verrekenprijs: €{k.verrekenprijs:,.2f} | Kostprijs: €{k.kostprijs:,.2f}")
                            if k.taak:
                                lines.append(f"  Taak: {k.taak}")
                            if k.boekdatum:
                                lines.append(f"  Boekdatum: {k.boekdatum}")

                    # Oplossingen
                    if p.oplossingen:
                        lines.append("")
                        lines.append("**Oplossingen:**")
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

                    # Opvolgingen
                    if p.opvolgingen:
                        lines.append("")
                        lines.append("**Opvolgingen:**")
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
