import logging

logging.basicConfig(level=logging.INFO)

def mock_validator(state):
    print(f"--> [Node: validator] Attempt {state.get('repair_count', 0) + 1}")
    errors = state.get("errors", [])
    repair_count = state.get("repair_count", 0)
    
    if repair_count < 2:
        print(f"    Validation Failed. Pushing error.")
        return {"errors": errors + ["Mock ValidationError: field X missing"], "validation_results": {"passed": False}}
    else:
        print(f"    Validation Succeeded! Clearing errors.")
        return {"errors": [], "validation_results": {"passed": True}}

def test_graph_routing():
    print("\n--- Testing LangGraph Conditional Edges ---")
    
    import src.pipeline.nodes as nodes
    
    nodes.validator = mock_validator
    
    from langgraph.graph import StateGraph
    from src.pipeline.state import PipelineState
    from src.pipeline.router import route_after_validation
    
    workflow = StateGraph(PipelineState)
    workflow.add_node("preprocess", nodes.preprocess)
    workflow.add_node("threat_intel", nodes.threat_intel)
    workflow.add_node("entity_extraction", nodes.entity_extraction)
    workflow.add_node("metadata", nodes.metadata)
    workflow.add_node("mitre_mapping", nodes.mitre_mapping)
    workflow.add_node("ir_builder", nodes.ir_builder)
    workflow.add_node("schema_mapper", nodes.schema_mapper)
    workflow.add_node("sigma_gen", nodes.sigma_gen)
    workflow.add_node("kql_gen", nodes.kql_gen)
    workflow.add_node("spl_gen", nodes.spl_gen)
    workflow.add_node("validator", nodes.validator)
    workflow.add_node("repair", nodes.repair)
    workflow.add_node("output", nodes.output)
    
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "threat_intel")
    workflow.add_edge("threat_intel", "metadata")
    workflow.add_edge("metadata", "entity_extraction")
    workflow.add_edge("entity_extraction", "mitre_mapping")
    workflow.add_edge("mitre_mapping", "ir_builder")
    workflow.add_edge("ir_builder", "schema_mapper")
    workflow.add_edge("schema_mapper", "sigma_gen")
    workflow.add_edge("sigma_gen", "kql_gen")
    workflow.add_edge("kql_gen", "spl_gen")
    workflow.add_edge("spl_gen", "validator")
    
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "repair": "repair",
            "pass": "output",
            "max_retries": "output"
        }
    )
    workflow.add_edge("repair", "ir_builder")
    workflow.set_finish_point("output")
    
    app_test = workflow.compile()
    
    # Run the graph
    initial_state = {"raw_report": "Dummy report", "repair_count": 0, "errors": []}
    
    print("Starting execution trace...\n")
    final_state = app_test.invoke(initial_state)
    
    print("\n--- Execution Finished ---")
    print(f"Final Repair Count: {final_state.get('repair_count')}")
    print(f"Errors remaining: {len(final_state.get('errors', []))}")
    if final_state.get('repair_count') == 2:
        print("SUCCESS: LangGraph successfully looped through repair twice and exited correctly!")
    else:
        print("FAILED: Graph routing logic broke.")

if __name__ == '__main__':
    test_graph_routing()
