import json
import os
from typing import Dict, Any, List, Optional
from anthropic import Anthropic
from src.config import config
from src.models.database import SessionLocal
from src.models.classification import Classification
from src.models.client_config import ClientConfig
from src.services.contract_loader import ContractLoader

# Pilot: Feature flag voor nieuwe LLM systeem
USE_NEW_LLM_SYSTEM = os.getenv('USE_NEW_LLM_SYSTEM', 'true').lower() == 'true'

if USE_NEW_LLM_SYSTEM:
    try:
        from src.services.llm_service import get_llm_service
    except ImportError:
        print("[WARN] LLM service not available, falling back to direct Anthropic")
        USE_NEW_LLM_SYSTEM = False


class ClassificationService:
    """Service to classify werkbonnen using Claude API.

    Uses three layers for classification:
    1. Classificatie Opdracht + Bedrijfscontext (from ClientConfig) -> System prompt
    2. Contract (LLM-ready) -> User message
    3. Werkbon verhaal -> User message
    """

    # Fallback system prompt als ClientConfig niet is ingevuld
    DEFAULT_SYSTEM_PROMPT = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

Analyseer de werkbon en vergelijk met de contractvoorwaarden. Let op:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Materialen en onderdelen
- Arbeidsuren en tarieven
- Specifieke uitsluitingen in het contract

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" | "NEE" | "ONZEKER",
    "mapping_score": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg van je redenering"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract
- NEE: Werkzaamheden vallen buiten het contract (factureerbaar)
- ONZEKER: Niet duidelijk, handmatige review nodig

mapping_score: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

Als er GEEN contract beschikbaar is voor deze debiteur, geef dan:
- classificatie: "ONZEKER"
- mapping_score: 0.0
- toelichting: Vermeld dat er geen contract gevonden is voor deze debiteur"""

    def __init__(self, client_code: str = "WVC"):
        # Pilot: Use new LLM system if enabled
        self.use_new_system = USE_NEW_LLM_SYSTEM

        if self.use_new_system:
            # NEW: LLM service (Supabase determines model: Mistral for classification)
            self.llm_service = get_llm_service('werkbon-checker')
        else:
            # OLD: Direct Anthropic client (fallback)
            self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

        self.contract_loader = ContractLoader()
        self._fallback_contracts_text: Optional[str] = None
        self._client_config: Optional[ClientConfig] = None
        self._client_code = client_code
        self._load_client_config()

    def _load_client_config(self):
        """Load client configuration for system prompt."""
        session = SessionLocal()
        try:
            self._client_config = session.query(ClientConfig).filter(
                ClientConfig.client_code == self._client_code,
                ClientConfig.active == True
            ).first()
            if self._client_config:
                session.expunge(self._client_config)
        finally:
            session.close()

    def _get_system_prompt(self) -> str:
        """Get system prompt from ClientConfig or use default."""
        if self._client_config:
            prompt = self._client_config.get_system_prompt()
            if prompt:
                return prompt
        return self.DEFAULT_SYSTEM_PROMPT

    def set_contracts(self, contracts_text: str):
        """Set fallback contracts text (used when no client_id match)."""
        self._fallback_contracts_text = contracts_text

    def _get_contract_for_werkbon(self, werkbon: Dict[str, Any]) -> tuple[str, Optional[str]]:
        """Get the contract text for a specific werkbon.

        Extracts debiteur_code from werkbon and looks up the contract via contract_relatie.

        Returns:
            Tuple of (contract_text, contract_filename or None)
        """
        # Extract debiteur_code from debiteur field
        # Format: "007453 - Stichting Bazalt Wonen" -> "007453"
        debiteur = werkbon.get("debiteur", "")
        debiteur_code = None

        if debiteur:
            # Extract first 6 digits (debiteur code)
            parts = debiteur.split(" - ")
            if parts and parts[0].strip().isdigit():
                debiteur_code = parts[0].strip()

        if debiteur_code:
            # Try to find contract for this specific debiteur
            contract = self.contract_loader.get_contract_for_debiteur(debiteur_code)
            if contract:
                return contract["content"], contract["filename"]

        # Fallback to all contracts if no debiteur_code or no match
        if self._fallback_contracts_text:
            return self._fallback_contracts_text, None

        # Load all contracts as last resort
        return self.contract_loader.get_contracts_text(), None

    def classify_werkbon(self, werkbon: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a single werkbon using the debiteur's specific contract."""
        werkbon_text = self._format_werkbon(werkbon)
        contract_text, contract_filename = self._get_contract_for_werkbon(werkbon)

        # Build user message with contract and werkbon
        if contract_filename:
            debiteur = werkbon.get('debiteur', 'onbekend')
            contract_header = f"### CONTRACT: {contract_filename} (voor {debiteur}) ###"
        else:
            contract_header = "### CONTRACTEN ###"

        user_message = f"""{contract_header}
{contract_text}

### WERKBON ###
{werkbon_text}

Classificeer deze werkbon. Geef je antwoord in JSON formaat."""

        # Pilot: Use new LLM system or fallback to old
        if self.use_new_system:
            # NEW: Use LLM service (Supabase picks model: Mistral Large for werkbon_classification)
            response = self.llm_service.generate(
                system_prompt=self._get_system_prompt(),
                user_message=user_message,
                action_type='werkbon_classification',
                organization_id=werkbon.get('debiteur_code'),  # For org-specific config
                werkbon_id=str(werkbon.get('werkbon_id', '')),
                max_tokens=1024
            )
            response_text = response.content
        else:
            # OLD: Direct Anthropic client
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": user_message}],
            )
            response_text = response.content[0].text

        result = self._parse_response(response_text)
        result["werkbon_id"] = werkbon.get("werkbon_id")
        result["werkbon_bedrag"] = werkbon.get("bedrag")
        result["contract_filename"] = contract_filename  # Track which contract was used

        return result

    def classify_batch(
        self, werkbonnen: List[Dict[str, Any]], save_to_db: bool = True
    ) -> List[Dict[str, Any]]:
        """Classify a batch of werkbonnen."""
        results = []
        db = SessionLocal()

        try:
            for werkbon in werkbonnen:
                result = self.classify_werkbon(werkbon)
                results.append(result)

                if save_to_db:
                    classification = Classification(
                        werkbon_id=result["werkbon_id"],
                        classificatie=result["classificatie"],
                        mapping_score=result["mapping_score"],
                        contract_referentie=result.get("contract_referentie"),
                        toelichting=result.get("toelichting"),
                        werkbon_bedrag=result.get("werkbon_bedrag"),
                    )
                    db.add(classification)

            if save_to_db:
                db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

        return results

    def _format_werkbon(self, werkbon: Dict[str, Any]) -> str:
        """Format werkbon data for Claude prompt."""
        lines = []
        field_labels = {
            "werkbon_id": "Werkbon ID",
            "client_id": "Klant ID",
            "datum": "Datum",
            "klant_naam": "Klant",
            "adres": "Adres",
            "omschrijving": "Omschrijving",
            "uitgevoerde_werkzaamheden": "Uitgevoerde werkzaamheden",
            "materialen": "Materialen",
            "monteur": "Monteur",
            "bedrag": "Bedrag",
            "contract_type": "Contract type",
        }

        for key, label in field_labels.items():
            value = werkbon.get(key)
            if value is not None:
                lines.append(f"{label}: {value}")

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response."""
        try:
            # Try to extract JSON from response
            text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text.strip())

            # Validate required fields
            if "classificatie" not in result:
                result["classificatie"] = "ONZEKER"
            if "mapping_score" not in result:
                result["mapping_score"] = 0.5

            # Ensure classificatie is valid
            if result["classificatie"] not in ["JA", "NEE", "ONZEKER"]:
                result["classificatie"] = "ONZEKER"

            # Apply confidence threshold
            if result["mapping_score"] < config.CONFIDENCE_THRESHOLD:
                result["classificatie"] = "ONZEKER"

            return result

        except (json.JSONDecodeError, IndexError):
            return {
                "classificatie": "ONZEKER",
                "mapping_score": 0.0,
                "toelichting": f"Kon response niet parsen: {response_text[:200]}",
            }


class ResultsAnalyzer:
    """Analyze classification results and generate metrics."""

    def __init__(self):
        self.db = SessionLocal()

    def get_confusion_matrix(self) -> Dict[str, Any]:
        """Calculate confusion matrix from classifications with actual values."""
        from sqlalchemy import func

        results = (
            self.db.query(
                Classification.classificatie,
                Classification.werkelijke_classificatie,
                func.count(Classification.id),
            )
            .filter(Classification.werkelijke_classificatie.isnot(None))
            .group_by(
                Classification.classificatie, Classification.werkelijke_classificatie
            )
            .all()
        )

        matrix = {"JA": {"JA": 0, "NEE": 0}, "NEE": {"JA": 0, "NEE": 0}}

        for predicted, actual, count in results:
            if predicted in matrix and actual in matrix[predicted]:
                matrix[predicted][actual] = count

        # Calculate metrics
        tp = matrix["JA"]["JA"]
        fp = matrix["JA"]["NEE"]
        fn = matrix["NEE"]["JA"]
        tn = matrix["NEE"]["NEE"]

        total = tp + fp + fn + tn
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "matrix": matrix,
            "metrics": {
                "accuracy": round(accuracy, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "false_positive_rate": round(fp / total, 4) if total > 0 else 0,
                "false_negative_rate": round(fn / total, 4) if total > 0 else 0,
            },
            "counts": {"total": total, "tp": tp, "fp": fp, "fn": fn, "tn": tn},
        }

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of all classifications."""
        from sqlalchemy import func

        total = self.db.query(func.count(Classification.id)).scalar() or 0

        by_classification = dict(
            self.db.query(
                Classification.classificatie, func.count(Classification.id)
            )
            .group_by(Classification.classificatie)
            .all()
        )

        avg_score = (
            self.db.query(func.avg(Classification.mapping_score)).scalar() or 0
        )

        return {
            "total_classifications": total,
            "by_classification": by_classification,
            "average_mapping_score": round(float(avg_score), 4),
            "onzeker_percentage": round(
                by_classification.get("ONZEKER", 0) / total * 100, 2
            )
            if total > 0
            else 0,
        }

    def close(self):
        self.db.close()
