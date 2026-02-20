"""
Service voor het genereren van LLM-ready versies van contracten.

Gebruikt Claude API om platte contract tekst te verrijken en structureren.
"""
import os
from typing import Optional
from anthropic import Anthropic
from src.config import config
from src.models.database import SessionLocal
from src.models.contract import Contract

# Pilot: Feature flag voor nieuwe LLM systeem
USE_NEW_LLM_SYSTEM = os.getenv('USE_NEW_LLM_SYSTEM', 'true').lower() == 'true'

if USE_NEW_LLM_SYSTEM:
    try:
        from src.services.llm_service import get_llm_service
    except ImportError:
        print("[WARN] LLM service not available, falling back to direct Anthropic")
        USE_NEW_LLM_SYSTEM = False


class ContractLLMGenerator:
    """Generate structured LLM-ready versions of contracts using Claude."""

    SYSTEM_PROMPT = """Je bent een expert in het analyseren en structureren van servicecontracten voor verwarmings- en onderhoudsbedrijven.

Je taak is om een platte tekst versie van een contract om te zetten naar een goed gestructureerde, leesbare versie die optimaal is voor AI-classificatie van werkbonnen.

## Instructies

1. **Behoud alle informatie** - Verwijder geen details uit het originele contract
2. **Structureer met duidelijke secties** - Gebruik markdown headers
3. **Highlight belangrijke elementen**:
   - Wat valt WEL onder het contract (dekking)
   - Wat valt NIET onder het contract (uitsluitingen)
   - Tarieven en voorwaarden
   - Specifieke artikelen of clausules

## Output Format

Gebruik deze structuur (pas aan waar nodig):

```markdown
# [Contract Naam]

## Samenvatting
[Korte samenvatting van het contract type en dekking]

## Dekking (wat valt WEL onder contract)
- [Punt 1]
- [Punt 2]
...

## Uitsluitingen (wat valt NIET onder contract)
- [Punt 1]
- [Punt 2]
...

## Tarieven & Voorwaarden
[Relevante tarieven, uren, etc.]

## Specifieke Bepalingen
[Andere belangrijke clausules]

## Originele Artikelen
[Behoud originele artikel nummering waar relevant]
```

## Belangrijk
- Schrijf in het Nederlands
- Wees precies en volledig
- Gebruik bullet points voor lijsten
- Markeer onduidelijkheden met [ONDUIDELIJK: ...]
- Als er aanvullende context/instructies zijn, volg deze op"""

    def __init__(self):
        # Pilot: Use new LLM system if enabled
        self.use_new_system = USE_NEW_LLM_SYSTEM

        if self.use_new_system:
            # NEW: LLM service (Supabase determines model: Claude for contract_generation)
            self.llm_service = get_llm_service('werkbon-checker')
        else:
            # OLD: Direct Anthropic client (fallback)
            self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def generate_llm_ready(self, contract_id: int) -> str:
        """
        Generate LLM-ready version for a contract.

        Args:
            contract_id: Database ID of the contract

        Returns:
            Generated LLM-ready text

        Raises:
            ValueError: If contract not found or has no content
            Exception: On API errors
        """
        db = SessionLocal()
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()

            if not contract:
                raise ValueError(f"Contract met ID {contract_id} niet gevonden")

            if not contract.content:
                raise ValueError(f"Contract '{contract.filename}' heeft geen content om te verwerken")

            # Build user message
            user_message = self._build_user_message(contract)

            # Pilot: Use new LLM system or fallback to old
            if self.use_new_system:
                # NEW: Use LLM service (Supabase picks model: Claude Sonnet for contract_generation)
                response = self.llm_service.generate(
                    system_prompt=self.SYSTEM_PROMPT,
                    user_message=user_message,
                    action_type='contract_generation',
                    organization_id=contract.client_code if hasattr(contract, 'client_code') else None,
                    max_tokens=4096
                )
                return response.content
            else:
                # OLD: Direct Anthropic client
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text

        finally:
            db.close()

    def _build_user_message(self, contract: Contract) -> str:
        """Build the user message for Claude with contract content and optional context."""
        parts = []

        # Contract header
        parts.append(f"# Contract: {contract.filename}")
        if contract.client_name:
            parts.append(f"Klant: {contract.client_name}")
        parts.append("")

        # Additional context/instructions if provided
        if contract.llm_context:
            parts.append("## Aanvullende Instructies")
            parts.append(contract.llm_context)
            parts.append("")

        # Original content
        parts.append("## Originele Contract Tekst")
        parts.append("```")
        parts.append(contract.content)
        parts.append("```")
        parts.append("")

        # Request
        parts.append("---")
        parts.append("Verwerk bovenstaande contract tekst naar een gestructureerde LLM-ready versie.")

        return "\n".join(parts)
