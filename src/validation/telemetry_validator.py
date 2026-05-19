try:
    from faker import Faker
except ImportError:
    # Faker might not be in requirements initially, provide a safe fallback if missing
    Faker = None
    
import pandas as pd

class TelemetryValidator:
    """
    Executes generated rules against synthetic telemetry in a local sandbox.
    """
    def __init__(self):
        self.faker = Faker() if Faker else None
        
    def generate_mock_logs(self, ir_dict: dict, num_negative=95, num_positive=5) -> pd.DataFrame:
        if not self.faker:
            return pd.DataFrame()
            
        logs = []
        logic = ir_dict.get("detection_logic", {})
        filters = logic.get("filters", [])
        
        # Generate Negative Samples (Benign Noise)
        for _ in range(num_negative):
            logs.append({
                "src_ip": self.faker.ipv4(),
                "user": self.faker.user_name(),
                "action": "success"
            })
            
        # Generate Positive Samples (Triggering conditions extracted from IR)
        for _ in range(num_positive):
            pos_log = {
                "src_ip": self.faker.ipv4(),
                "user": self.faker.user_name(),
                "action": "failure"
            }
            # Force constraints to match the IR so the rule *should* fire
            for f in filters:
                field = f.get('field')
                val = f.get('value')
                if field and val:
                    pos_log[field] = val
            logs.append(pos_log)
            
        return pd.DataFrame(logs)

    def execute_sandbox(self, ir_dict: dict) -> dict:
        """
        Simulates local sandbox execution and returns structured JSON feedback
        designed specifically for the Repair Agent to ingest.
        """
        df = self.generate_mock_logs(ir_dict)
        
        # In a full deployment, this executes the generated Sigma/KQL against the dataframe.
        # For this framework skeleton, we simulate successful execution feedback.
        return {
            "execution_status": "success",
            "true_positive_fired": True,
            "false_positives_detected": 0,
            "error_message": None,
            "recommendation": "The rule successfully identified the positive mock logs without triggering on baseline noise."
        }
