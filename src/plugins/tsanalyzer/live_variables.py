"""Live Variable Analysis
"""

from typing import List, Dict, Set, Optional, Tuple, Any
import tree_sitter

from tstool.analyzer.TS_analyzer import TSAnalyzer
from plugins.tsanalyzer.cfg_builder import ControlFlowGraph, BasicBlock
from plugins.tsanalyzer.monotone_framework import MonotoneDataFlowAnalysis
from plugins.tsanalyzer.dataflow_utils import Definition, Use
from plugins.tsanalyzer.ast_utils import ASTAnalysisHelper


class LiveVariables(MonotoneDataFlowAnalysis):
    """Live Variable Analysis
    
    A backward dataflow analysis that computes which variables are live (may be used in the future) at each program point. 
    """
    
    def __init__(self, cfg: ControlFlowGraph, ts_analyzer: TSAnalyzer):
        self.all_uses: Dict[int, List[Use]] = {}
        self.ast_helper = ASTAnalysisHelper(ts_analyzer.code_in_files[cfg.function.file_path])
        super().__init__(cfg, ts_analyzer)
    
    def is_forward_analysis(self) -> bool:
        """Live variables is a backward analysis"""
        return False
    
    def _compute_gen_kill_sets(self):
        """Compute GEN and KILL sets for live variables
        
        GEN[B] = variables used in block B (before being defined)
        KILL[B] = variables defined in block B
        """
        for block_id, block in self.cfg.blocks.items():
            self.gen_sets[block_id] = set()
            self.kill_sets[block_id] = set()
            
            # Find all uses and definitions in this block
            uses = self._find_uses_in_block(block)
            definitions = self._find_definitions_in_block(block)
            
            self.all_uses[block_id] = uses
            
            # GEN set: variables used in this block (before being defined)
            defined_vars = {defn.variable for defn in definitions}
            for use in uses:
                if use.variable not in defined_vars:
                    self.gen_sets[block_id].add(use.variable)
            
            # KILL set: variables defined in this block
            for defn in definitions:
                self.kill_sets[block_id].add(defn.variable)
    
    def _find_uses_in_block(self, block: BasicBlock) -> List[Use]:
        """Find all variable uses in a basic block
        
        Args:
            block: Basic block to analyze
            
        Returns:
            List of uses found in the block
        """
        uses = []
        
        for stmt in block.statements:
            stmt_uses = self.ast_helper.extract_uses_from_node(stmt, block.id)
            uses.extend(stmt_uses)
        
        return uses
    
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
    
    def _meet_operation(self, sets: List[Set[str]]) -> Set[str]:
        """Union operation for live variables
        
        The meet operation for live variables is union because
        a variable is live if it's live on any successor path.
        """
        return set().union(*sets) if sets else set()
    
    def _transfer_function(self, block_id: int, out_set: Set[str]) -> Set[str]:
        """Transfer function for backward analysis: IN[B] = GEN[B] ∪ (OUT[B] - KILL[B])
        
        Args:
            block_id: ID of the basic block
            out_set: Set of live variables at the exit of the block
            
        Returns:
            Set of live variables at the entry of the block
        """
        return self.gen_sets[block_id].union(out_set - self.kill_sets[block_id])
