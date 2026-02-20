# Config Service Migration Example

## Overview

This document shows how to migrate existing hardcoded configuration values to use the new `config_service.py` for reading app configuration from Supabase.

## Before: Hardcoded Config

```python
# OLD: src/services/classifier.py
from src.config import config

class ClassificationService:
    def __init__(self, client_code: str = "WVC"):
        # Hardcoded API key
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

        # Hardcoded confidence threshold
        self.confidence_threshold = 0.85

        # Hardcoded batch size
        self.max_batch_size = 100
```

## After: Dynamic Config from Supabase

```python
# NEW: src/services/classifier.py
from src.config import config
from src.services.config_service import get_app_config

class ClassificationService:
    def __init__(self, client_code: str = "WVC", organization_id: str = None):
        # API key still from .env (secrets don't go in database)
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

        # Read confidence threshold from Supabase (editable via admin UI)
        self.confidence_threshold = get_app_config(
            'confidence_threshold',
            organization_id=organization_id,
            default=0.85
        )

        # Read max batch size from Supabase
        self.max_batch_size = get_app_config(
            'max_batch_size',
            organization_id=organization_id,
            default=100
        )

        # Feature flag: quick classification
        self.quick_classification_enabled = get_app_config(
            'feature_quick_classification',
            organization_id=organization_id,
            default=True
        )
```

## Migration Strategy

### Option 1: Gradual Migration (Recommended)

Add organization_id parameter but keep defaults for backward compatibility:

```python
class ClassificationService:
    def __init__(
        self,
        client_code: str = "WVC",
        organization_id: Optional[str] = None,
        use_dynamic_config: bool = True  # Feature flag
    ):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.organization_id = organization_id

        # Allow fallback to hardcoded values during migration
        if use_dynamic_config:
            self.confidence_threshold = get_app_config(
                'confidence_threshold',
                organization_id=organization_id,
                default=0.85
            )
        else:
            self.confidence_threshold = 0.85
```

### Option 2: Full Migration

Replace all hardcoded values at once:

```python
# Get all configs at once for efficiency
from src.services.config_service import get_config_service

class ClassificationService:
    def __init__(self, client_code: str = "WVC", organization_id: Optional[str] = None):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

        # Get config service
        config_service = get_config_service("werkbon-checker")

        # Read all configs at once
        self.configs = config_service.get_all_configs(organization_id=organization_id)

        # Extract individual values
        self.confidence_threshold = self.configs.get('confidence_threshold', 0.85)
        self.max_batch_size = self.configs.get('max_batch_size', 100)
        self.quick_classification_enabled = self.configs.get('feature_quick_classification', True)
```

## Example: Updating Streamlit App

```python
# OLD: app/pages/02_Quick_Classification.py
CONFIDENCE_THRESHOLD = 0.85  # Hardcoded

def classify_batch(werkbonnen):
    for wb in werkbonnen:
        if wb.score >= CONFIDENCE_THRESHOLD:
            wb.status = "APPROVED"
```

```python
# NEW: app/pages/02_Quick_Classification.py
from src.services.config_service import get_app_config

# Read from Supabase (admin can change without redeploying)
confidence_threshold = get_app_config('confidence_threshold', default=0.85)

def classify_batch(werkbonnen, organization_id=None):
    # Allow org-specific overrides
    threshold = get_app_config(
        'confidence_threshold',
        organization_id=organization_id,
        default=0.85
    )

    for wb in werkbonnen:
        if wb.score >= threshold:
            wb.status = "APPROVED"
```

## Settings to Migrate

### High Priority (User-Editable)

These should be moved to `app_configuration` table:

| Setting | Current Location | New Location | Reason |
|---------|-----------------|--------------|--------|
| `CONFIDENCE_THRESHOLD` | Hardcoded 0.85 | app_configuration | Admins want to tune this |
| Feature flags | Not implemented | app_configuration | Enable/disable features per org |
| UI settings (items per page) | Hardcoded | app_configuration | User preference |

### Keep in .env (Secrets)

These should NEVER be in database:

| Setting | Location | Reason |
|---------|----------|--------|
| `ANTHROPIC_API_KEY` | .env | Secret, never commit |
| `MISTRAL_API_KEY` | .env | Secret, never commit |
| `SUPABASE_SERVICE_KEY` | .env | Secret, never commit |
| `DB_PASSWORD` | .env | Secret, never commit |

### Keep in .env (Environment-Specific)

These are environment-specific and don't belong in shared database:

| Setting | Location | Reason |
|---------|----------|--------|
| `CONTRACTS_FOLDER` | .env | Path differs per environment |
| `VPS4_SSH_KEY_PATH` | .env | Path differs per environment |
| `DB_HOST` | .env | Different per environment |

## Testing Migration

1. Deploy schema:
   ```bash
   # In Supabase SQL Editor, run:
   sql/003_app_configuration.sql
   ```

2. Test config service:
   ```bash
   python scripts/test_config_service.py
   ```

3. Verify configs exist:
   ```sql
   SELECT config_key, config_value, value_type
   FROM app_configuration_overview
   WHERE app_code = 'werkbon-checker';
   ```

4. Update code to use config service

5. Test with different organizations:
   ```python
   # Default threshold
   threshold = get_app_config('confidence_threshold')
   # Returns: 0.85

   # WVC-specific threshold (if override exists)
   threshold_wvc = get_app_config('confidence_threshold', organization_id='wvc-uuid')
   # Returns: 0.80 (if custom config exists) or 0.85 (fallback)
   ```

## Rollback Strategy

If issues occur, the code has built-in fallbacks:

```python
# Config service always has a default parameter
confidence_threshold = get_app_config('confidence_threshold', default=0.85)

# If Supabase is down or config not found, returns 0.85
# Application continues working with sensible defaults
```

## Benefits After Migration

1. **No Redeployment**: Admin can change thresholds via UI
2. **Per-Client Tuning**: Different orgs can have different settings
3. **Audit Trail**: All config changes tracked with user_id and timestamp
4. **Feature Flags**: Enable/disable features without code changes
5. **A/B Testing**: Try different settings for different orgs

## Next Steps

1. ✅ Deploy `003_app_configuration.sql` to Supabase
2. ✅ Test config service with `test_config_service.py`
3. ⏳ Migrate classifier.py to use config service
4. ⏳ Migrate Streamlit pages to use config service
5. ⏳ Build React admin UI for config management
6. ⏳ Add config change audit log to UI

---

**Ready to migrate!** 🚀

Start with non-critical settings first, then gradually move more configs to Supabase.
