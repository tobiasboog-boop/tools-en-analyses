const BASE_URL = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// DWH endpoints
export const dwhApi = {
  getHoofdprojecten: (klantnummer: number) =>
    request<any[]>(`/dwh/${klantnummer}/hoofdprojecten`),

  getDeelprojecten: (klantnummer: number, hoofdprojectKey: number) =>
    request<any[]>(`/dwh/${klantnummer}/deelprojecten/${hoofdprojectKey}`),

  getProjectdata: (klantnummer: number, hoofdprojectKey: number) =>
    request<any[]>(`/dwh/${klantnummer}/projectdata/${hoofdprojectKey}`),
}

// Opname endpoints
export const opnameApi = {
  list: (klantnummer: number) =>
    request<any[]>(`/opnames/${klantnummer}`),

  get: (klantnummer: number, opnameKey: number) =>
    request<any>(`/opnames/${klantnummer}/${opnameKey}`),

  create: (klantnummer: number, data: any) =>
    request<any>(`/opnames/${klantnummer}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (klantnummer: number, opnameKey: number, data: any) =>
    request<any>(`/opnames/${klantnummer}/${opnameKey}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (klantnummer: number, opnameKey: number) =>
    request<void>(`/opnames/${klantnummer}/${opnameKey}`, { method: 'DELETE' }),
}

// Regels endpoints
export const regelApi = {
  list: (klantnummer: number, opnameKey: number) =>
    request<any[]>(`/opnames/${klantnummer}/${opnameKey}/regels`),

  populate: (klantnummer: number, opnameKey: number) =>
    request<any[]>(`/opnames/${klantnummer}/${opnameKey}/regels/populate`, {
      method: 'POST',
    }),

  batchUpdate: (klantnummer: number, opnameKey: number, regels: any[]) =>
    request<any>(`/opnames/${klantnummer}/${opnameKey}/regels/batch`, {
      method: 'PUT',
      body: JSON.stringify({ regels }),
    }),
}

// Berekening endpoints
export const berekeningApi = {
  bereken: (klantnummer: number, opnameKey: number) =>
    request<any>(`/opnames/${klantnummer}/${opnameKey}/bereken`, {
      method: 'POST',
    }),

  opslaan: (klantnummer: number, opnameKey: number) =>
    request<any>(`/opnames/${klantnummer}/${opnameKey}/opslaan`, {
      method: 'POST',
    }),
}
