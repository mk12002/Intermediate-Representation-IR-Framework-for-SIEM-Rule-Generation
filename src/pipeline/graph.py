from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import PipelineState
from .nodes import (preprocess, threat_intel, metadata, entity_extraction,
                     mitre_mapping, ir_builder, schema_mapper,
                     sigma_gen, kql_gen, spl_gen, validator, repair, output)
from .router import route_after_validation

def build_pipeline() -> StateGraph:
    workflow = StateGraph(PipelineState)

    # Register all nodes
    nodes = [
        ("preprocess", preprocess), ("threat_intel", threat_intel),
        ("metadata", metadata), ("entity_extraction", entity_extraction),
        ("mitre_mapping", mitre_mapping), ("ir_builder", ir_builder),
        ("schema_mapper", schema_mapper), ("sigma_gen", sigma_gen),
        ("kql_gen", kql_gen), ("spl_gen", spl_gen),
        ("validator", validator), ("repair", repair), ("output", output)
    ]
    for name, fn in nodes:
        workflow.add_node(name, fn)

    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "threat_intel")
    
    # Parallel execution for extraction agents
    for node in ["metadata", "entity_extraction", "mitre_mapping"]:
        workflow.add_edge("threat_intel", node)
        workflow.add_edge(node, "ir_builder")
        
    workflow.add_edge("ir_builder", "schema_mapper")
    
    # Parallel execution for generators
    for gen in ["sigma_gen", "kql_gen", "spl_gen"]:
        workflow.add_edge("schema_mapper", gen)
        workflow.add_edge(gen, "validator")
        
    workflow.add_conditional_edges(
        "validator", 
        route_after_validation,
        {"pass": "output", "repair": "repair", "max_retries": "output"}
    )
    
    workflow.add_edge("repair", "ir_builder")
    workflow.add_edge("output", END)

    # Use MemorySaver for now until SQLite integration is ready
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
