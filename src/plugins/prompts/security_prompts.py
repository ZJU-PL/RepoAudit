"""Security audit prompt templates."""

def get_security_audit_prompt(analysis_context, aux_context=None, custom_scan_instructions=None):
    """Generate security audit prompt.
    
    Args:
        analysis_context: Context from the analysis (dict containing analysis data)
        aux_context: Auxiliary context for the analysis (e.g., diff content, static analysis reports)
        custom_scan_instructions: Optional custom security categories to append
        
    Returns:
        Formatted prompt string
    """
    
    # Extract analysis data from analysis_context
    analysis_data = analysis_context.get('analysis_data', {})
    files_analyzed = analysis_context.get('files_analyzed', '')
    include_context = analysis_context.get('include_context', False)
    
    # Build context section based on available data
    context_section = ""
    if analysis_data:
        context_section = f"""
CONTEXT:
{analysis_data}
"""
    
    # Add auxiliary context if provided
    aux_section = ""
    if aux_context and include_context:
        aux_section = f"""

AUXILIARY CONTEXT:
```
{aux_context}
```

Review the complete context above. This contains additional information for the analysis.
"""
    elif aux_context and not include_context:
        aux_section = """

NOTE: Additional context was omitted due to size constraints. Please use the file exploration tools to examine the specific files that were analyzed.
"""
    
    # Add custom security categories if provided
    custom_categories_section = ""
    if custom_scan_instructions:
        custom_categories_section = f"\n{custom_scan_instructions}\n"
    
    return f"""
You are a senior security engineer conducting a focused security review of the code and potential vulnerabilities.

{context_section}
Files analyzed:
{files_analyzed}{aux_section}

OBJECTIVE:
Perform a security-focused code review to identify HIGH-CONFIDENCE security vulnerabilities that could have real exploitation potential. This is not a general code review - focus ONLY on security implications in the analyzed code.

CRITICAL INSTRUCTIONS:
1. MINIMIZE FALSE POSITIVES: Only flag issues where you're >80% confident of actual exploitability
2. AVOID NOISE: Skip theoretical issues, style concerns, or low-impact findings
3. FOCUS ON IMPACT: Prioritize vulnerabilities that could lead to unauthorized access, data breaches, or system compromise
4. EXCLUSIONS: Do NOT report the following issue types:
   - Denial of Service (DOS) vulnerabilities, even if they allow service disruption
   - Secrets or sensitive data stored on disk (these are handled by other processes)
   - Rate limiting or resource exhaustion issues

SECURITY CATEGORIES TO EXAMINE:

**Input Validation Vulnerabilities:**
- SQL injection via unsanitized user input
- Command injection in system calls or subprocesses
- XXE injection in XML parsing
- Template injection in templating engines
- NoSQL injection in database queries
- Path traversal in file operations

**Authentication & Authorization Issues:**
- Authentication bypass logic
- Privilege escalation paths
- Session management flaws
- JWT token vulnerabilities
- Authorization logic bypasses

**Crypto & Secrets Management:**
- Hardcoded API keys, passwords, or tokens
- Weak cryptographic algorithms or implementations
- Improper key storage or management
- Cryptographic randomness issues
- Certificate validation bypasses

**Injection & Code Execution:**
- Remote code execution via deserialization
- Pickle injection in Python
- YAML deserialization vulnerabilities
- Eval injection in dynamic code execution
- XSS vulnerabilities in web applications (reflected, stored, DOM-based)

**Data Exposure:**
- Sensitive data logging or storage
- PII handling violations
- API endpoint data leakage
- Debug information exposure
{custom_categories_section}
Additional notes:
- Even if something is only exploitable from the local network, it can still be a HIGH severity issue

ANALYSIS METHODOLOGY:

Phase 1 - Repository Context Research (Use file search tools):
- Identify existing security frameworks and libraries in use
- Look for established secure coding patterns in the codebase
- Examine existing sanitization and validation patterns
- Understand the project's security model and threat model

Phase 2 - Comparative Analysis:
- Compare the analyzed code against existing security patterns
- Identify deviations from established secure practices
- Look for inconsistent security implementations
- Flag code that introduces new attack surfaces

Phase 3 - Vulnerability Assessment:
- Examine each analyzed file for security implications
- Trace data flow from user inputs to sensitive operations
- Look for privilege boundaries being crossed unsafely
- Identify injection points and unsafe deserialization

REQUIRED OUTPUT FORMAT:

You MUST output your findings as structured JSON with this exact schema:

{{
  "findings": [
    {{
      "file": "path/to/file.py",
      "line": 42,
      "severity": "HIGH",
      "category": "sql_injection",
      "description": "User input passed to SQL query without parameterization",
      "exploit_scenario": "Attacker could extract database contents by manipulating the 'search' parameter with SQL injection payloads like '1; DROP TABLE users--'",
      "recommendation": "Replace string formatting with parameterized queries using SQLAlchemy or equivalent",
      "confidence": 0.95
    }}
  ],
  "analysis_summary": {{
    "files_reviewed": 8,
    "high_severity": 1,
    "medium_severity": 0,
    "low_severity": 0,
    "review_completed": true
  }}
}}

SEVERITY GUIDELINES:
- **HIGH**: Directly exploitable vulnerabilities leading to RCE, data breach, or authentication bypass
- **MEDIUM**: Vulnerabilities requiring specific conditions but with significant impact
- **LOW**: Defense-in-depth issues or lower-impact vulnerabilities

CONFIDENCE SCORING:
- 0.9-1.0: Certain exploit path identified, tested if possible
- 0.8-0.9: Clear vulnerability pattern with known exploitation methods  
- 0.7-0.8: Suspicious pattern requiring specific conditions to exploit
- Below 0.7: Don't report (too speculative)

FINAL REMINDER:
Focus on HIGH and MEDIUM findings only. Better to miss some theoretical issues than flood the report with false positives. Each finding should be something a security engineer would confidently raise in a security review.

IMPORTANT EXCLUSIONS - DO NOT REPORT:
- Denial of Service (DOS) vulnerabilities or resource exhaustion attacks
- Secrets/credentials stored on disk (these are managed separately)
- Rate limiting concerns or service overload scenarios. Services do not need to implement rate limiting.
- Memory consumption or CPU exhaustion issues.
- Lack of input validation on non-security-critical fields. If there isn't a proven problem from a lack of input validation, don't report it.

Begin your analysis now. Use the repository exploration tools to understand the codebase context, then analyze the code  for security implications.

Your final reply must contain the JSON and nothing else. You should not reply again after outputting the JSON.
"""