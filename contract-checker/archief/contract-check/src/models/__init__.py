from .database import db, init_db, Base
from .contract import Contract
from .contract_change import ContractChange
from .client_config import ClientConfig
from .contract_relatie import ContractRelatie

# Import both classification modules first (without using the classes)
# This registers both with SQLAlchemy's mapper before relationships are resolved
from .classification_kostenregel import ClassificationKostenregel
from .classification import Classification

# Configure the mappers to resolve all relationships
from sqlalchemy.orm import configure_mappers
configure_mappers()

__all__ = [
    "db", "init_db", "Base", "Classification", "ClassificationKostenregel",
    "Contract", "ContractChange", "ClientConfig", "ContractRelatie"
]
