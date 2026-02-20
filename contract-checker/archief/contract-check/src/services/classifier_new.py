"""
Classification Service (Migrated to new LLM system)

This is an example of the classifier.py migrated to use the new LLM abstraction layer.
Copy this code to classifier.py when ready to migrate.

Key changes:
1. Uses LLMService instead of direct Anthropic client
2. Automatic provider selection based on Supabase config
3. Automatic usage tracking
4. Supports fallback to old system for gradual migration
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy.orm import Session
from src.config import Config
from src.models.classification import Classification, ClassificationKostenregel
from src.models.werkbon import Werkbon
from src.models.client_config import ClientConfig
from src.services.contract_loader import ContractLoader
from src.services.werkbon_keten_service import WerkbonKetenService

# New LLM system imports
from src.services.llm_service import get_llm_service
from src.services.llm_provider import LLMResponse

# Old system import (for fallback)
from anthropic import Anthropic


class ClassificationService:
    """
    Service voor het classificeren van werkbonnen tegen contracten.

    Migrated to use new LLM configuration system with:
    - Flexible provider selection (Claude, Mistral, local)
    - Automatic usage tracking
    - Cost optimization
    """

    DEFAULT_SYSTEM_PROMPT = """Je bent een expert in het analyseren van servicecontracten..."""

    def __init__(
        self,
        db_session: Session,
        use_new_llm_system: bool = True
    ):
        """
        Initialize classification service.

        Args:
            db_session: Database session
            use_new_llm_system: Use new LLM configuration system (True) or old Anthropic client (False)
        """
        self.db = db_session
        self.contract_loader = ContractLoader(db_session)
        self.werkbon_service = WerkbonKetenService(db_session)

        # Try to use new system, fallback to old if unavailable
        self.use_new_llm_system = use_new_llm_system

        if self.use_new_llm_system:
            try:
                self.llm_service = get_llm_service(
                    enable_supabase=True,
                    enable_usage_logging=True
                )
                print("✓ Using new LLM configuration system with Supabase")
            except Exception as e:
                print(f"⚠ Falling back to old system: {e}")
                self.use_new_llm_system = False
                self._init_old_system()
        else:
            self._init_old_system()

    def _init_old_system(self):
        """Initialize old Anthropic client system."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        print("✓ Using legacy Anthropic client")

    def classify_werkbon(
        self,
        werkbon: Werkbon,
        client_config: Optional[ClientConfig] = None,
        user_id: Optional[str] = None
    ) -> Classification:
        """
        Classificeer een werkbon tegen het contract.

        Args:
            werkbon: Werkbon to classify
            client_config: Client-specific configuration
            user_id: User who triggered the classification

        Returns:
            Classification result with decision and reasoning

        Raises:
            Exception: If classification fails
        """
        # Get contract for this debiteur
        contract_text = self.contract_loader.get_contract_for_debiteur(werkbon.debiteur_code)

        if not contract_text:
            raise ValueError(f"No contract found for debiteur: {werkbon.debiteur_code}")

        # Build werkbon narrative
        verhaal = self.werkbon_service.build_verhaal(werkbon)

        # Build prompts
        system_prompt = self._build_system_prompt(client_config)
        user_message = self._build_user_message(werkbon, contract_text, verhaal)

        # Call LLM (new or old system)
        if self.use_new_llm_system:
            response = self._classify_new(
                system_prompt=system_prompt,
                user_message=user_message,
                werkbon=werkbon,
                user_id=user_id
            )
        else:
            response_text = self._classify_old(
                system_prompt=system_prompt,
                user_message=user_message
            )
            # Wrap in LLMResponse-like object for uniform processing
            response = self._wrap_old_response(response_text)

        # Parse and store classification
        classification = self._parse_and_store_response(
            response=response,
            werkbon=werkbon,
            client_config=client_config
        )

        return classification

    def _classify_new(
        self,
        system_prompt: str,
        user_message: str,
        werkbon: Werkbon,
        user_id: Optional[str] = None
    ) -> LLMResponse:
        """
        Classify using new LLM system.

        Automatically selects provider based on Supabase configuration.
        Logs usage for cost tracking.
        """
        response = self.llm_service.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            action_type="werkbon_classification",
            client_id=werkbon.debiteur_code,
            user_id=user_id,
            werkbon_id=str(werkbon.id),
            max_tokens=1024,
            temperature=0.0,
            metadata={
                "hoofdwerkbon_key": werkbon.hoofdwerkbon_key,
                "bedrag": float(werkbon.bedrag) if werkbon.bedrag else None
            }
        )

        # Check for errors
        if not response.success:
            raise Exception(f"LLM classification failed: {response.error_message}")

        # Log provider info for debugging
        print(f"  Used: {response.provider} ({response.model})")
        print(f"  Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
        print(f"  Cost: €{response.usage.total_cost:.6f}")

        return response

    def _classify_old(
        self,
        system_prompt: str,
        user_message: str
    ) -> str:
        """
        Classify using old Anthropic client.

        Kept for backward compatibility during migration.
        """
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        # Extract text content
        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content = block.text
                    break

        return content

    def _wrap_old_response(self, response_text: str) -> LLMResponse:
        """
        Wrap old response in LLMResponse-like object for uniform processing.
        """
        from src.services.llm_provider import LLMResponse, LLMUsageMetrics

        return LLMResponse(
            content=response_text,
            usage=LLMUsageMetrics(),  # No usage info from old system
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            success=True
        )

    def _build_system_prompt(self, client_config: Optional[ClientConfig]) -> str:
        """
        Build system prompt from client configuration.

        Combines:
        - Classification task (classificatie_opdracht)
        - Business context (werkwijze, syntess_context, etc.)
        - Output format (classificatie_output_format)
        """
        if not client_config:
            return self.DEFAULT_SYSTEM_PROMPT

        parts = []

        # Classification task
        if client_config.classificatie_opdracht:
            parts.append(client_config.classificatie_opdracht)

        # Business context
        context_parts = []
        if client_config.werkwijze:
            context_parts.append(f"**Werkwijze:**\n{client_config.werkwijze}")
        if client_config.syntess_context:
            context_parts.append(f"**Syntess Systeem:**\n{client_config.syntess_context}")
        if client_config.werkbon_context:
            context_parts.append(f"**Werkbonnen:**\n{client_config.werkbon_context}")
        if client_config.contract_context:
            context_parts.append(f"**Contracten:**\n{client_config.contract_context}")

        if context_parts:
            parts.append("# Bedrijfscontext\n\n" + "\n\n".join(context_parts))

        # Output format
        if client_config.classificatie_output_format:
            parts.append(client_config.classificatie_output_format)

        return "\n\n".join(parts) if parts else self.DEFAULT_SYSTEM_PROMPT

    def _build_user_message(
        self,
        werkbon: Werkbon,
        contract_text: str,
        verhaal: str
    ) -> str:
        """
        Build user message with contract and werkbon details.
        """
        message_parts = [
            "# Contract",
            contract_text,
            "",
            "# Werkbon",
            f"**Hoofdwerkbon:** {werkbon.hoofdwerkbon_key}",
            f"**Debiteur:** {werkbon.debiteur_code}",
            f"**Bedrag:** €{werkbon.bedrag:.2f}" if werkbon.bedrag else "**Bedrag:** N/A",
            "",
            "## Verhaal",
            verhaal,
            "",
            "## Kostenregels",
        ]

        # Add kostenregels if available
        if hasattr(werkbon, 'kostenregels') and werkbon.kostenregels:
            for regel in werkbon.kostenregels:
                message_parts.append(
                    f"- {regel.categorie}: {regel.omschrijving} - €{regel.bedrag:.2f}"
                )
        else:
            message_parts.append("Geen kostenregels beschikbaar")

        return "\n".join(message_parts)

    def _parse_and_store_response(
        self,
        response: LLMResponse,
        werkbon: Werkbon,
        client_config: Optional[ClientConfig]
    ) -> Classification:
        """
        Parse LLM response and store classification in database.
        """
        # Parse JSON from response
        parsed = self._parse_response(response.content)

        # Apply confidence threshold
        threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
        if parsed.get("mapping_score", 0) < threshold:
            parsed["classificatie"] = "ONZEKER"
            parsed["toelichting"] = (
                f"Confidence score ({parsed['mapping_score']:.2f}) below threshold ({threshold}). "
                f"Original classification: {parsed.get('classificatie', 'N/A')}. "
                f"{parsed.get('toelichting', '')}"
            )

        # Create classification record
        classification = Classification(
            werkbon_id=werkbon.id,
            classificatie=parsed.get("classificatie", "ONZEKER"),
            mapping_score=parsed.get("mapping_score", 0.0),
            contract_referentie=parsed.get("contract_referentie", ""),
            toelichting=parsed.get("toelichting", ""),
            llm_provider=response.provider,
            llm_model=response.model,
            llm_cost=response.usage.total_cost,
            created_at=datetime.now()
        )

        self.db.add(classification)
        self.db.flush()  # Get ID

        # Store line-item classifications if available
        if "kostenregels" in parsed and isinstance(parsed["kostenregels"], list):
            for regel_data in parsed["kostenregels"]:
                kostenregel_classificatie = ClassificationKostenregel(
                    classification_id=classification.id,
                    kostenregel_id=regel_data.get("id"),
                    classificatie=regel_data.get("classificatie", "ONZEKER"),
                    toelichting=regel_data.get("toelichting", "")
                )
                self.db.add(kostenregel_classificatie)

        self.db.commit()

        return classification

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM.

        Handles markdown code blocks and validates required fields.
        """
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            # Parse JSON
            data = json.loads(text.strip())

            # Validate required fields
            required_fields = ["classificatie", "mapping_score"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # Validate classificatie value
            valid_classifications = ["JA", "NEE", "ONZEKER", "GEDEELTELIJK"]
            if data["classificatie"] not in valid_classifications:
                data["classificatie"] = "ONZEKER"

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to process response: {e}")

    def classify_batch(
        self,
        werkbonnen: List[Werkbon],
        client_config: Optional[ClientConfig] = None,
        user_id: Optional[str] = None
    ) -> List[Classification]:
        """
        Classify multiple werkbonnen in batch.

        Args:
            werkbonnen: List of werkbonnen to classify
            client_config: Client-specific configuration
            user_id: User who triggered the batch

        Returns:
            List of classifications
        """
        results = []

        for werkbon in werkbonnen:
            try:
                classification = self.classify_werkbon(
                    werkbon=werkbon,
                    client_config=client_config,
                    user_id=user_id
                )
                results.append(classification)
                print(f"✓ Classified werkbon {werkbon.hoofdwerkbon_key}: {classification.classificatie}")

            except Exception as e:
                print(f"✗ Failed to classify werkbon {werkbon.hoofdwerkbon_key}: {e}")
                # Create error classification
                error_classification = Classification(
                    werkbon_id=werkbon.id,
                    classificatie="ONZEKER",
                    mapping_score=0.0,
                    toelichting=f"Classification failed: {str(e)}",
                    created_at=datetime.now()
                )
                self.db.add(error_classification)
                self.db.commit()
                results.append(error_classification)

        return results


# Backward compatible export
__all__ = ["ClassificationService"]
