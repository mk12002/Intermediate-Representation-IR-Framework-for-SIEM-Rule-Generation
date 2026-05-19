from typing import Dict, Any, List
from .ir_schema import (
    SecurityIR, IRMetadata, DetectionLogic, EntityMapping, 
    TemporalLogic, MITREMapping, OutputConfig
)
import uuid
from datetime import datetime

class IRBuilder:
    """
    Utility class to assemble a complete SecurityIR from partial components
    extracted by different agents.
    """
    def __init__(self):
        self._components = {}
        
    def add_metadata(self, rule_name: str, description: str, severity: str, tags: List[str] = None):
        self._components['metadata'] = IRMetadata(
            rule_name=rule_name,
            description=description,
            severity=severity,
            tags=tags or []
        )
        return self
        
    def add_detection_logic(self, event_type: str, filters: List[dict] = None, 
                            aggregation: dict = None, timeframe: dict = None):
        self._components['detection_logic'] = DetectionLogic(
            event_type=event_type,
            filters=filters or [],
            aggregation=aggregation,
            timeframe=timeframe
        )
        return self
        
    def add_entities(self, entities: dict):
        self._components['entity_mapping'] = EntityMapping(entities=entities)
        return self
        
    def add_mitre_mappings(self, mappings: List[dict]):
        mitre_list = [MITREMapping(**m) for m in mappings]
        self._components['mitre_mapping'] = mitre_list
        return self
        
    def build(self, source_document: str = None) -> SecurityIR:
        """Assembles all components into a valid SecurityIR model."""
        # Ensure required components exist
        if 'metadata' not in self._components:
            raise ValueError("Missing IR metadata")
        if 'detection_logic' not in self._components:
            raise ValueError("Missing detection logic")
            
        return SecurityIR(
            rule_id=str(uuid.uuid4()),
            created_at=datetime.utcnow().isoformat(),
            source_document=source_document,
            metadata=self._components['metadata'],
            detection_logic=self._components['detection_logic'],
            entity_mapping=self._components.get('entity_mapping', EntityMapping()),
            mitre_mapping=self._components.get('mitre_mapping', []),
            output_config=OutputConfig()
        )
