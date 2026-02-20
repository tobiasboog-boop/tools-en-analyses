# LLM Configuration - API Integration for React Frontend

## Overview

Dit document beschrijft hoe het LLM configuratie systeem ontworpen is voor gebruik met een toekomstige React frontend. Het systeem is volledig API-first en kan gebruikt worden door:
- **Huidige:** Streamlit Contract Checker app (Python backend)
- **Toekomst:** Centrale React app met uniforme look & feel

---

## Architectuur: API-First Design

```
┌─────────────────────────────────────────────────────────┐
│              Frontend Layer                             │
│  ┌──────────────────┐      ┌──────────────────┐        │
│  │   Streamlit UI   │      │    React App     │        │
│  │   (huidig)       │      │   (toekomst)     │        │
│  └────────┬─────────┘      └────────┬─────────┘        │
└───────────┼──────────────────────────┼──────────────────┘
            │                          │
            └──────────┬───────────────┘
                       │ REST API / Direct DB
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Supabase Layer                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │   LLM Configuration Tables                      │   │
│  │   - llm_configurations                          │   │
│  │   - llm_usage_logs                              │   │
│  │   - llm_usage_summary                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │   Supabase Edge Functions (optioneel)           │   │
│  │   - POST /api/llm/generate                      │   │
│  │   - GET  /api/llm/configs                       │   │
│  │   - GET  /api/llm/usage                         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Provider Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Anthropic │  │ Mistral  │  │ OpenAI   │  │ Local  │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Toegangsmethoden

### Methode 1: Direct Database Access (Huidig - Python)

**Huidige Streamlit app:**
```python
from src.services.llm_service import get_llm_service

llm = get_llm_service()
response = llm.generate(
    system_prompt="...",
    user_message="...",
    action_type="werkbon_classification"
)
```

**Voordeel:** Geen extra API layer nodig
**Nadeel:** Alleen Python-gebaseerde apps

---

### Methode 2: Supabase Client Library (React Ready)

**Toekomstige React app:**
```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Ophalen configuratie
const { data: configs } = await supabase
  .from('llm_configurations')
  .select('*')
  .eq('action_type', 'werkbon_classification')
  .eq('is_active', true)
  .order('priority', { ascending: false })
  .limit(1)

// Logging usage
const { data: log } = await supabase
  .from('llm_usage_logs')
  .insert({
    action_type: 'werkbon_classification',
    provider: 'mistral',
    model_name: 'mistral-large-latest',
    input_tokens: 2500,
    output_tokens: 150,
    input_cost: 0.002,
    output_cost: 0.00036,
    latency_ms: 1250,
    success: true
  })
```

**Voordeel:** Direct database access, real-time updates
**Nadeel:** LLM calls nog steeds via eigen backend

---

### Methode 3: Supabase Edge Functions (Aanbevolen voor React)

**Edge Function: `/functions/llm-generate/index.ts`**

```typescript
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import Anthropic from 'https://esm.sh/@anthropic-ai/sdk'

serve(async (req) => {
  try {
    const {
      system_prompt,
      user_message,
      action_type,
      client_id,
      werkbon_id
    } = await req.json()

    // Get Supabase client
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    // Get configuration
    const { data: config } = await supabase
      .from('llm_configurations')
      .select('*')
      .eq('action_type', action_type)
      .or(`client_id.eq.${client_id},client_id.is.null`)
      .eq('is_active', true)
      .order('priority', { ascending: false })
      .limit(1)
      .single()

    if (!config) {
      throw new Error('No configuration found')
    }

    // Call appropriate LLM provider
    let response
    if (config.provider === 'anthropic') {
      const anthropic = new Anthropic({
        apiKey: Deno.env.get(config.api_key_env_var)
      })

      const startTime = Date.now()

      const message = await anthropic.messages.create({
        model: config.model_name,
        max_tokens: config.max_tokens,
        temperature: config.temperature,
        system: system_prompt,
        messages: [{ role: 'user', content: user_message }]
      })

      const latency = Date.now() - startTime

      response = {
        content: message.content[0].text,
        provider: config.provider,
        model: config.model_name,
        usage: {
          input_tokens: message.usage.input_tokens,
          output_tokens: message.usage.output_tokens,
          latency_ms: latency,
          input_cost: (message.usage.input_tokens / 1_000_000) * config.cost_per_input_token,
          output_cost: (message.usage.output_tokens / 1_000_000) * config.cost_per_output_token
        }
      }
    } else if (config.provider === 'mistral') {
      // Mistral implementation
      const startTime = Date.now()

      const mistralResponse = await fetch(config.api_endpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${Deno.env.get(config.api_key_env_var)}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: config.model_name,
          messages: [
            { role: 'system', content: system_prompt },
            { role: 'user', content: user_message }
          ],
          max_tokens: config.max_tokens,
          temperature: config.temperature
        })
      })

      const data = await mistralResponse.json()
      const latency = Date.now() - startTime

      response = {
        content: data.choices[0].message.content,
        provider: config.provider,
        model: config.model_name,
        usage: {
          input_tokens: data.usage.prompt_tokens,
          output_tokens: data.usage.completion_tokens,
          latency_ms: latency,
          input_cost: (data.usage.prompt_tokens / 1_000_000) * config.cost_per_input_token,
          output_cost: (data.usage.completion_tokens / 1_000_000) * config.cost_per_output_token
        }
      }
    }

    // Log usage
    await supabase.from('llm_usage_logs').insert({
      config_id: config.id,
      action_type,
      client_id,
      werkbon_id,
      provider: response.provider,
      model_name: response.model,
      input_tokens: response.usage.input_tokens,
      output_tokens: response.usage.output_tokens,
      input_cost: response.usage.input_cost,
      output_cost: response.usage.output_cost,
      latency_ms: response.usage.latency_ms,
      success: true
    })

    return new Response(JSON.stringify(response), {
      headers: { 'Content-Type': 'application/json' },
      status: 200
    })

  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { 'Content-Type': 'application/json' },
      status: 500
    })
  }
})
```

**React Frontend:**
```typescript
// services/llm.service.ts
import { supabase } from './supabase'

export async function generateLLMResponse(params: {
  systemPrompt: string
  userMessage: string
  actionType: string
  clientId?: string
  werkbonId?: string
}) {
  const { data, error } = await supabase.functions.invoke('llm-generate', {
    body: {
      system_prompt: params.systemPrompt,
      user_message: params.userMessage,
      action_type: params.actionType,
      client_id: params.clientId,
      werkbon_id: params.werkbonId
    }
  })

  if (error) throw error
  return data
}

// Usage in React component
const response = await generateLLMResponse({
  systemPrompt: 'Je bent een contract expert...',
  userMessage: 'Classificeer deze werkbon...',
  actionType: 'werkbon_classification',
  clientId: 'WVC',
  werkbonId: '12345'
})
```

**Voordelen:**
- ✅ Serverless - schaalt automatisch
- ✅ API keys veilig in Supabase secrets
- ✅ Automatische usage logging
- ✅ Werkt met elke frontend (React, Vue, Mobile)
- ✅ CORS automatisch geconfigureerd

---

## REST API Specificatie (voor Edge Functions)

### POST `/functions/llm-generate`

**Request:**
```json
{
  "system_prompt": "Je bent een expert...",
  "user_message": "Analyseer deze werkbon...",
  "action_type": "werkbon_classification",
  "client_id": "WVC",
  "werkbon_id": "12345",
  "metadata": {
    "hoofdwerkbon_key": "WB2024-001",
    "bedrag": 150.50
  }
}
```

**Response:**
```json
{
  "content": "{\n  \"classificatie\": \"NEE\",\n  \"mapping_score\": 0.92,\n  ...\n}",
  "provider": "mistral",
  "model": "mistral-large-latest",
  "usage": {
    "input_tokens": 2500,
    "output_tokens": 150,
    "latency_ms": 1250,
    "input_cost": 0.002,
    "output_cost": 0.00036,
    "total_cost": 0.00236
  }
}
```

**Error Response:**
```json
{
  "error": "No configuration found for action_type: werkbon_classification"
}
```

---

### GET `/functions/llm-configs`

**Request:**
```
GET /functions/llm-configs?action_type=werkbon_classification&client_id=WVC
```

**Response:**
```json
{
  "configs": [
    {
      "id": "uuid-here",
      "client_id": "WVC",
      "action_type": "werkbon_classification",
      "provider": "anthropic",
      "model_name": "claude-sonnet-4-20250514",
      "model_alias": "Claude Sonnet 4",
      "max_tokens": 1024,
      "temperature": 0.0,
      "cost_per_input_token": 3.00,
      "cost_per_output_token": 15.00,
      "is_active": true,
      "priority": 200
    }
  ]
}
```

---

### GET `/functions/llm-usage`

**Request:**
```
GET /functions/llm-usage?start_date=2024-01-01&end_date=2024-01-31&client_id=WVC
```

**Response:**
```json
{
  "stats": {
    "total_requests": 1250,
    "successful_requests": 1235,
    "failed_requests": 15,
    "success_rate": 0.988,
    "total_input_tokens": 3125000,
    "total_output_tokens": 187500,
    "total_tokens": 3312500,
    "total_cost": 11.45,
    "avg_cost_per_request": 0.009160,
    "avg_latency_ms": 1150,
    "currency": "EUR"
  },
  "breakdown_by_action": {
    "werkbon_classification": {
      "request_count": 1000,
      "total_tokens": 2650000,
      "total_cost": 2.36,
      "avg_latency_ms": 980
    },
    "contract_generation": {
      "request_count": 250,
      "total_tokens": 662500,
      "total_cost": 9.09,
      "avg_latency_ms": 2100
    }
  }
}
```

---

## Database Schema Aanpassingen voor Multi-App Support

### Toevoegen: `application_id` kolom

Om meerdere apps te ondersteunen in één Supabase database:

```sql
-- Uitbreiding van llm_configurations
ALTER TABLE llm_configurations
ADD COLUMN application_id VARCHAR(50) DEFAULT 'contract-checker';

ALTER TABLE llm_configurations
DROP CONSTRAINT llm_configurations_client_id_action_type_provider_model_name_key;

ALTER TABLE llm_configurations
ADD CONSTRAINT llm_configurations_unique_key
UNIQUE(application_id, client_id, action_type, provider, model_name);

CREATE INDEX idx_llm_config_app ON llm_configurations(application_id);

-- Uitbreiding van llm_usage_logs
ALTER TABLE llm_usage_logs
ADD COLUMN application_id VARCHAR(50) DEFAULT 'contract-checker';

CREATE INDEX idx_llm_usage_app ON llm_usage_logs(application_id, created_at DESC);

-- Update materialized view
DROP MATERIALIZED VIEW llm_usage_summary;

CREATE MATERIALIZED VIEW llm_usage_summary AS
SELECT
    application_id,
    client_id,
    action_type,
    provider,
    model_name,
    DATE(created_at) as usage_date,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(total_cost) as total_cost,
    AVG(total_cost) as avg_cost_per_request,
    currency,
    AVG(latency_ms) as avg_latency_ms,
    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as error_count,
    MIN(created_at) as first_request,
    MAX(created_at) as last_request
FROM llm_usage_logs
GROUP BY application_id, client_id, action_type, provider, model_name, DATE(created_at), currency;

CREATE INDEX idx_llm_summary_app_date ON llm_usage_summary(application_id, usage_date DESC);
```

**Voorbeeld configuraties:**
```sql
-- Contract Checker app
INSERT INTO llm_configurations (
    application_id, client_id, action_type, provider, model_name,
    cost_per_input_token, cost_per_output_token, priority
) VALUES
    ('contract-checker', NULL, 'werkbon_classification', 'mistral', 'mistral-large-latest', 0.80, 2.40, 100),
    ('contract-checker', NULL, 'contract_generation', 'anthropic', 'claude-sonnet-4-20250514', 3.00, 15.00, 100);

-- Andere toekomstige app
INSERT INTO llm_configurations (
    application_id, client_id, action_type, provider, model_name,
    cost_per_input_token, cost_per_output_token, priority
) VALUES
    ('facility-management', NULL, 'incident_analysis', 'mistral', 'mistral-large-latest', 0.80, 2.40, 100),
    ('facility-management', NULL, 'report_generation', 'anthropic', 'claude-sonnet-4-20250514', 3.00, 15.00, 100);
```

---

## React Component Voorbeeld

```typescript
// components/WerkbonClassification.tsx
import { useState } from 'react'
import { generateLLMResponse } from '../services/llm.service'
import { supabase } from '../services/supabase'

interface ClassificationResult {
  classificatie: 'JA' | 'NEE' | 'ONZEKER' | 'GEDEELTELIJK'
  mapping_score: number
  contract_referentie: string
  toelichting: string
}

export function WerkbonClassification({ werkbonId, clientId }: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ClassificationResult | null>(null)
  const [cost, setCost] = useState<number>(0)

  async function classify() {
    setLoading(true)
    try {
      // Haal werkbon en contract op
      const { data: werkbon } = await supabase
        .from('werkbonnen')
        .select('*')
        .eq('id', werkbonId)
        .single()

      const { data: contract } = await supabase
        .from('contracts')
        .select('llm_ready')
        .eq('debiteur_code', werkbon.debiteur_code)
        .single()

      // Bouw prompts
      const systemPrompt = buildSystemPrompt()
      const userMessage = buildUserMessage(werkbon, contract)

      // Classificeer via LLM
      const response = await generateLLMResponse({
        systemPrompt,
        userMessage,
        actionType: 'werkbon_classification',
        clientId,
        werkbonId: werkbonId.toString()
      })

      // Parse result
      const classification = JSON.parse(response.content)
      setResult(classification)
      setCost(response.usage.total_cost)

      // Sla classificatie op in database
      await supabase.from('classifications').insert({
        werkbon_id: werkbonId,
        classificatie: classification.classificatie,
        mapping_score: classification.mapping_score,
        contract_referentie: classification.contract_referentie,
        toelichting: classification.toelichting,
        llm_provider: response.provider,
        llm_model: response.model,
        llm_cost: response.usage.total_cost
      })

    } catch (error) {
      console.error('Classification failed:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="classification-panel">
      <button onClick={classify} disabled={loading}>
        {loading ? 'Classificeren...' : 'Classificeer Werkbon'}
      </button>

      {result && (
        <div className="result">
          <h3>Classificatie: {result.classificatie}</h3>
          <p>Score: {(result.mapping_score * 100).toFixed(0)}%</p>
          <p>Kosten: €{cost.toFixed(6)}</p>
          <p>{result.toelichting}</p>
        </div>
      )}
    </div>
  )
}
```

---

## TypeScript Types voor React

```typescript
// types/llm.types.ts

export type LLMProvider = 'anthropic' | 'mistral' | 'openai' | 'local'

export type ActionType =
  | 'werkbon_classification'
  | 'contract_generation'
  | 'contract_analysis'
  | 'report_generation'

export interface LLMConfiguration {
  id: string
  application_id: string
  client_id: string | null
  action_type: ActionType
  provider: LLMProvider
  model_name: string
  model_alias: string | null
  api_endpoint: string | null
  max_tokens: number
  temperature: number
  cost_per_input_token: number
  cost_per_output_token: number
  currency: string
  is_active: boolean
  priority: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface LLMUsageLog {
  id: string
  config_id: string | null
  application_id: string
  client_id: string | null
  action_type: ActionType
  request_id: string | null
  provider: LLMProvider
  model_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost: number
  output_cost: number
  total_cost: number
  currency: string
  latency_ms: number
  success: boolean
  error_message: string | null
  user_id: string | null
  werkbon_id: string | null
  contract_id: string | null
  metadata: Record<string, any>
  created_at: string
}

export interface LLMGenerateRequest {
  system_prompt: string
  user_message: string
  action_type: ActionType
  client_id?: string
  werkbon_id?: string
  contract_id?: string
  user_id?: string
  metadata?: Record<string, any>
}

export interface LLMGenerateResponse {
  content: string
  provider: LLMProvider
  model: string
  usage: {
    input_tokens: number
    output_tokens: number
    latency_ms: number
    input_cost: number
    output_cost: number
    total_cost: number
  }
}

export interface LLMUsageStats {
  total_requests: number
  successful_requests: number
  failed_requests: number
  success_rate: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost: number
  avg_cost_per_request: number
  avg_latency_ms: number
  currency: string
  period: {
    start: string | null
    end: string | null
  }
}
```

---

## Migratiestrategie: Streamlit → React

### Fase 1: Supabase Foundation (Nu)
1. ✅ Schema ontwerpen met `application_id` support
2. ✅ Python LLM service implementeren
3. ⏳ Testen met huidige Streamlit app

### Fase 2: API Layer (3-6 maanden)
1. Supabase Edge Functions bouwen
2. REST API endpoints implementeren
3. Parallel testing (Python + Edge Functions)

### Fase 3: React Migration (6-12 maanden)
1. React app ontwikkelen met Supabase client
2. TypeScript services implementeren
3. Component library bouwen
4. Geleidelijke migratie per feature

### Fase 4: Consolidatie (12+ maanden)
1. Alle apps migreren naar centrale React app
2. Python backend als optionele compute layer
3. Uniforme look & feel
4. Gedeelde componenten en services

---

## Aanbevelingen

### Voor Nu (Streamlit)
- ✅ Gebruik Python LLM service zoals ontworpen
- ✅ Schema bevat al `application_id` voor toekomst
- ✅ Alle functionaliteit werkt zonder API layer

### Voor Toekomst (React)
- 🔄 Supabase Edge Functions voor LLM calls
- 🔄 TypeScript types en services
- 🔄 Gedeelde configuratie tussen apps
- 🔄 Real-time updates via Supabase subscriptions

### Gemeenschappelijk
- 📊 Centralized usage tracking in Supabase
- 💰 Unified cost monitoring dashboard
- 🔐 Centralized LLM provider credentials
- ⚙️ Configuration management UI (Streamlit of React)

---

## Volgende Stappen

1. **Deel huidige Supabase schema** met SQL query
2. **Besluit:** Direct database access of Edge Functions?
3. **Implementeer** gekozen methode
4. **Test** met huidige Streamlit app
5. **Documenteer** API voor toekomstige React team

Wil je dat ik de Edge Functions volledig implementeer, of focussen we eerst op de Python implementatie met het oog op latere migratie?
