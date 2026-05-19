import yaml
from pathlib import Path

class SchemaMapper:
    """
    Reads YAML mappings to translate OCSF event types and fields into 
    platform-specific syntax (Sigma categories, KQL tables, Splunk indexes).
    """
    def __init__(self, schema_file: str = "config/schemas/schema_map.yaml"):
        project_root = Path(__file__).parent.parent.parent
        self.schema_path = project_root / schema_file
        
        with open(self.schema_path, 'r') as f:
            self.mapping = yaml.safe_load(f)

    def resolve_field(self, event_type: str, platform: str, ocsf_field: str) -> str:
        """Translates an OCSF field to a platform-specific field."""
        try:
            return self.mapping[event_type][platform]["fields"].get(ocsf_field, ocsf_field)
        except KeyError:
            return ocsf_field # Fallback to original if mapping fails or is undefined

    def resolve_table(self, event_type: str, platform: str) -> str:
        """Translates an OCSF event_type to a platform table/index/category."""
        try:
            if platform == "sigma":
                return self.mapping[event_type][platform].get("category", event_type)
            elif platform == "kql":
                return self.mapping[event_type][platform].get("table", event_type)
            elif platform == "spl":
                return self.mapping[event_type][platform].get("index", event_type)
            return event_type
        except KeyError:
            return event_type
