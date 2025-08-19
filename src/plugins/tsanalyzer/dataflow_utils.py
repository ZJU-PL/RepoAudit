"""Basic Elements for Dataflow Analysis"""

from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import tree_sitter

from memory.syntactic.function import Function


class DataFlowElement(ABC):
    """Abstract base class for dataflow analysis elements"""
    
    @abstractmethod
    def __hash__(self):
        pass
    
    @abstractmethod
    def __eq__(self, other):
        pass
    
    @abstractmethod
    def __str__(self):
        pass


@dataclass
class Definition(DataFlowElement):
    """Variable definition
    
    Represents a point in the program where a variable is assigned a value.
    """
    variable: str
    line: int
    block_id: int
    node: tree_sitter.Node
    
    def __hash__(self):
        return hash((self.variable, self.line, self.block_id))
    
    def __eq__(self, other):
        if not isinstance(other, Definition):
            return False
        return (self.variable == other.variable and 
                self.line == other.line and 
                self.block_id == other.block_id)
    
    def __str__(self):
        return f"def({self.variable}@{self.line})"


@dataclass
class Use(DataFlowElement):
    """Variable use
    
    Represents a point in the program where a variable's value is read.
    """
    variable: str
    line: int
    block_id: int
    node: tree_sitter.Node
    
    def __hash__(self):
        return hash((self.variable, self.line, self.block_id))
    
    def __eq__(self, other):
        if not isinstance(other, Use):
            return False
        return (self.variable == other.variable and 
                self.line == other.line and 
                self.block_id == other.block_id)
    
    def __str__(self):
        return f"use({self.variable}@{self.line})"


@dataclass
class AnalysisResult:
    """Base class for analysis results"""
    function: Function
    success: bool
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if not self.success and not self.error_message:
            self.error_message = "Analysis failed with unknown error"


@dataclass
class DataFlowResult(AnalysisResult):
    """Result of dataflow analysis"""
    in_sets: Dict[int, Set[DataFlowElement]] = None
    out_sets: Dict[int, Set[DataFlowElement]] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.in_sets is None:
            self.in_sets = {}
        if self.out_sets is None:
            self.out_sets = {}


@dataclass  
class AnalysisMetrics:
    """Metrics for analysis performance"""
    iterations: int = 0
    time_elapsed: float = 0.0
    blocks_analyzed: int = 0


