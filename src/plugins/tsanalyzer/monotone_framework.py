"""Generic Monotone Dataflow Analysis Engine"""

from typing import List, Dict, Set, Optional, Tuple, Any
from abc import ABC, abstractmethod
# import tree_sitter

from tstool.analyzer.TS_analyzer import TSAnalyzer
from plugins.tsanalyzer.cfg_builder import ControlFlowGraph, BasicBlock


class MonotoneDataFlowAnalysis(ABC):
    
    def __init__(self, cfg: ControlFlowGraph, ts_analyzer: TSAnalyzer):
        self.cfg = cfg
        self.ts_analyzer = ts_analyzer
        self.source_code = ts_analyzer.code_in_files[cfg.function.file_path]
        
        # Initialize data flow sets for each block
        self.in_sets: Dict[int, Set[Any]] = {}
        self.out_sets: Dict[int, Set[Any]] = {}
        self.gen_sets: Dict[int, Set[Any]] = {}
        self.kill_sets: Dict[int, Set[Any]] = {}
        
        self._compute_gen_kill_sets()
    
    @abstractmethod
    def _compute_gen_kill_sets(self):
        """Compute GEN and KILL sets for each basic block
        
        This method should populate self.gen_sets and self.kill_sets for all blocks in the CFG.
        """
        pass
    
    @abstractmethod
    def _meet_operation(self, sets: List[Set[Any]]) -> Set[Any]:
        """Meet operation for combining sets
        
        Args:
            sets: List of sets to combine
            
        Returns:
            Combined set using the appropriate meet operation
            (union for forward analyses, intersection for backward analyses)
        """
        pass
    
    @abstractmethod
    def _transfer_function(self, block_id: int, in_set: Set[Any]) -> Set[Any]:
        """Transfer function for a basic block
        
        Args:
            block_id: ID of the basic block
            in_set: Input set to the block
            
        Returns:
            Output set from the block (typically GEN ∪ (IN - KILL))
        """
        pass
    
    @abstractmethod
    def is_forward_analysis(self) -> bool:
        """Return True if this is a forward analysis, False for backward"""
        pass
    
    def analyze(self, max_iterations: int = 100) -> Tuple[Dict[int, Set[Any]], Dict[int, Set[Any]]]:
        """Run the monotone dataflow analysis using fixed-point iteration
        
        Args:
            max_iterations: Maximum number of iterations before giving up
            
        Returns:
            Tuple of (in_sets, out_sets) mapping block IDs to their respective sets
        """
        # Initialize all sets
        for block_id in self.cfg.blocks:
            self.in_sets[block_id] = set()
            self.out_sets[block_id] = set()
        
        if self.is_forward_analysis():
            return self._analyze_forward(max_iterations)
        else:
            return self._analyze_backward(max_iterations)
    
    def _analyze_forward(self, max_iterations: int) -> Tuple[Dict[int, Set[Any]], Dict[int, Set[Any]]]:
        """Run forward dataflow analysis"""
        changed = True
        iteration = 0
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            
            for block_id, block in self.cfg.blocks.items():
                old_out = self.out_sets[block_id].copy()
                
                # Compute IN[B] using meet operation on predecessors
                predecessor_outs = []
                for pred in self.cfg.get_predecessors(block_id):
                    predecessor_outs.append(self.out_sets[pred.id])
                
                if predecessor_outs:
                    self.in_sets[block_id] = self._meet_operation(predecessor_outs)
                else:
                    self.in_sets[block_id] = set()
                
                # Compute OUT[B] using transfer function
                self.out_sets[block_id] = self._transfer_function(block_id, self.in_sets[block_id])
                
                if self.out_sets[block_id] != old_out:
                    changed = True
        
        return self.in_sets, self.out_sets
    
    def _analyze_backward(self, max_iterations: int) -> Tuple[Dict[int, Set[Any]], Dict[int, Set[Any]]]:
        """Run backward dataflow analysis"""
        changed = True
        iteration = 0
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            
            # Process blocks in reverse order for backward analysis
            for block_id in reversed(list(self.cfg.blocks.keys())):
                old_in = self.in_sets[block_id].copy()
                
                # Compute OUT[B] using meet operation on successors
                successor_ins = []
                for succ in self.cfg.get_successors(block_id):
                    successor_ins.append(self.in_sets[succ.id])
                
                if successor_ins:
                    self.out_sets[block_id] = self._meet_operation(successor_ins)
                else:
                    self.out_sets[block_id] = set()
                
                # Compute IN[B] using transfer function
                self.in_sets[block_id] = self._transfer_function(block_id, self.out_sets[block_id])
                
                if self.in_sets[block_id] != old_in:
                    changed = True
        
        return self.in_sets, self.out_sets
