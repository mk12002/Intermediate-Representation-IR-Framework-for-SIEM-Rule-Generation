from .base_generator import BaseGenerator

class KQLGenerator(BaseGenerator):
    """
    Generates Microsoft Sentinel KQL queries from SecurityIR.
    """
    def __init__(self):
        super().__init__("kql", "kql_base.kql.j2")

    def generate(self, ir_dict: dict) -> str:
        logic = ir_dict.get("detection_logic", {})
        event_type = logic.get("event_type", "unknown")
        
        # Translate OCSF to ASIM tables and fields
        table_name = self.resolver.mapper.resolve_table(event_type, "kql")
        filters = self.resolver.translate_filters(event_type, "kql", logic.get("filters", []))
        aggregation = self.resolver.translate_aggregation(event_type, "kql", logic.get("aggregation"))
        
        template = self.env.get_template(self.template_name)
        return template.render(
            table_name=table_name,
            filters=filters,
            aggregation=aggregation
        )
