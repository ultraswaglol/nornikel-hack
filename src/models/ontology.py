# src/models/ontology.py
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

class SecurityLevel(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"

class TrustLevel(str, Enum):
    LEVEL_A = "A"
    LEVEL_B = "B"
    LEVEL_C = "C"

# --- Сущности (Nodes) ---

class MaterialNode(BaseModel):
    id: str
    name: str
    name_en: Optional[str] = None
    formula: Optional[str] = None
    state_of_matter: Optional[str] = None

class ProcessNode(BaseModel):
    id: str
    name: str
    type: Optional[str] = None

class PropertyNode(BaseModel):
    id: str
    name: str
    # Фикс: Значение и диапазоны теперь могут быть как числами (float), так и текстом/формулами (str)
    value: Optional[Union[float, str]] = None
    min_value: Optional[Union[float, str]] = None
    max_value: Optional[Union[float, str]] = None
    unit: str

class EquipmentNode(BaseModel):
    id: str
    name: str
    type: Optional[str] = None

class ExpertNode(BaseModel):
    id: str
    name: str
    organization: Optional[str] = None
    email: Optional[str] = None

class PublicationNode(BaseModel):
    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: int
    geography: str
    security_level: SecurityLevel = Field(default=SecurityLevel.PUBLIC)
    trust_level: TrustLevel = Field(default=TrustLevel.LEVEL_B)

# --- Связи (Edges) ---

class RelationType(str, Enum):
    USES_MATERIAL = "uses_material"
    OPERATES_AT_CONDITION = "operates_at_condition"
    PRODUCES_OUTPUT = "produces_output"
    DESCRIBED_IN = "described_in"
    VALIDATED_BY = "validated_by"
    CONTRADICTS = "contradicts"

class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: RelationType
    confidence_score: float = 1.0
    description: Optional[str] = None

# --- Полный Граф ---

class ExtractedKnowledgeGraph(BaseModel):
    materials: List[MaterialNode] = Field(default_factory=list)
    processes: List[ProcessNode] = Field(default_factory=list)
    properties: List[PropertyNode] = Field(default_factory=list)
    equipment: List[EquipmentNode] = Field(default_factory=list)
    experts: List[ExpertNode] = Field(default_factory=list)
    publications: List[PublicationNode] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)