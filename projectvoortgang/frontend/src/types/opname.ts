export interface Projectopname {
  projectopname_key: number
  klantnummer: number
  hoofdproject_key: number
  hoofdproject: string | null
  hoogst_geselecteerd_projectniveau: number | null
  start_boekdatum: string | null
  einde_boekdatum: string | null
  grondslag_calculatie_kosten: string | null
  grondslag_geboekte_kosten: string | null
  groepering_paragraafniveau: number | null

  // Resolved
  calculatie_inkoop: number
  calculatie_montage: number
  calculatie_projectgebonden: number
  geboekt_inkoop: number
  geboekt_montage: number
  geboekt_projectgebonden: number
  geboekt_montage_uren: number
  geboekt_projectgebonden_uren: number

  // TMB
  tmb_inkoop: number
  tmb_montage: number
  tmb_projectgebonden: number
  tmb_montage_uren: number
  tmb_projectgebonden_uren: number

  // Verschil
  verschil_inkoop_huidige_stand: number
  verschil_montage_huidige_stand: number
  verschil_projectgebonden_huidige_stand: number

  // Gemiddeld PG
  gemiddeld_pg_inkoop: number
  gemiddeld_pg_montage: number
  gemiddeld_pg_projectgebonden: number
  gemiddeld_pg_totaal: number

  // Verschil einde project
  verschil_inkoop_einde_project: number
  verschil_montage_einde_project: number
  verschil_projectgebonden_einde_project: number

  // Grenzen
  ondergrens_inkoop: number
  ondergrens_montage: number
  ondergrens_projectgebonden: number
  bovengrens_inkoop: number
  bovengrens_montage: number
  bovengrens_projectgebonden: number

  // Historische verzoeken
  historische_verzoeken_inkoop: number
  historische_verzoeken_montage: number
  historische_verzoeken_projectgebonden: number

  // Status
  autorisatie_status: string
  opgeslagen: boolean
  opmerking: string | null

  // Audit
  aanmaakdatum: string
  aanmaker: string
  wijzigdatum: string
  wijziger: string
}

export interface ProjectopnameCreate {
  hoofdproject_key: number
  hoofdproject?: string
  start_boekdatum?: string
  einde_boekdatum?: string
  grondslag_calculatie_kosten: string
  grondslag_geboekte_kosten: string
  groepering_paragraafniveau?: number
}

export interface Opnameregel {
  regel_key: number
  projectopname_key: number
  klantnummer: number
  project_key: number | null
  project: string | null
  projectniveau: number | null
  projectfase: string | null
  deelproject_jn: string
  bestekparagraaf_key: number | null
  bestekparagraaf: string | null
  bestekparagraafniveau: number | null

  calculatie_kosten_inkoop: number
  calculatie_kosten_arbeid_montage: number
  calculatie_kosten_arbeid_projectgebonden: number
  calculatie_montage_uren: number
  calculatie_projectgebonden_uren: number

  geboekte_kosten_inkoop: number
  geboekte_kosten_arbeid_montage: number
  geboekte_kosten_arbeid_projectgebonden: number
  montage_uren: number
  projectgebonden_uren: number

  laatste_pg_inkoop: number | null
  laatste_pg_montage: number | null
  laatste_pg_projectgebonden: number | null

  percentage_gereed_inkoop: number
  percentage_gereed_arbeid_montage: number
  percentage_gereed_arbeid_projectgebonden: number
}

export interface RegelUpdate {
  regel_key: number
  percentage_gereed_inkoop?: number
  percentage_gereed_arbeid_montage?: number
  percentage_gereed_arbeid_projectgebonden?: number
}
