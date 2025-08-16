#!/usr/bin/env python3
"""
LLM x 漏洞挖掘 - 内存安全漏洞静态审计系统
单一漏洞类型检测，多模型协同判断
"""

import sys
import os
import argparse
from pathlib import Path

# Add src directory to Python path
BASE_PATH = Path(__file__).resolve().parent.parent.parent  # Go up one level from src/ to repo root
sys.path.insert(0, str(BASE_PATH / "src"))

import json
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from llmtool.LLM_tool import LLMTool, LLMToolInput, LLMToolOutput
from ui.logger import Logger


class VulnType(Enum):
    NPD = "Null Pointer Dereference"
    UAF = "Use-After-Free"
    BOF = "Buffer Overflow"
    ML = "Memory Leak"


class Severity(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class Finding:
    vuln_type: VulnType
    severity: Severity
    description: str
    line_range: str
    confidence: float
    agent_id: str


class MemoryAuditInput(LLMToolInput):
    def __init__(self, code: str, bug_type: VulnType, language: str = "C"):
        self.code = code
        self.bug_type = bug_type
        self.language = language
    
    def __hash__(self):
        return hash((self.code, self.bug_type.name, self.language))


class MemoryAuditOutput(LLMToolOutput):
    def __init__(self, findings: List[Finding]):
        self.findings = findings


class VulnerabilityAnalyzer(LLMTool):
    """通用漏洞分析工具"""
    def __init__(self, model_name: str, agent_id: str, temperature: float, language: str, max_query_num: int, logger: Logger):
        super().__init__(model_name, temperature, language, max_query_num, logger)
        self.agent_id = agent_id
    
    def _get_prompt(self, input: LLMToolInput) -> str:
        # Cast input to the expected type
        audit_input = input if isinstance(input, MemoryAuditInput) else None
        if audit_input is None:
            raise ValueError("Expected MemoryAuditInput")
            
        bug_descriptions = {
            VulnType.NPD: "Null Pointer Dereference - accessing NULL pointer",
            VulnType.UAF: "Use-After-Free - using freed memory",
            VulnType.BOF: "Buffer Overflow - writing beyond buffer boundaries",
            VulnType.ML: "Memory Leak - allocated memory not freed"
        }
        
        return f"""You are a security expert who needs to check {audit_input.language} code for {bug_descriptions[audit_input.bug_type]} vulnerabilities.

Code:
```{audit_input.language}
{audit_input.code}
```

Please carefully analyze the code and focus only on {audit_input.bug_type.value} type vulnerabilities.

Return JSON format:
{{
    "findings": [
        {{
            "severity": "CRITICAL|HIGH|MEDIUM|LOW",
            "description": "Detailed description of the issue found",
            "line_range": "L1-L3",
            "confidence": 0.85
        }}
    ]
}}

If no issues are found, return an empty array. Only return JSON, no other content."""

    def _parse_response(self, response: str, input: Optional[LLMToolInput] = None) -> Optional[MemoryAuditOutput]:
        # Cast input to the expected type
        audit_input = input if isinstance(input, MemoryAuditInput) else None
        if audit_input is None:
            return MemoryAuditOutput([])
            
        try:
            # Clean the response to extract JSON
            response = response.strip()
            
            # Log the raw response for debugging
            self.logger.print_log(f"Raw response from {self.agent_id}: {response}")
            
            # Remove code block markers if present
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end]
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end]
            
            response = response.strip()
            
            # Skip empty responses
            if not response:
                self.logger.print_log(f"{self.agent_id}: Empty response after cleaning")
                return MemoryAuditOutput([])
            
            # Parse JSON
            data = json.loads(response)
            findings = []
            
            for item in data.get("findings", []):
                finding = Finding(
                    vuln_type=audit_input.bug_type,
                    severity=Severity[item["severity"]],
                    description=item["description"],
                    line_range=item["line_range"],
                    confidence=item["confidence"],
                    agent_id=self.agent_id
                )
                findings.append(finding)
            
            self.logger.print_log(f"{self.agent_id}: Parsed {len(findings)} findings")
            return MemoryAuditOutput(findings)
        except Exception as e:
            self.logger.print_log(f"Error parsing {self.agent_id} response: {e}")
            self.logger.print_log(f"Raw response: {response}")
            return MemoryAuditOutput([])


class MemoryAuditor:
    def __init__(self, bug_type: VulnType, language: str = "C", temperature: float = 0.0, 
                 model_name: str = "deepseek-chat", max_workers: int = 3):
        self.bug_type = bug_type
        self.language = language
        self.temperature = temperature
        self.model_name = model_name
        self.max_workers = max_workers
        
        # Initialize logger
        log_dir = f"{BASE_PATH}/log/swarm_audit/{bug_type.name}/{time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())}"
        os.makedirs(log_dir, exist_ok=True)
        self.logger = Logger(f"{log_dir}/audit.log")
        
        # Initialize multiple models for the same bug type
        self.agents = [
            (self.model_name, "Security Expert"),
            (self.model_name, "Static Analysis Expert"),
            (self.model_name, "Senior Programmer")
        ][:self.max_workers]
    
    def judge(self, all_findings: List[Finding]) -> List[Finding]:
        """Comprehensive judgment - at least 2 models must agree to confirm"""
        if len(all_findings) < 2:
            return []
        
        # 按位置分组
        grouped: Dict[str, List[Finding]] = {}
        for f in all_findings:
            key = f.line_range
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(f)
        
        final_findings = []
        for line_range, findings in grouped.items():
            if len(findings) >= 2:  # At least 2 models detected
                avg_confidence = sum(f.confidence for f in findings) / len(findings)
                max_severity = max(findings, key=lambda x: list(Severity).index(x.severity)).severity
                
                final_findings.append(Finding(
                    vuln_type=self.bug_type,
                    severity=max_severity,
                    description=f"Multi-model confirmation: {findings[0].description}",
                    line_range=line_range,
                    confidence=min(0.99, avg_confidence + 0.1),
                    agent_id="Judge"
                ))
        
        return final_findings
    
    def _analyze_with_agent(self, audit_input: MemoryAuditInput, model_name: str, agent_name: str) -> Optional[MemoryAuditOutput]:
        """Helper method to analyze code with a single agent"""
        analyzer = VulnerabilityAnalyzer(
            model_name, agent_name, self.temperature, 
            self.language, 5, self.logger
        )
        return analyzer.invoke(audit_input, MemoryAuditOutput)
    
    def analyze(self, code: str) -> Dict:
        """Analyze code"""
        self.logger.print_console(f"🔍 Starting {self.bug_type.value} detection...\n")
        
        audit_input = MemoryAuditInput(code, self.bug_type, self.language)
        all_findings: List[Finding] = []
        
        # Parallel invocation of multiple models
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            futures = {}
            for model_name, agent_name in self.agents:
                futures[executor.submit(self._analyze_with_agent, audit_input, model_name, agent_name)] = agent_name
            
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    output = future.result()
                    if output and output.findings:
                        all_findings.extend(output.findings)
                        self.logger.print_console(f"✅ {agent_name} found {len(output.findings)} issues")
                    else:
                        self.logger.print_console(f"✅ {agent_name} found no issues")
                except Exception as e:
                    self.logger.print_log(f"Error in {agent_name}: {e}")
                    self.logger.print_console(f"❌ {agent_name} execution failed")
        
        # Comprehensive judgment
        final_findings = self.judge(all_findings)
        
        return {
            "bug_type": self.bug_type.value,
            "total_findings": len(all_findings),
            "confirmed_findings": final_findings
        }

def configure_args():
    parser = argparse.ArgumentParser(
        description="SwarmAudit: Multi-model vulnerability detection system for memory safety issues."
    )
    parser.add_argument(
        "--bug-type",
        required=True,
        choices=["NPD", "UAF", "BOF", "ML"],
        help="Bug type to detect (NPD: Null Pointer Dereference, UAF: Use-After-Free, BOF: Buffer Overflow, ML: Memory Leak)",
    )
    parser.add_argument(
        "--language",
        default="C",
        choices=["C", "Cpp", "Java", "Python", "Go"],
        help="Programming language of the code to analyze",
    )
    parser.add_argument(
        "--model-name",
        default="deepseek-chat",
        help="The name of LLM model to use for analysis",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Temperature for LLM inference (0.0-1.0)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Maximum number of parallel workers (models) to use",
    )
    parser.add_argument(
        "--code-file",
        help="Path to code file to analyze (if not provided, uses example code)",
    )
    parser.add_argument(
        "--output-format",
        choices=["console", "json"],
        default="console",
        help="Output format for results",
    )

    args = parser.parse_args()
    return args


def validate_inputs(args: argparse.Namespace) -> Tuple[bool, List[str]]:
    """Validate command line arguments"""
    errors = []
    
    # Validate temperature range
    if not (0.0 <= args.temperature <= 1.0):
        errors.append("Temperature must be between 0.0 and 1.0")
    
    # Validate max_workers
    if args.max_workers < 1 or args.max_workers > 10:
        errors.append("Max workers must be between 1 and 10")
    
    # Validate code file if provided
    if args.code_file and not os.path.exists(args.code_file):
        errors.append(f"Code file not found: {args.code_file}")
    
    return len(errors) == 0, errors


def get_example_code(bug_type: VulnType, language: str) -> str:
    """Get example code from benchmark directory"""
    benchmark_map = {
        VulnType.UAF: {"Cpp": "benchmark/Cpp/toy/UAF/uaf-case01.cpp"},
        VulnType.NPD: {
            "Cpp": "benchmark/Cpp/toy/NPD/npd-case01.cpp",
            "Java": "benchmark/Java/toy/NPD/TestCase1.java",
            "Python": "benchmark/Python/toy/NPD/case01.py",
            "Go": "benchmark/Go/toy/nil_case01.go"
        },
        VulnType.ML: {"Cpp": "benchmark/Cpp/toy/MLK/mlk-case01.cpp"},
        VulnType.BOF: {"Go": "benchmark/Go/toy/bof_case01.go"}
    }
    
    file_path = benchmark_map.get(bug_type, {}).get(language)
    if not file_path:
        file_path = list(benchmark_map.get(bug_type, {}).values())[0]
    
    try:
        full_path = BASE_PATH / file_path
        print(f"📍 Loading example from: {full_path}")
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Error loading example code: {e}")
        return f"// Example code for {bug_type.value} in {language}"


def main():
    args = configure_args()
    
    # Validate inputs
    is_valid, errors = validate_inputs(args)
    if not is_valid:
        print("❌ Input validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Convert bug type string to enum
    bug_type = VulnType[args.bug_type]
    
    # Get code to analyze
    if args.code_file:
        try:
            with open(args.code_file, 'r', encoding='utf-8') as f:
                code = f.read()
            print(f"📂 Analyzing code from: {args.code_file}")
        except Exception as e:
            print(f"❌ Error reading file {args.code_file}: {e}")
            sys.exit(1)
    else:
        code = get_example_code(bug_type, args.language)
        print(f"📝 Using example code for {args.bug_type} in {args.language}")
    
    # Create auditor and analyze
    auditor = MemoryAuditor(
        bug_type=bug_type,
        language=args.language,
        temperature=args.temperature,
        model_name=args.model_name,
        max_workers=args.max_workers
    )
    
    report = auditor.analyze(code)
    
    # Output results
    if args.output_format == "json":
        output = {
            "bug_type": report["bug_type"],
            "total_findings": report["total_findings"],
            "confirmed_findings": [
                {
                    "severity": f.severity.value,
                    "description": f.description,
                    "line_range": f.line_range,
                    "confidence": f.confidence,
                    "agent_id": f.agent_id
                }
                for f in report["confirmed_findings"]
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n📊 {report['bug_type']} detection completed")
        print(f"📋 Found {report['total_findings']} preliminary issues, confirmed {len(report['confirmed_findings'])}\n")
        
        for f in report['confirmed_findings']:
            print(f"[{f.severity.value}] {f.description}")
            print(f"  Location: {f.line_range}, Confidence: {f.confidence:.1%}\n")


if __name__ == "__main__":
    main()
