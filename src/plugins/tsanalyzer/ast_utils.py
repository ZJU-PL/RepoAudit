"""AST Analysis Utilities
"""

from typing import List, Dict, Set, Optional, Tuple, Any
import tree_sitter

from plugins.tsanalyzer.dataflow_utils import Definition, Use


class ASTAnalysisHelper:
    """Helper class for AST analysis operations
    
    This class provides methods to extract variable definitions and uses
    from AST nodes, handling language-specific constructs appropriately.
    """
    
    def __init__(self, source_code: str):
        self.source_code = source_code
    
    def extract_definitions_from_node(self, node: tree_sitter.Node, block_id: int) -> List[Definition]:
        """Extract variable definitions from AST node
        
        Args:
            node: AST node to analyze
            block_id: ID of the basic block containing this node
            
        Returns:
            List of Definition objects found in the node
        """
        definitions = []
        line = self.source_code[:node.start_byte].count('\n') + 1
        
        if node.type in ["assignment", "augmented_assignment"]:
            target = self._get_assignment_target(node)
            if target:
                definitions.append(Definition(target, line, block_id, node))
        elif node.type in ["for_statement", "with_statement"]:
            for target in self._get_loop_or_context_targets(node):
                definitions.append(Definition(target, line, block_id, node))
        
        # Recursively check children
        for child in node.children:
            definitions.extend(self.extract_definitions_from_node(child, block_id))
        
        return definitions
    
    def extract_uses_from_node(self, node: tree_sitter.Node, block_id: int) -> List[Use]:
        """Extract variable uses from an AST node
        
        Args:
            node: AST node to analyze
            block_id: ID of the basic block containing this node
            
        Returns:
            List of Use objects found in the node
        """
        uses = []
        
        if node.type == "identifier":
            # This is a variable use (unless it's an assignment target)
            var_name = self.source_code[node.start_byte:node.end_byte]
            line = self.source_code[:node.start_byte].count('\n') + 1
            
            # Check if this identifier is not an assignment target
            if not self._is_assignment_target(node):
                uses.append(Use(var_name, line, block_id, node))
        
        # Recursively check child nodes
        for child in node.children:
            uses.extend(self.extract_uses_from_node(child, block_id))
        
        return uses
    
    def _get_assignment_target(self, node: tree_sitter.Node) -> Optional[str]:
        """Get the target variable of an assignment
        
        Args:
            node: Assignment AST node
            
        Returns:
            Variable name being assigned to, or None if not found
        """
        for child in node.children:
            if child.type == "identifier":
                return self.source_code[child.start_byte:child.end_byte]
            elif child.type in ["attribute", "subscript"]:
                # For a.b or a[i], we consider 'a' as the target
                first_child = child.children[0] if child.children else None
                if first_child and first_child.type == "identifier":
                    return self.source_code[first_child.start_byte:first_child.end_byte]
        return None
    
    def _get_loop_or_context_targets(self, node: tree_sitter.Node) -> List[str]:
        """Get target variables from for loops or with statements"""
        targets = []
        
        if node.type == "for_statement":
            for child in node.children:
                if child.type == "identifier":
                    targets.append(self.source_code[child.start_byte:child.end_byte])
                    break
        elif node.type == "with_statement":
            for child in node.children:
                if child.type == "as_pattern":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            targets.append(self.source_code[subchild.start_byte:subchild.end_byte])
        
        return targets
    
    def _is_assignment_target(self, node: tree_sitter.Node) -> bool:
        """Check if an identifier node is an assignment target"""
        parent = node.parent
        return (parent and parent.type in ["assignment", "augmented_assignment"] 
                and parent.children and parent.children[0] == node)
