from .schema_mapper import SchemaMapper

class OCSFResolver:
    """
    Wraps the SchemaMapper to translate entire IR filter logic into platform-specific structures.
    """
    def __init__(self):
        self.mapper = SchemaMapper()

    def translate_filters(self, event_type: str, platform: str, filters: list) -> list:
        """
        Takes a list of Pydantic FilterConditions (as dicts) and returns them
        with the 'field' keys mapped to the target platform.
        """
        translated = []
        for f in filters:
            t_f = dict(f)
            t_f['field'] = self.mapper.resolve_field(event_type, platform, f['field'])
            translated.append(t_f)
        return translated

    def translate_aggregation(self, event_type: str, platform: str, aggregation: dict) -> dict:
        """
        Translates group_by fields and target_fields inside an aggregation.
        """
        if not aggregation:
            return aggregation
            
        t_agg = dict(aggregation)
        if t_agg.get('target_field'):
            t_agg['target_field'] = self.mapper.resolve_field(event_type, platform, t_agg['target_field'])
            
        if t_agg.get('group_by'):
            t_agg['group_by'] = [self.mapper.resolve_field(event_type, platform, g) for g in t_agg['group_by']]
            
        return t_agg
