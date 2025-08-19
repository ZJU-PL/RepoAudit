"""Reaching Definitions Analysis
"""

from typing import List, Dict, Set, Optional, Tuple, Any
import tree_sitter

from tstool.analyzer.TS_analyzer import TSAnalyzer
from plugins.tsanalyzer.cfg_builder import ControlFlowGraph, BasicBlock
from plugins.tsanalyzer.monotone_framework import MonotoneDataFlowAnalysis
from plugins.tsanalyzer.dataflow_utils import Definition, Use
from plugins.tsanalyzer.ast_utils import ASTAnalysisHelper


class ReachingDefinitions(MonotoneDataFlowAnalysis):
    """Reaching Definitions Analysis
    
    A forward dataflow analysis that computes which definitions reach each program point. 
    """
    
    def __init__(self, cfg: ControlFlowGraph, ts_analyzer: TSAnalyzer):
        self.all_definitions: Dict[int, List[Definition]] = {}
        self.ast_helper = ASTAnalysisHelper(ts_analyzer.code_in_files[cfg.function.file_path])
        super().__init__(cfg, ts_analyzer)
    
    def is_forward_analysis(self) -> bool:
        """Reaching definitions is a forward analysis"""
        return True
    
    def _compute_gen_kill_sets(self):
        """Compute GEN and KILL sets for reaching definitions
        
        GEN[B] = definitions generated in block B
        KILL[B] = definitions killed by block B (other definitions of same variables)
        """
        for block_id, block in self.cfg.blocks.items():
            self.gen_sets[block_id] = set()
            self.kill_sets[block_id] = set()
            
            # Find all definitions in this block
            definitions = self._find_definitions_in_block(block)
            self.all_definitions[block_id] = definitions
            
            # GEN set: definitions generated in this block
            for defn in definitions:
                self.gen_sets[block_id].add(defn)
            
            # KILL set: definitions of the same variable killed by this block
            for defn in definitions:
                # Find all other definitions of the same variable
                for other_block_id, other_block in self.cfg.blocks.items():
                    if other_block_id != block_id:
                        other_definitions = self._find_definitions_in_block(other_block)
                        for other_defn in other_definitions:
                            if other_defn.variable == defn.variable:
                                self.kill_sets[block_id].add(other_defn)
    
    def _find_definitions_in_block(self, block: BasicBlock) -> List[Definition]:
        """Find all variable definitions in a basic block
        
        Args:
            block: Basic block to analyze
            
        Returns:
            List of definitions found in the block
        """
        definitions = []
        
        for stmt in block.statements:
            defs = self.ast_helper.extract_definitions_from_node(stmt, block.id)
            definitions.extend(defs)
        
        return definitions
    
    def _meet_operation(self, sets: List[Set[Definition]]) -> Set[Definition]:
        """Union operation for reaching definitions
        
        The meet operation for reaching definitions is union because
        a definition reaches a point if it reaches via any path.
        """
        return set().union(*sets) if sets else set()
    
    def _transfer_function(self, block_id: int, in_set: Set[Definition]) -> Set[Definition]:
        """Transfer function: OUT[B] = GEN[B] ∪ (IN[B] - KILL[B])
        
        Args:
            block_id: ID of the basic block
            in_set: Set of definitions reaching the entry of the block
            
        Returns:
            Set of definitions reaching the exit of the block
        """
        return self.gen_sets[block_id].union(in_set - self.kill_sets[block_id])
