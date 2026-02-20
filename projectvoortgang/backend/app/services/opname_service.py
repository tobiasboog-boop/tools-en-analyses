"""Service for creating and populating opnames from DWH data."""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.dwh_interface import DWHReader
from app.models.projectopname import Projectopname, Projectopnameregel


class OpnameService:

    def populate_regels(
        self,
        db: Session,
        opname: Projectopname,
        dwh: DWHReader,
    ) -> list[Projectopnameregel]:
        """Populate detail lines from DWH based on opname settings.

        Groups DWH rows by bestekparagraaf (paragraaf mode) or
        by deelproject, depending on configuration.
        """
        # Fetch raw data from DWH
        raw_data = dwh.get_projectdata(
            klantnummer=opname.klantnummer,
            hoofdproject_key=opname.hoofdproject_key,
            start_boekdatum=opname.start_boekdatum,
            einde_boekdatum=opname.einde_boekdatum,
        )

        if not raw_data:
            return []

        # Delete existing regels for this opname
        db.query(Projectopnameregel).filter(
            Projectopnameregel.projectopname_key == opname.projectopname_key
        ).delete()

        grondslag_calc = opname.grondslag_calculatie_kosten or "Kostprijs"
        grondslag_geboekt = opname.grondslag_geboekte_kosten or "Kostprijs (definitief)"

        # Group by bestekparagraaf (paragraaf mode)
        paragraaf_groups: dict[int, list[dict]] = defaultdict(list)
        for row in raw_data:
            bp_key = row.get("bestekparagraaf_key")
            if bp_key:
                paragraaf_groups[bp_key].append(row)

        regels = []
        for bp_key, rows in paragraaf_groups.items():
            regel = self._create_regel_from_group(
                opname=opname,
                rows=rows,
                bp_key=bp_key,
                bp_naam=rows[0].get("bestekparagraaf", ""),
                bp_niveau=rows[0].get("bestekparagraafniveau"),
                deelproject_jn="N",
                grondslag_calc=grondslag_calc,
                grondslag_geboekt=grondslag_geboekt,
            )
            db.add(regel)
            regels.append(regel)

        # Also create deelproject rows
        project_groups: dict[int, list[dict]] = defaultdict(list)
        for row in raw_data:
            pk = row.get("project_key")
            niveau = row.get("projectniveau", 1)
            if pk and niveau > 1:
                project_groups[pk].append(row)

        for pk, rows in project_groups.items():
            regel = self._create_regel_from_group(
                opname=opname,
                rows=rows,
                bp_key=None,
                bp_naam=None,
                bp_niveau=None,
                deelproject_jn="J",
                grondslag_calc=grondslag_calc,
                grondslag_geboekt=grondslag_geboekt,
                project_key=pk,
                project_naam=rows[0].get("project_naam", ""),
                projectniveau=rows[0].get("projectniveau"),
                projectfase=rows[0].get("projectfase"),
            )
            db.add(regel)
            regels.append(regel)

        # Update header aggregates
        self._update_header_aggregates(opname, raw_data, grondslag_geboekt)

        db.commit()
        for r in regels:
            db.refresh(r)
        return regels

    def _create_regel_from_group(
        self,
        opname: Projectopname,
        rows: list[dict],
        bp_key: int | None,
        bp_naam: str | None,
        bp_niveau: int | None,
        deelproject_jn: str,
        grondslag_calc: str,
        grondslag_geboekt: str,
        project_key: int | None = None,
        project_naam: str | None = None,
        projectniveau: int | None = None,
        projectfase: str | None = None,
    ) -> Projectopnameregel:
        """Create a single opnameregel by aggregating a group of DWH rows."""

        def _sum(field: str) -> float:
            return sum(float(r.get(field, 0) or 0) for r in rows)

        # Resolve calculatie kosten based on grondslag
        if grondslag_calc == "Kostprijs":
            calc_inkoop = _sum("calculatie_kostprijs_inkoop")
            calc_montage = _sum("calculatie_kostprijs_arbeid_montage")
            calc_pg = _sum("calculatie_kostprijs_arbeid_projectgebonden")
        else:
            calc_inkoop = _sum("calculatie_verrekenprijs_inkoop")
            calc_montage = _sum("calculatie_verrekenprijs_arbeid_montage")
            calc_pg = _sum("calculatie_verrekenprijs_arbeid_projectgebonden")

        # Resolve geboekte kosten based on grondslag
        if "definitief + onverwerkt" in grondslag_geboekt.lower():
            geb_inkoop = _sum("definitieve_verrekenprijs_inkoop") + _sum("onverwerkte_verrekenprijs_inkoop")
            geb_montage = _sum("definitieve_verrekenprijs_arbeid_montage") + _sum("onverwerkte_verrekenprijs_arbeid_montage")
            geb_pg = _sum("definitieve_verrekenprijs_arbeid_projectgebonden") + _sum("onverwerkte_verrekenprijs_arbeid_projectgebonden")
        elif "definitief" in grondslag_geboekt.lower() and "verrekenprijs" in grondslag_geboekt.lower():
            geb_inkoop = _sum("definitieve_verrekenprijs_inkoop")
            geb_montage = _sum("definitieve_verrekenprijs_arbeid_montage")
            geb_pg = _sum("definitieve_verrekenprijs_arbeid_projectgebonden")
        else:
            geb_inkoop = _sum("definitieve_kostprijs_inkoop")
            geb_montage = _sum("definitieve_kostprijs_arbeid_montage")
            geb_pg = _sum("definitieve_kostprijs_arbeid_projectgebonden")

        return Projectopnameregel(
            projectopname_key=opname.projectopname_key,
            klantnummer=opname.klantnummer,
            deelproject_jn=deelproject_jn,
            bestekparagraaf_key=bp_key,
            bestekparagraaf=bp_naam,
            bestekparagraafniveau=bp_niveau,
            project_key=project_key,
            project=project_naam,
            projectniveau=projectniveau,
            projectfase=projectfase,
            # Calculatie
            calculatie_kosten_inkoop=calc_inkoop,
            calculatie_kosten_arbeid_montage=calc_montage,
            calculatie_kosten_arbeid_projectgebonden=calc_pg,
            calculatie_montage_uren=_sum("calculatie_montage_uren"),
            calculatie_projectgebonden_uren=_sum("calculatie_projectgebonden_uren"),
            calculatie_kostprijs_inkoop=_sum("calculatie_kostprijs_inkoop"),
            calculatie_kostprijs_arbeid_montage=_sum("calculatie_kostprijs_arbeid_montage"),
            calculatie_kostprijs_arbeid_projectgebonden=_sum("calculatie_kostprijs_arbeid_projectgebonden"),
            # Geboekt
            geboekte_kosten_inkoop=geb_inkoop,
            geboekte_kosten_arbeid_montage=geb_montage,
            geboekte_kosten_arbeid_projectgebonden=geb_pg,
            montage_uren=_sum("montage_uren_definitief") + _sum("montage_uren_onverwerkt"),
            projectgebonden_uren=_sum("projectgebonden_uren_definitief") + _sum("projectgebonden_uren_onverwerkt"),
            # Verzoeken
            verzoeken_inkoop=_sum("historische_verzoeken_inkoop"),
            verzoeken_montage=_sum("historische_verzoeken_montage"),
            verzoeken_projectgebonden=_sum("historische_verzoeken_projectgebonden"),
            verzoeken_montage_uren=_sum("historische_verzoeken_montage_uren"),
            verzoeken_projectgebonden_uren=_sum("historische_verzoeken_projectgebonden_uren"),
            # PG starts at 0
            percentage_gereed_inkoop=0,
            percentage_gereed_arbeid_montage=0,
            percentage_gereed_arbeid_projectgebonden=0,
        )

    def _update_header_aggregates(
        self, opname: Projectopname, raw_data: list[dict], grondslag_geboekt: str
    ) -> None:
        """Sum all raw DWH data into the opname header aggregates."""

        def _sum(field: str) -> float:
            return sum(float(r.get(field, 0) or 0) for r in raw_data)

        opname.calculatie_kostprijs_inkoop = _sum("calculatie_kostprijs_inkoop")
        opname.calculatie_kostprijs_arbeid_montage = _sum("calculatie_kostprijs_arbeid_montage")
        opname.calculatie_kostprijs_arbeid_projectgebonden = _sum("calculatie_kostprijs_arbeid_projectgebonden")
        opname.calculatie_verrekenprijs_inkoop = _sum("calculatie_verrekenprijs_inkoop")
        opname.calculatie_verrekenprijs_arbeid_montage = _sum("calculatie_verrekenprijs_arbeid_montage")
        opname.calculatie_verrekenprijs_arbeid_projectgebonden = _sum("calculatie_verrekenprijs_arbeid_projectgebonden")
        opname.calculatie_montage_uren = _sum("calculatie_montage_uren")
        opname.calculatie_projectgebonden_uren = _sum("calculatie_projectgebonden_uren")
        opname.definitieve_kostprijs_inkoop = _sum("definitieve_kostprijs_inkoop")
        opname.definitieve_kostprijs_arbeid_montage = _sum("definitieve_kostprijs_arbeid_montage")
        opname.definitieve_kostprijs_arbeid_projectgebonden = _sum("definitieve_kostprijs_arbeid_projectgebonden")
        opname.definitieve_verrekenprijs_inkoop = _sum("definitieve_verrekenprijs_inkoop")
        opname.definitieve_verrekenprijs_arbeid_montage = _sum("definitieve_verrekenprijs_arbeid_montage")
        opname.definitieve_verrekenprijs_arbeid_projectgebonden = _sum("definitieve_verrekenprijs_arbeid_projectgebonden")
        opname.onverwerkte_verrekenprijs_inkoop = _sum("onverwerkte_verrekenprijs_inkoop")
        opname.onverwerkte_verrekenprijs_arbeid_montage = _sum("onverwerkte_verrekenprijs_arbeid_montage")
        opname.onverwerkte_verrekenprijs_arbeid_projectgebonden = _sum("onverwerkte_verrekenprijs_arbeid_projectgebonden")
        opname.montage_uren_definitief = _sum("montage_uren_definitief")
        opname.montage_uren_onverwerkt = _sum("montage_uren_onverwerkt")
        opname.projectgebonden_uren_definitief = _sum("projectgebonden_uren_definitief")
        opname.projectgebonden_uren_onverwerkt = _sum("projectgebonden_uren_onverwerkt")
        opname.historische_verzoeken_inkoop = _sum("historische_verzoeken_inkoop")
        opname.historische_verzoeken_montage = _sum("historische_verzoeken_montage")
        opname.historische_verzoeken_projectgebonden = _sum("historische_verzoeken_projectgebonden")
        opname.historische_verzoeken_montage_uren = _sum("historische_verzoeken_montage_uren")
        opname.historische_verzoeken_projectgebonden_uren = _sum("historische_verzoeken_projectgebonden_uren")
