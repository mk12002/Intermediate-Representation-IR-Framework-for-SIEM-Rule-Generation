class FieldValidator:
    """
    Ensures that resolved fields don't contain illegal characters for their respective platforms.
    """
    @staticmethod
    def validate(field_name: str, platform: str) -> bool:
        # Basic validation placeholder. 
        # For KQL and Splunk, fields usually shouldn't contain spaces unless quoted.
        if " " in field_name:
            return False
        return True
