export interface DWHHoofdproject {
  project_key: number
  project_naam: string
  projectfase: string | null
  projectniveau: number
  start_boekdatum: string | null
  einde_boekdatum: string | null
}

export interface DWHDeelproject {
  project_key: number
  project_naam: string
  projectfase: string | null
  projectniveau: number
  hoofdproject_key: number
}
