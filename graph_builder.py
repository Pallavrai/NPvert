"""
NPvert Structure Graph Builder
Constructs a DAG representing document structure from LaTeX AST.
"""

import networkx as nx
from typing import Dict, List, Any, Optional, Tuple
from parser import LaTeXASTNode
import hashlib


class StructureGraphNode:
    """Node in the Structure Graph (DAG)."""
    def __init__(self, node_id: str, node_type: str, ast_node: LaTeXASTNode,
                 parent_id: Optional[str] = None):
        self.node_id = node_id
        self.node_type = node_type  # 'section', 'environment', 'slot', 'text', 'root'
        self.ast_node = ast_node
        self.parent_id = parent_id
        self.children_ids = []
        self.constraints = {}
        self.semantic_anchor = ""
        self.embedding = None
        self.anchoring_score = 0.0
        self.filled_content = None  # Content after LLM placement
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "semantic_anchor": self.semantic_anchor,
            "constraints": self.constraints,
            "is_slot": self.ast_node.is_slot if self.ast_node else False,
            "slot_type": self.ast_node.slot_type if self.ast_node else None,
            "content_preview": self.ast_node.content[:100] if self.ast_node else "",
            "filled_content": self.filled_content[:200] if self.filled_content else None
        }


class StructureGraph:
    """Directed Acyclic Graph representing document structure."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, StructureGraphNode] = {}
        self.root_id = "root"
        self._counter = 0
        
    def _generate_id(self, prefix: str = "node") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}_{hashlib.sha256(str(self._counter).encode()).hexdigest()[:6]}"
    
    def build_from_ast(self, ast_root: LaTeXASTNode) -> 'StructureGraph':
        """Build Structure Graph from LaTeX AST."""
        self.root_id = self._generate_id("root")
        root_node = StructureGraphNode(
            self.root_id, "root", ast_root, None
        )
        root_node.semantic_anchor = "Document Root"
        self.nodes[self.root_id] = root_node
        self.graph.add_node(self.root_id, data=root_node.to_dict())
        
        self._process_ast_children(ast_root, self.root_id)
        self._compute_constraints()
        
        return self
    
    def _process_ast_children(self, ast_node: LaTeXASTNode, parent_id: str):
        """Recursively process AST children and add to graph."""
        for child in ast_node.children:
            node_id = self._generate_id(child.node_type)
            
            # Determine node type
            if child.constraints.get('is_section'):
                node_type = "section"
            elif child.node_type == "environment":
                node_type = "environment"
            elif child.is_slot:
                node_type = "slot"
            elif child.node_type == "text":
                node_type = "text"
            else:
                node_type = child.node_type
            
            sg_node = StructureGraphNode(node_id, node_type, child, parent_id)
            sg_node.semantic_anchor = self._generate_semantic_anchor(child)
            sg_node.constraints = self._extract_constraints(child)
            
            self.nodes[node_id] = sg_node
            self.graph.add_node(node_id, data=sg_node.to_dict())
            self.graph.add_edge(parent_id, node_id)
            
            # Update parent's children list
            if parent_id in self.nodes:
                self.nodes[parent_id].children_ids.append(node_id)
            
            # Recursively process children
            if child.children:
                self._process_ast_children(child, node_id)
    
    def _generate_semantic_anchor(self, ast_node: LaTeXASTNode) -> str:
        """Generate semantic summary for anchoring."""
        if ast_node.semantic_summary:
            return ast_node.semantic_summary
        
        if ast_node.is_slot and ast_node.slot_type:
            return f"Slot for {ast_node.slot_type.lower().replace('_', ' ')}"
        
        if ast_node.environment:
            return f"{ast_node.environment.capitalize()} environment"
        
        if ast_node.macro and ast_node.macro in ['section', 'subsection', 'subsubsection']:
            if ast_node.args:
                return ast_node.args[0].strip('{}')
        
        content = ast_node.content.strip()
        if content:
            return content[:100]
        
        return f"{ast_node.node_type} node"
    
    def _extract_constraints(self, ast_node: LaTeXASTNode) -> Dict[str, Any]:
        """Extract structural constraints from AST node."""
        constraints = ast_node.constraints.copy()
        
        if ast_node.environment:
            constraints['environment_type'] = ast_node.environment
            constraints['allowed_content'] = self._get_allowed_content(ast_node.environment)
        
        if ast_node.is_slot:
            constraints['requires_content'] = True
            constraints['slot_type'] = ast_node.slot_type
        
        if ast_node.node_type == "text" and not ast_node.is_slot:
            constraints['is_static'] = True
        
        return constraints
    
    def _get_allowed_content(self, env_name: str) -> List[str]:
        """Determine allowed content types for an environment."""
        allowed = {
            'figure': ['image', 'caption', 'label'],
            'table': ['tabular', 'caption', 'label'],
            'equation': ['math'],
            'align': ['math'],
            'itemize': ['item'],
            'enumerate': ['item'],
            'verbatim': ['text'],
            'lstlisting': ['code']
        }
        return allowed.get(env_name, ['text'])
    
    def _compute_constraints(self):
        """Compute hierarchical and cross-cutting constraints."""
        # Propagate section-level constraints
        for node_id, node in self.nodes.items():
            if node.node_type == "section":
                # Sections can contain subsections, text, environments
                node.constraints['can_contain'] = ['subsection', 'environment', 'text', 'slot']
                node.constraints['level'] = node.ast_node.constraints.get('section_level', 0)
    
    def get_slots(self) -> List[StructureGraphNode]:
        """Get all slot nodes."""
        return [n for n in self.nodes.values() if n.node_type == "slot"]
    
    def get_sections(self) -> List[StructureGraphNode]:
        """Get all section nodes."""
        return [n for n in self.nodes.values() if n.node_type == "section"]
    
    def get_slot_by_type(self, slot_type: str) -> Optional[StructureGraphNode]:
        """Find slot by type."""
        for node in self.nodes.values():
            if node.node_type == "slot" and node.ast_node.slot_type == slot_type:
                return node
        return None
    
    def validate_placement(self, node_id: str, content_type: str) -> Tuple[bool, str]:
        """Validate if content type can be placed at node."""
        if node_id not in self.nodes:
            return False, "Node not found"
        
        node = self.nodes[node_id]
        constraints = node.constraints
        
        if not node.ast_node.is_slot:
            return False, "Node is not a slot"
        
        # Check environment constraints
        parent_id = node.parent_id
        if parent_id and parent_id in self.nodes:
            parent = self.nodes[parent_id]
            if 'allowed_content' in parent.constraints:
                if content_type not in parent.constraints['allowed_content']:
                    return False, f"Content type '{content_type}' not allowed in {parent.ast_node.environment}"
        
        return True, "Valid placement"
    
    def to_networkx(self) -> nx.DiGraph:
        """Return the NetworkX graph for visualization."""
        return self.graph
    
    def get_node_hierarchy(self) -> Dict[str, Any]:
        """Get hierarchical representation."""
        def build_tree(node_id: str) -> Dict[str, Any]:
            node = self.nodes[node_id]
            return {
                **node.to_dict(),
                "children": [build_tree(cid) for cid in node.children_ids]
            }
        
        return build_tree(self.root_id)
    
    def fill_slot(self, node_id: str, content: str) -> bool:
        """Fill a slot with content."""
        if node_id not in self.nodes:
            return False
        
        node = self.nodes[node_id]
        if not node.ast_node.is_slot:
            return False
        
        node.filled_content = content
        node.ast_node.content = content
        return True
    
    def get_filled_latex(self, ast_node: LaTeXASTNode = None, node_id: str = None) -> str:
        """Reconstruct LaTeX from AST with filled content."""
        if ast_node is None:
            # Find root AST node
            root = self.nodes.get(self.root_id)
            if root and root.ast_node:
                return self.get_filled_latex(root.ast_node, self.root_id)
            return ""
        
        if ast_node.is_slot and node_id:
            sg_node = self.nodes.get(node_id)
            if sg_node and sg_node.filled_content:
                return sg_node.filled_content + '\n'
        
        # Reconstruct from AST
        if ast_node.node_type == "environment":
            result = f"\\begin{{{ast_node.environment}}}\n"
            for child in ast_node.children:
                child_id = None
                # Find corresponding SG node
                for nid, n in self.nodes.items():
                    if n.ast_node == child:
                        child_id = nid
                        break
                result += self.get_filled_latex(child, child_id)
            result += f"\\end{{{ast_node.environment}}}\n"
            return result
        
        elif ast_node.node_type == "macro":
            if ast_node.args:
                args_str = ''.join([f"{{{arg.strip('{}')}}}" for arg in ast_node.args])
                return f"\\{ast_node.macro}{args_str}\n"
            return f"\\{ast_node.macro}\n"
        
        elif ast_node.node_type == "text":
            return ast_node.content + '\n'
        
        elif ast_node.node_type == "root":
            result = ""
            for child in ast_node.children:
                child_id = None
                for nid, n in self.nodes.items():
                    if n.ast_node == child:
                        child_id = nid
                        break
                result += self.get_filled_latex(child, child_id)
            return result
        
        return ast_node.content + '\n'
