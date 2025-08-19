#!/usr/bin/env python3
"""CFG Builder and Dataflow Analysis Test"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tstool.analyzer.Python_TS_analyzer import Python_TSAnalyzer
from memory.syntactic.function import Function
from plugins.tsanalyzer.cfg_builder import CFGBuilder
from plugins.tsanalyzer.reaching_definitions import ReachingDefinitions
from plugins.tsanalyzer.live_variables import LiveVariables


def get_stdlib_source(module_name):
    """Get stdlib module source code"""
    try:
        module = __import__(module_name)
        if hasattr(module, '__file__') and module.__file__:
            with open(module.__file__, 'r') as f:
                return module.__file__, f.read()
    except Exception as e:
        print(f"Error: {e}")
    return None, None


def analyze_function(ts_analyzer, function_name, source_code):
    """Analyze function with CFG and dataflow analysis"""
    if function_name not in ts_analyzer.functionNameToId:
        return None
    
    # Get function data
    function_id = next(iter(ts_analyzer.functionNameToId[function_name]))
    func_data = ts_analyzer.functionRawDataDic[function_id]
    file_path = ts_analyzer.functionToFile[function_id]
    
    # Extract function code
    lines = source_code.split('\n')
    function_code = '\n'.join(lines[func_data[1]-1:func_data[2]])
    
    function = Function(
        function_id=function_id,
        function_name=func_data[0],
        function_code=function_code,
        start_line_number=func_data[1],
        end_line_number=func_data[2],
        function_node=func_data[3],
        file_path=file_path
    )
    
    print(f"\n=== {function_name} (lines {func_data[1]}-{func_data[2]}) ===")
    
    try:
        # Build CFG
        cfg = CFGBuilder(ts_analyzer).build_cfg(function)
        print(f"✓ CFG: {cfg.get_block_count()} blocks, {cfg.get_edge_count()} edges")
        
        # Run analyses
        rd_analysis = ReachingDefinitions(cfg, ts_analyzer)
        rd_in, rd_out = rd_analysis.analyze()
        print(f"✓ Reaching definitions completed")
        
        lv_analysis = LiveVariables(cfg, ts_analyzer)  
        lv_in, lv_out = lv_analysis.analyze()
        print(f"✓ Live variables completed")
        
        # Save DOT with statement details
        with open(f"cfg_{function_name}.dot", 'w') as f:
            f.write(cfg.to_dot(source_code))
        print(f"✓ DOT saved: cfg_{function_name}.dot")
        
        return True
        
    except Exception as e:
        print(f"✗ Analysis failed: {e}")
        return False


def main():
    """Test CFG and dataflow analysis on Python stdlib"""
    print("CFG Builder and Dataflow Analysis Test")
    print("=====================================")
    
    module_path, source_code = get_stdlib_source('heapq')
    if not module_path:
        print("Could not load heapq module")
        return
    
    print(f"Module: {module_path}")
    print(f"Size: {len(source_code)} chars")
    
    # Initialize analyzer
    ts_analyzer = Python_TSAnalyzer({module_path: source_code}, "Python")
    print(f"Found {len(ts_analyzer.functionNameToId)} functions")
    
    # Test first 3 functions
    success_count = 0
    for func_name in list(ts_analyzer.functionNameToId.keys())[:3]:
        if analyze_function(ts_analyzer, func_name, source_code):
            success_count += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"✓ {success_count}/3 functions analyzed successfully")
    print("DOT files generated for visualization")


if __name__ == "__main__":
    main()
