"""
NPvert LaTeX AST Parser
Parses LaTeX templates into hierarchical AST representations.
"""

from pylatexenc.latexwalker import LatexWalker, LatexNode, LatexEnvironmentNode, LatexMacroNode, LatexCharsNode
from typing import List, Dict, Any, Optional
import re


class LaTeXASTNode:
    """Represents a node in the LaTeX AST."""
    def __init__(self, node_type: str, content: str, children: List['LaTeXASTNode'] = None,
                 environment: str = None, macro: str = None, args: List[str] = None,
                 level: int = 0, line_no: int = 0):
        self.node_type = node_type  # 'environment', 'macro', 'text', 'root', 'slot'
        self.content = content
        self.children = children or []
        self.environment = environment
        self.macro = macro
        self.args = args or []
        self.level = level
        self.line_no = line_no
        self.semantic_summary = ""
        self.constraints = {}
        self.is_slot = False
        self.slot_type = None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "content": self.content[:200] if self.content else "",
            "environment": self.environment,
            "macro": self.macro,
            "args": self.args,
            "level": self.level,
            "is_slot": self.is_slot,
            "slot_type": self.slot_type,
            "semantic_summary": self.semantic_summary,
            "constraints": self.constraints,
            "children": [child.to_dict() for child in self.children]
        }
    
    def __repr__(self):
        return f"LaTeXASTNode({self.node_type}, {self.macro or self.environment or self.content[:30]})"


class LaTeXParser:
    """AST-based LaTeX parser for NPvert."""
    
    SECTION_MACROS = ['section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph']
    CONTENT_ENVIRONMENTS = ['figure', 'table', 'equation', 'align', 'itemize', 'enumerate', 'verbatim', 'lstlisting']
    SLOT_PATTERN = re.compile(r'%\s*SLOT:\s*(\w+)', re.IGNORECASE)
    
    def __init__(self):
        self.slot_definitions = {}
        
    def parse(self, latex_source: str) -> LaTeXASTNode:
        """Parse LaTeX source into AST."""
        root = LaTeXASTNode("root", "", level=0)
        
        # Pre-process to identify slots
        lines = latex_source.split('\n')
        processed_lines = []
        for i, line in enumerate(lines):
            match = self.SLOT_PATTERN.search(line)
            if match:
                slot_name = match.group(1).upper()
                self.slot_definitions[slot_name] = {
                    'line': i,
                    'context': self._get_context(lines, i)
                }
            processed_lines.append(line)
        
        latex_source = '\n'.join(processed_lines)
        
        try:
            walker = LatexWalker(latex_source)
            nodes, _ = walker.get_latex_nodes(pos=0)
            for node in nodes:
                child = self._convert_node(node, level=1)
                if child:
                    root.children.append(child)
        except Exception as e:
            # Fallback: parse line by line for simple structures
            root = self._fallback_parse(latex_source)
        
        # Post-process to identify slots in the tree
        self._identify_slots(root)
        
        return root
    
    def _convert_node(self, node: LatexNode, level: int) -> Optional[LaTeXASTNode]:
        """Convert pylatexenc node to our AST node."""
        if node is None:
            return None
            
        if isinstance(node, LatexEnvironmentNode):
            env_name = node.environmentname
            content = node.nodelist.to_latex() if hasattr(node.nodelist, 'to_latex') else str(node.nodelist)
            ast_node = LaTeXASTNode(
                node_type="environment",
                content=content,
                environment=env_name,
                level=level
            )
            # Process children
            if hasattr(node, 'nodelist') and node.nodelist:
                for child in node.nodelist:
                    converted = self._convert_node(child, level + 1)
                    if converted:
                        ast_node.children.append(converted)
            return ast_node
            
        elif isinstance(node, LatexMacroNode):
            macro_name = node.macroname
            args = []
            if hasattr(node, 'nodeargs') and node.nodeargs:
                for arg in node.nodeargs:
                    if arg:
                        args.append(arg.to_latex() if hasattr(arg, 'to_latex') else str(arg))
            
            content = node.to_latex() if hasattr(node, 'to_latex') else f"\\{macro_name}"
            
            ast_node = LaTeXASTNode(
                node_type="macro",
                content=content,
                macro=macro_name,
                args=args,
                level=level
            )
            
            # Check if it's a section
            if macro_name in self.SECTION_MACROS:
                ast_node.constraints['is_section'] = True
                ast_node.constraints['section_level'] = self.SECTION_MACROS.index(macro_name)
                if args:
                    ast_node.semantic_summary = args[0].strip('{}')
            
            return ast_node
            
        elif isinstance(node, LatexCharsNode):
            text = node.chars if hasattr(node, 'chars') else str(node)
            return LaTeXASTNode(
                node_type="text",
                content=text,
                level=level
            )
        else:
            # Generic node handling
            content = node.to_latex() if hasattr(node, 'to_latex') else str(node)
            return LaTeXASTNode(
                node_type="unknown",
                content=content,
                level=level
            )
    
    def _fallback_parse(self, latex_source: str) -> LaTeXASTNode:
        """Simple line-based fallback parser."""
        root = LaTeXASTNode("root", "", level=0)
        lines = latex_source.split('\n')
        current_env = None
        current_section = None
        buffer = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for document class and preamble
            if stripped.startswith('\\documentclass') or stripped.startswith('\\usepackage'):
                root.children.append(LaTeXASTNode("macro", stripped, macro=stripped[1:].split('{')[0].split('[')[0], level=1))
                continue
            
            # Check for environments
            if stripped.startswith('\\begin{'):
                env_name = stripped.split('{')[1].split('}')[0]
                current_env = LaTeXASTNode("environment", "", environment=env_name, level=1)
                root.children.append(current_env)
                continue
            
            if stripped.startswith('\\end{'):
                current_env = None
                continue
            
            # Check for sections
            section_match = re.match(r'\\(section|subsection|subsubsection|paragraph)\*?(\{.*?\})', stripped)
            if section_match:
                sec_type = section_match.group(1)
                title = section_match.group(2).strip('{}')
                section_node = LaTeXASTNode(
                    "macro", stripped, macro=sec_type, args=[title],
                    level=1
                )
                section_node.constraints['is_section'] = True
                section_node.semantic_summary = title
                root.children.append(section_node)
                current_section = section_node
                continue
            
            # Check for slots
            slot_match = self.SLOT_PATTERN.search(stripped)
            if slot_match:
                slot_node = LaTeXASTNode("slot", stripped, level=2)
                slot_node.is_slot = True
                slot_node.slot_type = slot_match.group(1).upper()
                if current_env:
                    current_env.children.append(slot_node)
                else:
                    root.children.append(slot_node)
                continue
            
            # Regular content
            if stripped:
                text_node = LaTeXASTNode("text", line, level=2)
                if current_env:
                    current_env.children.append(text_node)
                elif current_section:
                    current_section.children.append(text_node)
                else:
                    root.children.append(text_node)
        
        return root
    
    def _identify_slots(self, node: LaTeXASTNode):
        """Identify slot markers in the AST."""
        if node.node_type == "text" and node.content:
            match = self.SLOT_PATTERN.search(node.content)
            if match:
                node.is_slot = True
                node.slot_type = match.group(1).upper()
                node.node_type = "slot"
        
        for child in node.children:
            self._identify_slots(child)
    
    def _get_context(self, lines: List[str], line_no: int, context_window: int = 3) -> str:
        """Get surrounding context for a slot."""
        start = max(0, line_no - context_window)
        end = min(len(lines), line_no + context_window + 1)
        return '\n'.join(lines[start:end])
    
    def extract_structure_only(self, node: LaTeXASTNode) -> LaTeXASTNode:
        """Create a structure-only copy with content masked."""
        masked = LaTeXASTNode(
            node_type=node.node_type,
            content="[MASKED]" if node.node_type == "text" and not node.is_slot else node.content,
            environment=node.environment,
            macro=node.macro,
            args=node.args.copy(),
            level=node.level
        )
        masked.is_slot = node.is_slot
        masked.slot_type = node.slot_type
        masked.semantic_summary = node.semantic_summary
        masked.constraints = node.constraints.copy()
        
        for child in node.children:
            masked.children.append(self.extract_structure_only(child))
        
        return masked
    
    def get_slots(self, node: LaTeXASTNode) -> List[LaTeXASTNode]:
        """Get all slot nodes in the AST."""
        slots = []
        if node.is_slot:
            slots.append(node)
        for child in node.children:
            slots.extend(self.get_slots(child))
        return slots
    
    def get_sections(self, node: LaTeXASTNode) -> List[LaTeXASTNode]:
        """Get all section nodes in the AST."""
        sections = []
        if node.constraints.get('is_section'):
            sections.append(node)
        for child in node.children:
            sections.extend(self.get_sections(child))
        return sections
