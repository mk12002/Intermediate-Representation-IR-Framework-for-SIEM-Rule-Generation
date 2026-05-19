from pydantic import ValidationError
from typing import Tuple, List, Optional
from .ir_schema import SecurityIR

class IRValidator:
    """
    Validates structural integrity and constraints of the Intermediate Representation.
    """
    
    @staticmethod
    def validate_dict(ir_data: dict) -> Tuple[bool, List[str], Optional[SecurityIR]]:
        """
        Validates a raw dictionary against the SecurityIR schema.
        Returns: (is_valid, list_of_errors, parsed_model_or_none)
        """
        try:
            ir_model = SecurityIR.model_validate(ir_data)
            return True, [], ir_model
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = " -> ".join([str(loc) for loc in err['loc']])
                msg = err['msg']
                errors.append(f"Field '{loc}': {msg}")
            return False, errors, None
            
    @staticmethod
    def validate_logic_coherence(ir: SecurityIR) -> List[str]:
        """
        Performs higher-level semantic checks that Pydantic alone might not catch.
        """
        errors = []
        dl = ir.detection_logic
        
        # Aggregation needs a timeframe to make sense
        if dl.aggregation is not None and dl.timeframe is None:
            errors.append("Aggregation logic is present but no timeframe is specified.")
            
        # Correlated events (if present) must have a timeframe
        if ir.temporal_logic and ir.temporal_logic.correlations:
            if not dl.timeframe:
                 errors.append("Temporal correlations require a timeframe.")
                 
        return errors
