from .base_generator import BaseGenerator

class SigmaGenerator(BaseGenerator):
    """
    Generates Sigma YAML rules from SecurityIR.
    """
    def __init__(self):
        super().__init__("sigma", "sigma_base.yml.j2")

    def generate(self, ir_dict: dict) -> str:
        logic = ir_dict.get("detection_logic", {})
        event_type = logic.get("event_type", "unknown")
        
        # Translate OCSF to Sigma-specific categories and fields
        table_name = self.resolver.mapper.resolve_table(event_type, "sigma")
        filters = self.resolver.translate_filters(event_type, "sigma", logic.get("filters", []))
        
        template = self.env.get_template(self.template_name)
        return template.render(
            metadata=ir_dict.get("metadata", {}),
            created_at=ir_dict.get("created_at", ""),
            table_name=table_name,
            filters=filters,
            aggregation=logic.get("aggregation")
        )
