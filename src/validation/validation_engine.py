from .syntax_validators import SyntaxValidator
from .semantic_validator import SemanticValidator
from .telemetry_validator import TelemetryValidator

class ValidationEngine:
    """
    Coordinates all validation stages (Syntax, Semantic, and Telemetry Sandbox).
    Returns aggregated feedback for the LangGraph Repair Node.
    """
    def __init__(self):
        self.syntax = SyntaxValidator()
        self.semantic = SemanticValidator()
        self.telemetry = TelemetryValidator()

    def run_all_validations(self, ir_dict: dict, generated_sigma: str) -> dict:
        """Runs the full validation suite and returns aggregated feedback."""
        
        # Stage 1: Syntax Validation
        syntax_res = self.syntax.validate_sigma(generated_sigma)
        
        # Stage 2: Telemetry Sandbox Execution
        sandbox_res = self.telemetry.execute_sandbox(ir_dict)
        
        # Final Determination
        is_valid = syntax_res["is_valid"] and sandbox_res.get("true_positive_fired", False)
        
        return {
            "is_valid": is_valid,
            "syntax_feedback": syntax_res,
            "sandbox_feedback": sandbox_res
        }
