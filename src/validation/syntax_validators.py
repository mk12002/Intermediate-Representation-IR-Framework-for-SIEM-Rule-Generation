import yaml
from sigma.collection import SigmaCollection
from sigma.exceptions import SigmaError

class SyntaxValidator:
    """
    Validates generated rule syntax. Uses pySigma for Sigma YAML validation.
    """
    def validate_sigma(self, sigma_rule_str: str) -> dict:
        try:
            # Parse YAML first to ensure it's valid YAML
            yaml.safe_load(sigma_rule_str)
            # Then validate using pysigma core
            SigmaCollection.from_yaml(sigma_rule_str)
            return {"is_valid": True, "error": None}
        except (yaml.YAMLError, SigmaError, Exception) as e:
            return {"is_valid": False, "error": str(e)}
