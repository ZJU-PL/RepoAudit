import json
from typing import Dict, List, Optional, Any

from llmtool.LLM_tool import LLMTool, LLMToolInput, LLMToolOutput
from memory.syntactic.function import Function
from tstool.analyzer.TS_analyzer import TSAnalyzer
from ui.logger import Logger


class NullabilityAnalysisInput(LLMToolInput):
    def __init__(self, function: Function, function_code: str, language: str):
        super().__init__()
        self.function = function
        self.function_code = function_code
        self.language = language
    
    def __hash__(self):
        return hash((self.function.function_id, self.function_code, self.language))


class NullabilityAnalysisOutput(LLMToolOutput):
    def __init__(self, parameters: List[Dict], return_values: List[Dict], 
                 callee_arguments: List[Dict], raw_response: str):
        super().__init__()
        self.parameters = parameters
        self.return_values = return_values
        self.callee_arguments = callee_arguments
        self.raw_response = raw_response
    
    def __str__(self):
        return f"NullabilityAnalysis(params={len(self.parameters)}, returns={len(self.return_values)}, args={len(self.callee_arguments)})"


class NullabilityExtractor(LLMTool):
    def _get_prompt(self, input: LLMToolInput) -> str:
        # Cast to the specific type we know it is
        nullability_input = input if isinstance(input, NullabilityAnalysisInput) else None
        if nullability_input is None:
            raise TypeError("Expected NullabilityAnalysisInput")
            
        return f"""You are an expert code analyzer for {self.language} nullability analysis.

Analyze this function for nullability patterns:
Function: {nullability_input.function.function_name}
```{self.language}
{nullability_input.function_code}
```

Return JSON with nullability analysis:
{{
  "parameters": [
    {{
      "name": "param_name",
      "nullability": "nullable|non_nullable|conditional|unknown",
      "conditions": "when null",
      "line_number": line_num,
      "confidence": "high|medium|low"
    }}
  ],
  "return_values": [
    {{
      "expression": "return_expr",
      "nullability": "nullable|non_nullable|conditional|unknown",
      "conditions": "when null",
      "line_number": line_num,
      "confidence": "high|medium|low"
    }}
  ],
  "callee_arguments": [
    {{
      "callee_name": "func_name",
      "argument_name": "arg_name",
      "argument_position": pos,
      "nullability": "nullable|non_nullable|conditional|unknown",
      "conditions": "constraints",
      "line_number": line_num,
      "confidence": "high|medium|low"
    }}
  ]
}}

Only return the JSON object."""
    
    def _parse_response(self, response: str, input: Optional[LLMToolInput] = None) -> Optional[LLMToolOutput]:
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response.strip())
            return NullabilityAnalysisOutput(
                result.get("parameters", []),
                result.get("return_values", []),
                result.get("callee_arguments", []),
                response
            )
        except Exception as e:
            self.logger.print_log(f"Parse error: {e}")
            return None


class NullabilitySummarizer:
    def __init__(self, ts_analyzer: TSAnalyzer, model_name: str = "gpt-4", 
                 temperature: float = 0.1, logger: Optional[Logger] = None):
        self.ts_analyzer = ts_analyzer
        self.logger = logger or Logger(log_file_path="nullability_analysis.log")
        self.extractor = NullabilityExtractor(model_name, temperature, 
                                            ts_analyzer.language_name, 3, self.logger)
        self.function_nullability: Dict[int, NullabilityAnalysisOutput] = {}
    
    def analyze_function(self, function: Function) -> Optional[NullabilityAnalysisOutput]:
        try:
            file_content = self.ts_analyzer.code_in_files[function.file_path]
            function_code = file_content[function.parse_tree_root_node.start_byte:function.parse_tree_root_node.end_byte]
            
            result = self.extractor.invoke(NullabilityAnalysisInput(function, function_code, self.ts_analyzer.language_name), 
                                         NullabilityAnalysisOutput)
            if result:
                self.function_nullability[function.function_id] = result
            return result
        except Exception as e:
            self.logger.print_log(f"Error analyzing {function.function_name}: {e}")
            return None
    
    def analyze_all_functions(self) -> Dict[int, NullabilityAnalysisOutput]:
        for function_id, function in self.ts_analyzer.function_env.items():
            if "test" not in function.file_path.lower():
                self.analyze_function(function)
        return self.function_nullability
    
    def get_nullable_items(self, function_id: int, item_type: str) -> List[Dict]:
        result = self.function_nullability.get(function_id)
        if not result:
            return []
        items = getattr(result, item_type, [])
        return [item for item in items if item.get("nullability") in ["nullable", "conditional"]]
    
    def export_summary(self, output_file: str) -> None:
        summary = {
            "metadata": {"total_functions": len(self.function_nullability), 
                        "language": self.ts_analyzer.language_name},
            "functions": {}
        }
        
        for function_id, result in self.function_nullability.items():
            function = self.ts_analyzer.function_env[function_id]
            summary["functions"][str(function_id)] = {
                "function_name": function.function_name,
                "file_path": function.file_path,
                "parameters": result.parameters,
                "return_values": result.return_values,
                "callee_arguments": result.callee_arguments
            }
        
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)


def create_nullability_analyzer(ts_analyzer: TSAnalyzer, model_name: str = "gpt-4", 
                               logger: Optional[Logger] = None) -> NullabilitySummarizer:
    return NullabilitySummarizer(ts_analyzer, model_name, logger=logger)
