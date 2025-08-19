"""
TSAnalyzer Plugin for Advanced Static Analysis

This plugin extends the basic TSAnalyzer capabilities with:
- Control Flow Graph (CFG) construction
- Data flow analysis (reaching definitions, live variables)
- Basic block identification
- Dependency analysis
"""

from .cfg_builder import CFGBuilder, BasicBlock, ControlFlowGraph

from .reaching_definitions import ReachingDefinitions
from .live_variables import LiveVariables
from .dataflow_utils import Definition, Use, DataFlowElement, AnalysisResult, DataFlowResult, AnalysisMetrics
from .monotone_framework import MonotoneDataFlowAnalysis


__all__ = [
    'CFGBuilder',
    'BasicBlock', 
    'ControlFlowGraph',

    'ReachingDefinitions',
    'LiveVariables',
    'Definition',
    'Use',
    'DataFlowElement',
    'MonotoneDataFlowAnalysis',
    'AnalysisResult',
    'DataFlowResult',
    'AnalysisMetrics'
]
