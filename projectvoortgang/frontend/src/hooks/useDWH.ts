import { useQuery } from '@tanstack/react-query'
import { dwhApi } from '../services/api'
import type { DWHHoofdproject } from '../types/dwh'

export function useHoofdprojecten(klantnummer: number) {
  return useQuery<DWHHoofdproject[]>({
    queryKey: ['dwh', 'hoofdprojecten', klantnummer],
    queryFn: () => dwhApi.getHoofdprojecten(klantnummer),
  })
}

export function useDeelprojecten(klantnummer: number, hoofdprojectKey: number) {
  return useQuery({
    queryKey: ['dwh', 'deelprojecten', klantnummer, hoofdprojectKey],
    queryFn: () => dwhApi.getDeelprojecten(klantnummer, hoofdprojectKey),
    enabled: !!hoofdprojectKey,
  })
}
