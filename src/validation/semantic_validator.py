import re

class SemanticValidator:
    """
    Evaluates the Semantic Rule Equivalence (SRE) between a generated query
    and a ground-truth query using AST node overlap (Jaccard Similarity).
    """
    def _extract_nodes(self, query_str: str) -> set:
        """
        Simplified AST node extraction using regex for fields and values.
        Identifies logical constraints like field == 'value'.
        """
        nodes = set()
        pattern = r'([a-zA-Z0-9_]+)\s*(?:==|=|!=|contains)\s*[\'"]?([^\'"\s]+)[\'"]?'
        matches = re.findall(pattern, query_str)
        for field, value in matches:
            nodes.add(f"{field}:{value}")
        return nodes

    def compute_sre(self, generated_query: str, ground_truth_query: str) -> float:
        """
        Calculates SRE using Jaccard Similarity of extracted AST nodes.
        """
        nodes_gen = self._extract_nodes(generated_query)
        nodes_gt = self._extract_nodes(ground_truth_query)
        
        if not nodes_gt:
            return 0.0
            
        intersection = nodes_gen.intersection(nodes_gt)
        union = nodes_gen.union(nodes_gt)
        
        if not union:
            return 1.0
            
        return len(intersection) / len(union)
