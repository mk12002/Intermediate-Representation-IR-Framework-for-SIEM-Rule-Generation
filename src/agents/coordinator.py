from .threat_intel_agent import ThreatIntelAgent
from .entity_extraction_agent import EntityExtractionAgent
from .metadata_agent import MetadataAgent
from .mitre_mapping_agent import MITREMappingAgent
from .ir_builder_agent import IRBuilderAgent
from .repair_agent import RepairAgent

class Coordinator:
    """
    Registry and wrapper for all LangChain agents.
    Provides instantiated access to the agents for the LangGraph nodes to execute.
    """
    def __init__(self):
        self.threat_intel_agent = ThreatIntelAgent()
        self.entity_agent = EntityExtractionAgent()
        self.metadata_agent = MetadataAgent()
        self.mitre_agent = MITREMappingAgent()
        self.ir_builder = IRBuilderAgent()
        self.repair_agent = RepairAgent()
