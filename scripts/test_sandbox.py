from src.validation.telemetry_validator import TelemetryValidator

ir_example = {
    "detection_logic": {
        "event_type": "authentication_success",
        "filters": [
            {
                "field": "action",
                "operator": "equals",
                "value": "failure"
            }
        ]
    }
}

def test_sandbox():
    print("Testing Telemetry Sandbox Execution...")
    validator = TelemetryValidator()
    result = validator.execute_sandbox(ir_example)
    
    print("\n--- Sandbox Result ---")
    print(f"Status: {result.get('execution_status')}")
    print(f"True Positives: {result.get('true_positives')}")
    print(f"False Positives: {result.get('false_positives_detected')}")
    print(f"Error Msg: {result.get('error_message')}")
    
    if result.get('true_positives', 0) == 5 and result.get('false_positives_detected') == 0:
        print("\nSUCCESS: Sandbox correctly identified the 5 injected positive samples and filtered out the 95 negative samples via Pandas logic!")
    else:
        print("\nFAILED: Sandbox math is incorrect or Faker is missing.")

if __name__ == '__main__':
    test_sandbox()
