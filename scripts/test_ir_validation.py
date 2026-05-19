import json
from src.ir_engine.ir_schema import SecurityIR

impossible_travel_json = """
{
  "ir_version": "1.0",
  "rule_id": "8f3a9e22-1b4d-4e9f-9a99-0e9f3b1b5f1f",
  "created_at": "2026-05-19T10:00:00Z",
  "metadata": {
    "rule_name": "Impossible Travel Detected",
    "description": "Detects a user logging in from two distinct countries within 2 hours.",
    "severity": "high",
    "tags": ["authentication", "impossible_travel"]
  },
  "detection_logic": {
    "event_type": "authentication_success",
    "filters": [
      {
        "field": "status",
        "operator": "equals",
        "value": "success"
      }
    ],
    "aggregation": {
      "function": "distinct_count",
      "target_field": "src_country",
      "group_by": ["user"],
      "threshold": {
        "operator": "greater_than",
        "value": 1
      }
    },
    "timeframe": {
      "duration": 2,
      "unit": "hours",
      "type": "sliding_window"
    }
  },
  "output_config": {
    "target_platforms": ["sigma", "kql"]
  }
}
"""

def test_ir_validation():
    print("Testing SecurityIR model_validate_json...")
    try:
        ir_obj = SecurityIR.model_validate_json(impossible_travel_json)
        print("SUCCESS: RFC-001 Impossible Travel JSON validated perfectly against Pydantic schema!")
        print(f"Rule Name: {ir_obj.metadata.rule_name}")
        print(f"Timeframe Type: {ir_obj.detection_logic.timeframe.type}")
    except Exception as e:
        print("FAILED: Schema validation threw an error!")
        print(e)
        exit(1)

if __name__ == '__main__':
    test_ir_validation()
