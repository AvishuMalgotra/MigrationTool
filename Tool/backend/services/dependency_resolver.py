from typing import List, Dict, Set, Any
import logging

logger = logging.getLogger(__name__)

class DependencyResolver:
    """
    Service for analyzing resource dependencies, sorting them, 
    and ensuring migration batches are complete.
    """

    def __init__(self, inventory_data: Dict[str, Any]):
        self.resources = {r["id"].lower(): r for r in inventory_data.get("resources", [])}
        self.edges = inventory_data.get("dependencies", [])
        
        # Build Adjacency List
        # graph[u] = [v, w] means u depends on v and w
        self.graph = {r_id: set() for r_id in self.resources}
        for edge in self.edges:
            src = edge["source"].lower()
            tgt = edge["target"].lower()
            if src in self.graph and tgt in self.resources:
                self.graph[src].add(tgt)

    def get_missing_dependencies(self, selected_ids: List[str]) -> List[str]:
        """
        Identifies resources that are required by the selected batch 
        but are NOT included in the selection.
        """
        selected_set = {rid.lower() for rid in selected_ids}
        missing = set()

        for rid in selected_set:
            if rid not in self.graph:
                continue
            
            # Check all things 'rid' depends on
            for dependency in self.graph[rid]:
                if dependency not in selected_set:
                    missing.add(dependency)
        
        return list(missing)

    def topological_sort(self, resource_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Returns the resources in dependency-sorted order.
        Dependent resources come AFTER their dependencies.
        (e.g., VNET -> Subnet -> NIC -> VM)
        """
        # Filter graph to only relevant nodes
        subset_ids = {rid.lower() for rid in resource_ids if rid.lower() in self.resources}
        
        # Calculate local in-degrees for the subgraph
        # In this context:
        # A depends on B (A -> B).
        # We want B to be created/moved BEFORE A.
        # So "sort order" should be: [B, A]
        # This is a reverse topological sort if edge is (Dependent -> Dependency)
        
        # Let's verify standard:
        # Edge: Dependent (Source) -> Dependency (Target)
        # Topological Sort: Dependency comes *after* Dependent in standard algo if edge is dest? 
        # No, "Topological sorting for Directed Acyclic Graph (DAG) is a linear ordering of vertices such that for every directed edge u v, vertex u comes before v in the ordering."
        # If A -> B (A depends on B), standard topo sort is [A, B].
        # We want [B, A] (Creation Order).
        # So we want the REVERSE of the topological sort.
        
        visited = set()
        stack = []
        
        def dfs(node):
            visited.add(node)
            if node in self.graph:
                for neighbor in self.graph[node]:
                    if neighbor in subset_ids and neighbor not in visited:
                        dfs(neighbor)
            stack.append(node)

        for rid in subset_ids:
            if rid not in visited:
                dfs(rid)

        # Stack now contains [Dependency, ..., Dependent] because we post-order append.
        # Let's trace: A -> B. DFS(A) calls DFS(B). DFS(B) finishes, checks children (none), pushes B. DFS(A) finishes, pushes A.
        # Stack: [B, A]. 
        # This corresponds to "Create B first, then A".
        # This is exactly what we want for "Ordered Batches" / IaC.
        
        sorted_ids = stack 
        
        # internal lookup to return full objects
        return [self.resources[rid] for rid in sorted_ids if rid in self.resources]
