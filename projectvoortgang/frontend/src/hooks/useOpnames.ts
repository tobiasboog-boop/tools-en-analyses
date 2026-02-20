import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { opnameApi, regelApi, berekeningApi } from '../services/api'
import type { Projectopname, Opnameregel, RegelUpdate } from '../types/opname'

export function useOpnames(klantnummer: number) {
  return useQuery<Projectopname[]>({
    queryKey: ['opnames', klantnummer],
    queryFn: () => opnameApi.list(klantnummer),
  })
}

export function useOpname(klantnummer: number, opnameKey: number) {
  return useQuery<Projectopname>({
    queryKey: ['opname', klantnummer, opnameKey],
    queryFn: () => opnameApi.get(klantnummer, opnameKey),
    enabled: !!opnameKey,
  })
}

export function useCreateOpname(klantnummer: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => opnameApi.create(klantnummer, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['opnames', klantnummer] }),
  })
}

export function useDeleteOpname(klantnummer: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (opnameKey: number) => opnameApi.delete(klantnummer, opnameKey),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['opnames', klantnummer] }),
  })
}

export function useRegels(klantnummer: number, opnameKey: number) {
  return useQuery<Opnameregel[]>({
    queryKey: ['regels', klantnummer, opnameKey],
    queryFn: () => regelApi.list(klantnummer, opnameKey),
    enabled: !!opnameKey,
  })
}

export function usePopulateRegels(klantnummer: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (opnameKey: number) => regelApi.populate(klantnummer, opnameKey),
    onSuccess: (_data, opnameKey) => {
      qc.invalidateQueries({ queryKey: ['regels', klantnummer, opnameKey] })
    },
  })
}

export function useBatchUpdateRegels(klantnummer: number, opnameKey: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (regels: RegelUpdate[]) =>
      regelApi.batchUpdate(klantnummer, opnameKey, regels),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['regels', klantnummer, opnameKey] })
      qc.invalidateQueries({ queryKey: ['opname', klantnummer, opnameKey] })
    },
  })
}

export function useBereken(klantnummer: number, opnameKey: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => berekeningApi.bereken(klantnummer, opnameKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opname', klantnummer, opnameKey] })
    },
  })
}

export function useOpslaan(klantnummer: number, opnameKey: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => berekeningApi.opslaan(klantnummer, opnameKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opname', klantnummer, opnameKey] })
      qc.invalidateQueries({ queryKey: ['opnames', klantnummer] })
    },
  })
}
