try:
    from faker import Faker
except ImportError:
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
                "action": "success",
                "status": "success" # Adding status for the Impossible Travel example
            })
            
        # Generate Positive Samples (Triggering conditions extracted from IR)
        for _ in range(num_positive):
            pos_log = {
                "src_ip": self.faker.ipv4(),
                "user": self.faker.user_name(),
                "action": "failure",
                "status": "failure"
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
        Simulates local sandbox execution by filtering the mock DataFrame 
        using Pandas logic, returning actual calculated TP/FP counts.
        """
        df = self.generate_mock_logs(ir_dict)
        if df.empty:
            return {"execution_status": "error", "error_message": "Faker not installed, no telemetry generated."}
            
        logic = ir_dict.get("detection_logic", {})
        filters = logic.get("filters", [])
        
        # Start with all True mask
        mask = pd.Series([True] * len(df), index=df.index)
        
        # Apply filters programmatically
        for f in filters:
            field = f.get('field')
            op = f.get('operator')
            val = f.get('value')
            
            if field not in df.columns:
                continue
                
            if op == 'equals':
                mask = mask & (df[field] == val)
            elif op == 'contains':
                mask = mask & (df[field].astype(str).str.contains(str(val), na=False))
            elif op == 'not_equals':
                mask = mask & (df[field] != val)
                
        filtered_df = df[mask]
        
        # Evaluate against our known ground truth labels from the generator
        # (Positive samples had action/status forced by filters, but originated from the failure loop block)
        # Since we force-injected the fields, we can just assume rows matching the injected filter are the TPs.
        # But wait, if a negative sample accidentally matched, it's an FP.
        # Let's use the index: the last 'num_positive' rows were the positives.
        num_positive = 5
        positive_indices = set(df.index[-num_positive:])
        
        detected_indices = set(filtered_df.index)
        
        true_positives = len(detected_indices.intersection(positive_indices))
        false_positives = len(detected_indices - positive_indices)
        
        return {
            "execution_status": "success",
            "true_positive_fired": true_positives > 0,
            "true_positives": true_positives,
            "false_positives_detected": false_positives,
            "error_message": None if true_positives > 0 else "Rule failed to trigger on positive samples.",
            "recommendation": "Sandbox execution complete."
        }
