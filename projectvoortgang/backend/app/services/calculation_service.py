"""Core business logic for projectvoortgang calculations.

Calculation flow:
1. Resolve calculatie (budget) based on grondslag_calculatie_kosten
2. Resolve geboekt (realized) based on grondslag_geboekte_kosten
3. TMB = percentage_gereed * calculatie / 100 (per regel, then summed)
4. Verschil huidige stand = Geboekt - TMB
5. Gemiddeld PG = weighted average of PG, weighted by calculatie
6. Verschil einde project = projected end-of-project variance
7. Onder/Bovengrens = TMB-based bounds
"""

from app.models.projectopname import Projectopname, Projectopnameregel


class CalculationService:

    def resolve_calculatie(self, opname: Projectopname, regels: list[Projectopnameregel]) -> None:
        """Map raw DWH costs to 'calculatie' based on grondslag selection."""
        if opname.grondslag_calculatie_kosten == "Kostprijs":
            opname.calculatie_inkoop = float(opname.calculatie_kostprijs_inkoop or 0)
            opname.calculatie_montage = float(opname.calculatie_kostprijs_arbeid_montage or 0)
            opname.calculatie_projectgebonden = float(opname.calculatie_kostprijs_arbeid_projectgebonden or 0)
        else:  # Verrekenprijs
            opname.calculatie_inkoop = float(opname.calculatie_verrekenprijs_inkoop or 0)
            opname.calculatie_montage = float(opname.calculatie_verrekenprijs_arbeid_montage or 0)
            opname.calculatie_projectgebonden = float(opname.calculatie_verrekenprijs_arbeid_projectgebonden or 0)

    def resolve_geboekt(self, opname: Projectopname, regels: list[Projectopnameregel]) -> None:
        """Map raw DWH costs to 'geboekt' based on grondslag selection."""
        grondslag = opname.grondslag_geboekte_kosten or ""

        if "definitief + onverwerkt" in grondslag.lower():
            opname.geboekt_inkoop = float(opname.definitieve_verrekenprijs_inkoop or 0) + float(opname.onverwerkte_verrekenprijs_inkoop or 0)
            opname.geboekt_montage = float(opname.definitieve_verrekenprijs_arbeid_montage or 0) + float(opname.onverwerkte_verrekenprijs_arbeid_montage or 0)
            opname.geboekt_projectgebonden = float(opname.definitieve_verrekenprijs_arbeid_projectgebonden or 0) + float(opname.onverwerkte_verrekenprijs_arbeid_projectgebonden or 0)
        elif "definitief" in grondslag.lower() and "verrekenprijs" in grondslag.lower():
            opname.geboekt_inkoop = float(opname.definitieve_verrekenprijs_inkoop or 0)
            opname.geboekt_montage = float(opname.definitieve_verrekenprijs_arbeid_montage or 0)
            opname.geboekt_projectgebonden = float(opname.definitieve_verrekenprijs_arbeid_projectgebonden or 0)
        else:  # Kostprijs (definitief)
            opname.geboekt_inkoop = float(opname.definitieve_kostprijs_inkoop or 0)
            opname.geboekt_montage = float(opname.definitieve_kostprijs_arbeid_montage or 0)
            opname.geboekt_projectgebonden = float(opname.definitieve_kostprijs_arbeid_projectgebonden or 0)

        # Geboekte uren = definitief + onverwerkt (always)
        opname.geboekt_montage_uren = float(opname.montage_uren_definitief or 0) + float(opname.montage_uren_onverwerkt or 0)
        opname.geboekt_projectgebonden_uren = float(opname.projectgebonden_uren_definitief or 0) + float(opname.projectgebonden_uren_onverwerkt or 0)

    def calculate_tmb(self, opname: Projectopname, regels: list[Projectopnameregel]) -> None:
        """TMB (Te Mogen Besteden) = SUM(PG * calculatie / 100) per category."""
        tmb_inkoop = 0.0
        tmb_montage = 0.0
        tmb_pg = 0.0
        tmb_montage_uren = 0.0
        tmb_pg_uren = 0.0

        for r in regels:
            pg_ink = float(r.percentage_gereed_inkoop or 0)
            pg_mon = float(r.percentage_gereed_arbeid_montage or 0)
            pg_prj = float(r.percentage_gereed_arbeid_projectgebonden or 0)

            tmb_inkoop += pg_ink / 100 * float(r.calculatie_kosten_inkoop or 0)
            tmb_montage += pg_mon / 100 * float(r.calculatie_kosten_arbeid_montage or 0)
            tmb_pg += pg_prj / 100 * float(r.calculatie_kosten_arbeid_projectgebonden or 0)
            tmb_montage_uren += pg_mon / 100 * float(r.calculatie_montage_uren or 0)
            tmb_pg_uren += pg_prj / 100 * float(r.calculatie_projectgebonden_uren or 0)

        opname.tmb_inkoop = round(tmb_inkoop, 2)
        opname.tmb_montage = round(tmb_montage, 2)
        opname.tmb_projectgebonden = round(tmb_pg, 2)
        opname.tmb_montage_uren = round(tmb_montage_uren, 2)
        opname.tmb_projectgebonden_uren = round(tmb_pg_uren, 2)

    def calculate_verschil_huidige_stand(self, opname: Projectopname) -> None:
        """Verschil huidige stand = Geboekt - TMB per category."""
        opname.verschil_inkoop_huidige_stand = round(float(opname.geboekt_inkoop or 0) - float(opname.tmb_inkoop or 0), 2)
        opname.verschil_montage_huidige_stand = round(float(opname.geboekt_montage or 0) - float(opname.tmb_montage or 0), 2)
        opname.verschil_projectgebonden_huidige_stand = round(float(opname.geboekt_projectgebonden or 0) - float(opname.tmb_projectgebonden or 0), 2)
        opname.verschil_montage_uren_huidige_stand = round(float(opname.geboekt_montage_uren or 0) - float(opname.tmb_montage_uren or 0), 2)
        opname.verschil_projectgebonden_uren_huidige_stand = round(float(opname.geboekt_projectgebonden_uren or 0) - float(opname.tmb_projectgebonden_uren or 0), 2)

    def calculate_gemiddeld_pg(self, opname: Projectopname, regels: list[Projectopnameregel]) -> None:
        """Weighted average PG = SUM(PG_i * Calculatie_i) / SUM(Calculatie_i)."""
        sum_weighted_inkoop = 0.0
        sum_calc_inkoop = 0.0
        sum_weighted_montage = 0.0
        sum_calc_montage = 0.0
        sum_weighted_pg = 0.0
        sum_calc_pg = 0.0

        for r in regels:
            calc_ink = float(r.calculatie_kosten_inkoop or 0)
            calc_mon = float(r.calculatie_kosten_arbeid_montage or 0)
            calc_prj = float(r.calculatie_kosten_arbeid_projectgebonden or 0)

            sum_weighted_inkoop += float(r.percentage_gereed_inkoop or 0) * calc_ink
            sum_calc_inkoop += calc_ink
            sum_weighted_montage += float(r.percentage_gereed_arbeid_montage or 0) * calc_mon
            sum_calc_montage += calc_mon
            sum_weighted_pg += float(r.percentage_gereed_arbeid_projectgebonden or 0) * calc_prj
            sum_calc_pg += calc_prj

        opname.gemiddeld_pg_inkoop = round(sum_weighted_inkoop / sum_calc_inkoop, 2) if sum_calc_inkoop else 0
        opname.gemiddeld_pg_montage = round(sum_weighted_montage / sum_calc_montage, 2) if sum_calc_montage else 0
        opname.gemiddeld_pg_projectgebonden = round(sum_weighted_pg / sum_calc_pg, 2) if sum_calc_pg else 0

        # Total weighted average across all categories
        total_weighted = sum_weighted_inkoop + sum_weighted_montage + sum_weighted_pg
        total_calc = sum_calc_inkoop + sum_calc_montage + sum_calc_pg
        opname.gemiddeld_pg_totaal = round(total_weighted / total_calc, 2) if total_calc else 0

    def calculate_verschil_einde_project(self, opname: Projectopname) -> None:
        """Projected end-of-project variance.

        If PG > 0: projected_total = geboekt / (PG/100)
        Verschil = projected_total - calculatie
        This estimates: at the current rate of spending, what will the total cost be?
        """
        for cat in ["inkoop", "montage", "projectgebonden"]:
            pg = float(getattr(opname, f"gemiddeld_pg_{cat}") or 0)
            geboekt = float(getattr(opname, f"geboekt_{cat}") or 0)
            calculatie = float(getattr(opname, f"calculatie_{cat}") or 0)
            verzoeken = float(getattr(opname, f"historische_verzoeken_{cat}") or 0)

            if pg > 0:
                projected = geboekt / (pg / 100)
                verschil = round(projected - calculatie - verzoeken, 2)
            else:
                verschil = 0

            setattr(opname, f"verschil_{cat}_einde_project", verschil)

        # Uren
        for cat in ["montage", "projectgebonden"]:
            pg = float(getattr(opname, f"gemiddeld_pg_{cat}") or 0)
            geboekt_uren = float(getattr(opname, f"geboekt_{cat}_uren") or 0)
            calc_uren = float(getattr(opname, f"calculatie_{cat}_uren") or 0)
            verzoeken_uren = float(getattr(opname, f"historische_verzoeken_{cat}_uren") or 0)

            if pg > 0:
                projected = geboekt_uren / (pg / 100)
                verschil = round(projected - calc_uren - verzoeken_uren, 2)
            else:
                verschil = 0

            setattr(opname, f"verschil_{cat}_uren_einde_project", verschil)

    def calculate_grenzen(self, opname: Projectopname) -> None:
        """Onder/bovengrens calculations.

        Ondergrens (lower bound) = TMB * 0.9 (conservative: 10% less than TMB)
        Bovengrens (upper bound) = TMB * 1.1 (optimistic: 10% more than TMB)

        NOTE: The actual Power Apps may use different margin factors.
        These should be made configurable per tenant.
        """
        margin = 0.10  # 10% margin

        for cat in ["inkoop", "montage", "projectgebonden"]:
            tmb = float(getattr(opname, f"tmb_{cat}") or 0)
            setattr(opname, f"ondergrens_{cat}", round(tmb * (1 - margin), 2))
            setattr(opname, f"bovengrens_{cat}", round(tmb * (1 + margin), 2))

        for cat in ["montage", "projectgebonden"]:
            tmb_uren = float(getattr(opname, f"tmb_{cat}_uren") or 0)
            setattr(opname, f"ondergrens_{cat}_uren", round(tmb_uren * (1 - margin), 2))
            setattr(opname, f"bovengrens_{cat}_uren", round(tmb_uren * (1 + margin), 2))

    def recalculate_all(self, opname: Projectopname, regels: list[Projectopnameregel]) -> None:
        """Run full recalculation pipeline."""
        self.resolve_calculatie(opname, regels)
        self.resolve_geboekt(opname, regels)
        self.calculate_tmb(opname, regels)
        self.calculate_verschil_huidige_stand(opname)
        self.calculate_gemiddeld_pg(opname, regels)
        self.calculate_verschil_einde_project(opname)
        self.calculate_grenzen(opname)
