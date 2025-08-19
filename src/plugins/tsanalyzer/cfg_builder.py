"""Control Flow Graph Builder"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import tree_sitter

from tstool.analyzer.TS_analyzer import TSAnalyzer, find_nodes_by_type, find_all_nodes
from memory.syntactic.function import Function


class BlockType(Enum):
    """Basic block types"""
    ENTRY = "entry"
    EXIT = "exit"
    NORMAL = "normal"
    CONDITIONAL = "conditional"
    LOOP_HEADER = "loop_header"
    LOOP_BODY = "loop_body"
    EXCEPTION = "exception"


@dataclass
class BasicBlock:
    """Basic block in CFG"""
    id: int
    start_line: int
    end_line: int
    block_type: BlockType
    statements: List[tree_sitter.Node]
    predecessors: Set[int] = None
    successors: Set[int] = None
    
    def __post_init__(self):
        if self.predecessors is None:
            self.predecessors = set()
        if self.successors is None:
            self.successors = set()
    
    def __str__(self) -> str:
        return f"Block_{self.id}[{self.start_line}-{self.end_line}]({self.block_type.value})"
    
    def add_predecessor(self, block_id: int):
        """Add predecessor block ID"""
        self.predecessors.add(block_id)
    
    def add_successor(self, block_id: int):
        """Add successor block ID"""
        self.successors.add(block_id)
    
    def remove_predecessor(self, block_id: int):
        """Remove predecessor block ID"""
        self.predecessors.discard(block_id)
    
    def remove_successor(self, block_id: int):
        """Remove successor block ID"""
        self.successors.discard(block_id)
    
    def has_predecessor(self, block_id: int) -> bool:
        """Check if block has specific predecessor"""
        return block_id in self.predecessors
    
    def has_successor(self, block_id: int) -> bool:
        """Check if block has specific successor"""
        return block_id in self.successors
    
    def get_predecessor_count(self) -> int:
        """Get number of predecessors"""
        return len(self.predecessors)
    
    def get_successor_count(self) -> int:
        """Get number of successors"""
        return len(self.successors)
    
    def is_entry_block(self) -> bool:
        """Check if this is an entry block"""
        return self.block_type == BlockType.ENTRY
    
    def is_exit_block(self) -> bool:
        """Check if this is an exit block"""
        return self.block_type == BlockType.EXIT
    
    def is_conditional_block(self) -> bool:
        """Check if this is a conditional block"""
        return self.block_type == BlockType.CONDITIONAL
    
    def is_loop_block(self) -> bool:
        """Check if this is a loop-related block"""
        return self.block_type in [BlockType.LOOP_HEADER, BlockType.LOOP_BODY]
    
    def get_statement_count(self) -> int:
        """Get number of statements in this block"""
        return len(self.statements)
    
    def get_line_count(self) -> int:
        """Get number of lines this block spans"""
        return self.end_line - self.start_line + 1


class ControlFlowGraph:
    """Control Flow Graph representation"""
    
    def __init__(self, function: Function):
        self.function = function
        self.blocks: Dict[int, BasicBlock] = {}
        self.entry_block: Optional[BasicBlock] = None
        self.exit_blocks: Set[int] = set()  # Store block IDs instead of blocks
        self.edges: List[Tuple[int, int]] = []
    
    def add_block(self, block: BasicBlock):
        """Add a basic block to the CFG"""
        self.blocks[block.id] = block
        
        if block.block_type == BlockType.ENTRY:
            self.entry_block = block
        elif block.block_type == BlockType.EXIT:
            self.exit_blocks.add(block.id)  # Store block ID instead of block
    
    def add_edge(self, from_id: int, to_id: int):
        """Add edge between blocks"""
        if from_id in self.blocks and to_id in self.blocks:
            self.blocks[from_id].add_successor(to_id)
            self.blocks[to_id].add_predecessor(from_id)
            self.edges.append((from_id, to_id))
    
    def remove_edge(self, from_id: int, to_id: int):
        """Remove edge between blocks"""
        if from_id in self.blocks and to_id in self.blocks:
            self.blocks[from_id].remove_successor(to_id)
            self.blocks[to_id].remove_predecessor(from_id)
            if (from_id, to_id) in self.edges:
                self.edges.remove((from_id, to_id))
    
    def get_predecessors(self, block_id: int) -> List[BasicBlock]:
        """Get predecessor blocks"""
        if block_id not in self.blocks:
            return []
        return [self.blocks[pid] for pid in self.blocks[block_id].predecessors if pid in self.blocks]
    
    def get_successors(self, block_id: int) -> List[BasicBlock]:
        """Get successor blocks"""
        if block_id not in self.blocks:
            return []
        return [self.blocks[sid] for sid in self.blocks[block_id].successors if sid in self.blocks]
    
    def get_block(self, block_id: int) -> Optional[BasicBlock]:
        """Get BasicBlock by ID"""
        return self.blocks.get(block_id)
    
    def get_exit_blocks(self) -> List[BasicBlock]:
        """Get all exit blocks"""
        return [self.blocks[bid] for bid in self.exit_blocks if bid in self.blocks]
    
    def get_all_blocks(self) -> List[BasicBlock]:
        """Get all blocks as a list"""
        return list(self.blocks.values())
    
    def get_block_ids(self) -> List[int]:
        """Get all block IDs"""
        return list(self.blocks.keys())
    
    def has_block(self, block_id: int) -> bool:
        """Check if block exists"""
        return block_id in self.blocks
    
    def get_block_count(self) -> int:
        """Get total number of blocks"""
        return len(self.blocks)
    
    def get_edge_count(self) -> int:
        """Get total number of edges"""
        return len(self.edges)
    
    def to_dot(self, source_code: str = None) -> str:
        """Generate DOT representation with statement details"""
        colors = {BlockType.ENTRY: "green", BlockType.EXIT: "red", BlockType.CONDITIONAL: "yellow",
                 BlockType.LOOP_HEADER: "blue", BlockType.LOOP_BODY: "lightblue", BlockType.EXCEPTION: "orange"}
        
        nodes = []
        # Use the full source code if provided, otherwise fall back to function code
        code_to_use = source_code if source_code else self.function.function_code
        
        for block in self.blocks.values():
            # Create detailed label with statements
            label_parts = [f"Block_{block.id} [{block.start_line}-{block.end_line}]"]
            label_parts.append(f"({block.block_type.value})")
            label_parts.append("")  # Empty line separator
            
            # Add statements from the block
            if block.statements:
                for stmt in block.statements:  # Show ALL statements
                    if source_code:
                        # Use the full source code with byte offsets
                        stmt_text = source_code[stmt.start_byte:stmt.end_byte].strip()
                    else:
                        # Fall back to extracting from function lines
                        lines = code_to_use.split('\n')
                        stmt_line = source_code[:stmt.start_byte].count('\n') if source_code else 0
                        if stmt_line < len(lines):
                            stmt_text = lines[stmt_line].strip()
                        else:
                            stmt_text = "(statement text unavailable)"
                    
                    # Clean up the statement text for DOT format
                    stmt_text = stmt_text.replace('"', '\\"').replace('\n', '\\n').replace('\t', ' ')
                    # Don't truncate - show full statements
                    if stmt_text:  # Only add non-empty statements
                        label_parts.append(stmt_text)
            else:
                # Show line range content even if no statements detected
                if source_code:
                    lines = source_code.split('\n')
                    if block.start_line <= len(lines) and block.end_line <= len(lines):
                        for line_num in range(block.start_line, min(block.end_line + 1, block.start_line + 3)):
                            if line_num <= len(lines):
                                line_text = lines[line_num - 1].strip()
                                if line_text:
                                    line_text = line_text.replace('"', '\\"').replace('\n', '\\n')
                                    if len(line_text) > 60:
                                        line_text = line_text[:57] + "..."
                                    label_parts.append(line_text)
                
                if not any(label_parts[3:]):  # If no content was added
                    label_parts.append("(empty block)")
            
            # Create the DOT node
            label = "\\n".join(label_parts)
            color = colors.get(block.block_type, "white")
            nodes.append(f'  {block.id} [label="{label}", fillcolor="{color}", style="filled", shape="box"];')
        
        nodes_str = '\n'.join(nodes)
        edges = '\n'.join(f'  {f} -> {t};' for f, t in self.edges)
        
        return f'digraph CFG_{self.function.function_id} {{\n  label="{self.function.function_name}";\n  node [fontname="Courier", fontsize=10];\n{nodes_str}\n{edges}\n}}'


class CFGBuilder:
    """Control Flow Graph Builder"""
    
    def __init__(self, ts_analyzer: TSAnalyzer):
        self.ts_analyzer = ts_analyzer
        self.block_counter = 0
    
    def build_cfg(self, function: Function) -> ControlFlowGraph:
        """Build CFG for a function"""
        cfg = ControlFlowGraph(function)
        
        # Get source code for line number calculations
        source_code = self.ts_analyzer.code_in_files[function.file_path]
        
        # Identify leaders (basic block entry points)
        leaders = self._identify_leaders(function, source_code)
        
        # Create basic blocks
        blocks = self._create_basic_blocks(function, source_code, leaders)
        
        # Add blocks to CFG
        for block in blocks:
            cfg.add_block(block)
        
        # Build edges between blocks
        self._build_edges(cfg, function, source_code)
        
        return cfg
    
    def _identify_leaders(self, function: Function, source_code: str) -> Set[int]:
        """Identify basic block leaders (entry points)"""
        leaders = set()
        root_node = function.parse_tree_root_node
        
        # Function entry is always a leader
        leaders.add(function.start_line_number)
        
        # Find all control flow statements
        control_types = ["if_statement", "while_statement", "for_statement", "try_statement", 
                        "return_statement", "break_statement", "continue_statement"]
        control_statements = []
        for stmt_type in control_types:
            control_statements.extend(find_nodes_by_type(root_node, stmt_type))
        
        for stmt in control_statements:
            stmt_line = source_code[:stmt.start_byte].count('\n') + 1
            leaders.add(stmt_line)
            
            # Add targets of control flow
            if stmt.type == "if_statement":
                # Add line after condition as leader
                leaders.add(stmt_line + 1)
                
                # Add else clause as leader if exists
                else_clause = self._find_else_clause(stmt)
                if else_clause:
                    else_line = source_code[:else_clause.start_byte].count('\n') + 1
                    leaders.add(else_line)
            
            elif stmt.type in ["while_statement", "for_statement"]:
                # Add loop body as leader
                body = self._find_loop_body(stmt)
                if body:
                    body_line = source_code[:body.start_byte].count('\n') + 1
                    leaders.add(body_line)
            
            # Add line after control statement as leader
            stmt_end_line = source_code[:stmt.end_byte].count('\n') + 1
            if stmt_end_line < function.end_line_number:
                leaders.add(stmt_end_line + 1)
        
        return leaders
    
    def _create_basic_blocks(self, function: Function, source_code: str, leaders: Set[int]) -> List[BasicBlock]:
        """Create basic blocks from leaders"""
        blocks = []
        sorted_leaders = sorted(leaders)
        
        for i, leader in enumerate(sorted_leaders):
            # Determine block end
            if i + 1 < len(sorted_leaders):
                end_line = sorted_leaders[i + 1] - 1
            else:
                end_line = function.end_line_number
            
            # Determine block type
            block_type = self._determine_block_type(leader, function, source_code)
            
            # Get statements in this block
            statements = self._get_statements_in_range(function, source_code, leader, end_line)
            
            block = BasicBlock(
                id=self.block_counter,
                start_line=leader,
                end_line=end_line,
                block_type=block_type,
                statements=statements,
                predecessors=set(),
                successors=set()
            )
            
            blocks.append(block)
            self.block_counter += 1
        
        return blocks
    
    def _determine_block_type(self, line: int, function: Function, source_code: str) -> BlockType:
        """Determine the type of a basic block"""
        if line == function.start_line_number:
            return BlockType.ENTRY
        
        # Check if this line contains control flow statements
        root_node = function.parse_tree_root_node
        all_nodes = find_all_nodes(root_node)
        
        for node in all_nodes:
            node_line = source_code[:node.start_byte].count('\n') + 1
            if node_line == line:
                if node.type == "if_statement":
                    return BlockType.CONDITIONAL
                elif node.type in ["while_statement", "for_statement"]:
                    return BlockType.LOOP_HEADER
                elif node.type == "return_statement":
                    return BlockType.EXIT
                elif node.type == "try_statement":
                    return BlockType.EXCEPTION
        
        # Check if this is inside a loop body
        if self._is_in_loop_body(line, function, source_code):
            return BlockType.LOOP_BODY
        
        return BlockType.NORMAL
    
    def _get_statements_in_range(self, function: Function, source_code: str, start_line: int, end_line: int) -> List[tree_sitter.Node]:
        """Get all statements within a line range"""
        statements = []
        root_node = function.parse_tree_root_node
        all_nodes = find_all_nodes(root_node)
        
        for node in all_nodes:
            node_start_line = source_code[:node.start_byte].count('\n') + 1
            node_end_line = source_code[:node.end_byte].count('\n') + 1
            
            # Check if node is a statement within the range
            if (start_line <= node_start_line <= end_line and 
                node.type in self._get_statement_types()):
                statements.append(node)
        
        return statements
    
    def _get_statement_types(self) -> Set[str]:
        """Get AST node types that represent statements"""
        return {
            "expression_statement", "assignment", "call", "return_statement",
            "if_statement", "while_statement", "for_statement", "break_statement",
            "continue_statement", "try_statement", "with_statement", "assert_statement",
            "pass_statement", "delete_statement", "raise_statement", "import_statement",
            "import_from_statement", "global_statement", "nonlocal_statement"
        }
    
    def _build_edges(self, cfg: ControlFlowGraph, function: Function, source_code: str):
        """Build edges between basic blocks"""
        blocks = list(cfg.blocks.values())
        
        for i, block in enumerate(blocks):
            # Default: fall-through to next block
            if i + 1 < len(blocks) and block.block_type not in [BlockType.EXIT]:
                next_block = blocks[i + 1]
                
                # Check if there's no explicit control transfer
                if not self._has_explicit_control_transfer(block, source_code):
                    cfg.add_edge(block.id, next_block.id)
            
            # Handle control flow based on block type
            if block.block_type == BlockType.CONDITIONAL:
                self._handle_conditional_edges(cfg, block, blocks, source_code)
            elif block.block_type == BlockType.LOOP_HEADER:
                self._handle_loop_edges(cfg, block, blocks, source_code)
    
    def _has_explicit_control_transfer(self, block: BasicBlock, source_code: str) -> bool:
        """Check if block ends with control transfer"""
        return any(stmt.type in {"return_statement", "break_statement", "continue_statement", "raise_statement"} 
                  for stmt in block.statements)
    
    def _handle_conditional_edges(self, cfg: ControlFlowGraph, block: BasicBlock, blocks: List[BasicBlock], source_code: str):
        """Handle edges for conditional blocks"""
        # Find the if statement in this block
        for stmt in block.statements:
            if stmt.type == "if_statement":
                # True branch - typically the next block
                true_block = self._find_next_block(block, blocks)
                if true_block:
                    cfg.add_edge(block.id, true_block.id)
                
                # False branch - find else clause or block after if
                else_clause = self._find_else_clause(stmt)
                if else_clause:
                    else_line = source_code[:else_clause.start_byte].count('\n') + 1
                    else_block = self._find_block_by_line(blocks, else_line)
                    if else_block:
                        cfg.add_edge(block.id, else_block.id)
                else:
                    # No else clause, edge to block after if statement
                    after_if_line = source_code[:stmt.end_byte].count('\n') + 2
                    after_block = self._find_block_by_line(blocks, after_if_line)
                    if after_block:
                        cfg.add_edge(block.id, after_block.id)
                break
    
    def _handle_loop_edges(self, cfg: ControlFlowGraph, block: BasicBlock, blocks: List[BasicBlock], source_code: str):
        """Handle edges for loop blocks"""
        # Loop condition to body (true branch)
        loop_body = self._find_next_block(block, blocks)
        if loop_body:
            cfg.add_edge(block.id, loop_body.id)
        
        # Find loop exit (false branch)
        for stmt in block.statements:
            if stmt.type in ["while_statement", "for_statement"]:
                after_loop_line = source_code[:stmt.end_byte].count('\n') + 2
                exit_block = self._find_block_by_line(blocks, after_loop_line)
                if exit_block:
                    cfg.add_edge(block.id, exit_block.id)
                break
        
        # Add back edge from loop body to header
        if loop_body and loop_body.block_type == BlockType.LOOP_BODY:
            cfg.add_edge(loop_body.id, block.id)
    
    def _find_next_block(self, current_block: BasicBlock, blocks: List[BasicBlock]) -> Optional[BasicBlock]:
        """Find next block after current"""
        return next((b for b in blocks if b.start_line > current_block.end_line), None)
    
    def _find_block_by_line(self, blocks: List[BasicBlock], line: int) -> Optional[BasicBlock]:
        """Find block containing line"""
        return next((b for b in blocks if b.start_line <= line <= b.end_line), None)
    
    # Helper methods for AST analysis
    def _find_condition_end(self, if_stmt: tree_sitter.Node, source_code: str) -> Optional[int]:
        """Find the end line of if condition"""
        # This is a simplified implementation
        return source_code[:if_stmt.start_byte].count('\n') + 1
    
    def _find_else_clause(self, if_stmt: tree_sitter.Node) -> Optional[tree_sitter.Node]:
        """Find else clause in if statement"""
        for child in if_stmt.children:
            if child.type == "else_clause":
                return child
        return None
    
    def _find_loop_body(self, loop_stmt: tree_sitter.Node) -> Optional[tree_sitter.Node]:
        """Find loop body"""
        for child in loop_stmt.children:
            if child.type in ["block", "suite"]:
                return child
        return None
    
    def _is_in_loop_body(self, line: int, function: Function, source_code: str) -> bool:
        """Check if line is inside a loop body"""
        root_node = function.parse_tree_root_node
        loop_nodes = find_nodes_by_type(root_node, "while_statement") + find_nodes_by_type(root_node, "for_statement")
        
        for loop in loop_nodes:
            loop_start = source_code[:loop.start_byte].count('\n') + 1
            loop_end = source_code[:loop.end_byte].count('\n') + 1
            if loop_start < line <= loop_end:
                return True
        
        return False
