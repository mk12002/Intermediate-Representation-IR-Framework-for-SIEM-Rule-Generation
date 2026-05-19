from .base_generator import BaseGenerator

class SPLGenerator(BaseGenerator):
    """
    Generates Splunk SPL queries from SecurityIR.
    """
    def __init__(self):
        super().__init__("spl", "spl_base.spl.j2")

    def generate(self, ir_dict: dict) -> str:
        logic = ir_dict.get("detection_logic", {})
        event_type = logic.get("event_type", "unknown")
        
        # Translate OCSF to Splunk CIM indexes and fields
        table_name = self.resolver.mapper.resolve_table(event_type, "spl")
        filters = self.resolver.translate_filters(event_type, "spl", logic.get("filters", []))
        aggregation = self.resolver.translate_aggregation(event_type, "spl", logic.get("aggregation"))
        
        template = self.env.get_template(self.template_name)
        return template.render(
            table_name=table_name,
            filters=filters,
            aggregation=aggregation
        )
