"""
NPvert LLM Semantic Placer
Uses Gemini Pro for semantic anchoring and content placement.
"""

from google import genai
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from graph_builder import StructureGraph, StructureGraphNode


class SemanticPlacer:
    """LLM-based semantic content placer for NPvert."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"
        
    def analyze_content(self, input_text: str) -> Dict[str, Any]:
        """Analyze input content and extract semantic blocks."""
        prompt = f"""
Analyze the following document content and break it down into semantic blocks.
For each block, identify:
1. Content type (abstract, introduction, methodology, results, discussion, conclusion, references, table_data, figure_caption, etc.)
2. A brief summary (2-3 sentences)
3. Key entities, numbers, and findings

Content:
{input_text[:8000]}

Return ONLY a JSON object with this structure:
{{
  "blocks": [
    {{
      "type": "content_type",
      "summary": "brief summary",
      "key_content": "key information",
      "original_text": "relevant excerpt"
    }}
  ]
}}
"""
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            text = response.text
            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            return json.loads(text)
        except Exception as e:
            # Fallback: simple heuristic segmentation
            return self._fallback_segmentation(input_text)
    
    def _fallback_segmentation(self, text: str) -> Dict[str, Any]:
        """Simple fallback segmentation."""
        blocks = []
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        for para in paragraphs:
            block_type = "text"
            if any(word in para.lower() for word in ['abstract', 'summary']):
                block_type = "abstract"
            elif any(word in para.lower() for word in ['introduction', 'background']):
                block_type = "introduction"
            elif any(word in para.lower() for word in ['method', 'approach', 'algorithm']):
                block_type = "methodology"
            elif any(word in para.lower() for word in ['result', 'finding', 'accuracy', 'performance']):
                block_type = "results"
            elif any(word in para.lower() for word in ['conclusion', 'future work']):
                block_type = "conclusion"
            elif any(word in para.lower() for word in ['table', 'figure']):
                block_type = "table_data" if '%' in para or '|' in para else "figure_caption"
            
            blocks.append({
                "type": block_type,
                "summary": para[:200],
                "key_content": para,
                "original_text": para
            })
        
        return {"blocks": blocks}
    
    def compute_anchoring_scores(self, content_blocks: List[Dict], 
                                  graph: StructureGraph) -> Dict[str, List[Tuple[str, float]]]:
        """Compute semantic compatibility scores between content and graph slots."""
        slots = graph.get_slots()
        if not slots:
            return {}
        
        scores = {}
        for block in content_blocks:
            block_scores = []
            for slot in slots:
                score = self._compute_similarity(block, slot)
                block_scores.append((slot.node_id, score))
            
            # Sort by score descending
            block_scores.sort(key=lambda x: x[1], reverse=True)
            scores[block['type']] = block_scores
        
        return scores
    
    def _compute_similarity(self, block: Dict, slot: StructureGraphNode) -> float:
        """Compute semantic similarity between content block and slot."""
        block_type = block['type'].lower()
        slot_type = (slot.ast_node.slot_type or '').lower() if slot.ast_node else ''
        slot_anchor = slot.semantic_anchor.lower()
        
        score = 0.0
        
        # Type matching
        if block_type in slot_type or slot_type in block_type:
            score += 0.5
        
        # Keyword matching in semantic anchor
        block_keywords = set(block['summary'].lower().split())
        anchor_keywords = set(slot_anchor.split())
        if block_keywords and anchor_keywords:
            overlap = len(block_keywords & anchor_keywords)
            score += 0.3 * (overlap / max(len(block_keywords), len(anchor_keywords)))
        
        # Contextual hints
        if 'result' in block_type and ('result' in slot_type or 'result' in slot_anchor):
            score += 0.2
        if 'abstract' in block_type and ('abstract' in slot_type or 'abstract' in slot_anchor):
            score += 0.2
        if 'method' in block_type and ('method' in slot_type or 'method' in slot_anchor):
            score += 0.2
        if 'conclusion' in block_type and ('conclusion' in slot_type or 'conclusion' in slot_anchor):
            score += 0.2
        
        return min(score, 1.0)
    
    def generate_latex_content(self, block: Dict, slot: StructureGraphNode,
                                context: str = "") -> str:
        """Generate LaTeX-compatible content for a slot."""
        slot_type = slot.ast_node.slot_type if slot.ast_node else "TEXT"
        
        prompt = f"""
You are a LaTeX document synthesis engine. Given the following content block and a template slot,
generate appropriate LaTeX content that fits the slot type while preserving the original meaning.

Slot Type: {slot_type}
Slot Context: {slot.semantic_anchor}
Document Context: {context[:500]}

Content Block:
Type: {block['type']}
Summary: {block['summary']}
Original Text: {block['original_text'][:2000]}

Generate ONLY the LaTeX content for this slot. Do not include \\begin or \\end for the parent environment.
Ensure the output is valid LaTeX syntax.
"""
        
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            latex_content = response.text.strip()
            
            # Clean up markdown code blocks
            latex_content = re.sub(r'```latex\s*', '', latex_content)
            latex_content = re.sub(r'```\s*', '', latex_content)
            
            return latex_content
        except Exception as e:
            # Fallback: return original text as LaTeX
            return self._text_to_latex(block['original_text'])
    
    def _text_to_latex(self, text: str) -> str:
        """Convert plain text to basic LaTeX."""
        # Escape special characters
        text = text.replace('&', '\\&')
        text = text.replace('%', '\\%')
        text = text.replace('$', '\\$')
        text = text.replace('#', '\\#')
        text = text.replace('_', '\\_')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')
        text = text.replace('~', '\\textasciitilde ')
        text = text.replace('^', '\\textasciicircum ')
        
        # Wrap paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return '\n\n'.join([f"{p}" for p in paragraphs])
    
    def place_content(self, input_text: str, graph: StructureGraph) -> StructureGraph:
        """Main placement pipeline."""
        # Step 1: Analyze content
        analysis = self.analyze_content(input_text)
        blocks = analysis.get('blocks', [])
        
        if not blocks:
            return graph
        
        # Step 2: Compute anchoring scores
        scores = self.compute_anchoring_scores(blocks, graph)
        
        # Step 3: Assign blocks to slots (greedy assignment)
        assigned_slots = set()
        slot_assignments = {}  # slot_id -> block
        
        for block in blocks:
            block_type = block['type']
            if block_type in scores:
                for slot_id, score in scores[block_type]:
                    if slot_id not in assigned_slots and score > 0.2:
                        # Validate placement
                        valid, msg = graph.validate_placement(slot_id, block['type'])
                        if valid:
                            assigned_slots.add(slot_id)
                            slot_assignments[slot_id] = block
                            break
        
        # Step 4: Generate LaTeX content for each assignment
        sections = graph.get_sections()
        section_context = ""
        for sec in sections:
            section_context += f"- {sec.semantic_anchor}\n"
        
        for slot_id, block in slot_assignments.items():
            slot = graph.nodes[slot_id]
            latex_content = self.generate_latex_content(block, slot, section_context)
            graph.fill_slot(slot_id, latex_content)
        
        return graph
    
    def _escape_latex_content(self, text: str) -> str:
        """Escape special LaTeX characters in generated content."""
        # Don't escape if it looks like already-formatted LaTeX
        if '\\' in text and any(cmd in text for cmd in ['\\textbf', '\\textit', '\\section', '\\begin', '\\item', '\\cite']):
            return text
        
        # Escape special characters
        replacements = [
            ('\\', '\\textbackslash '),
            ('&', '\\&'),
            ('%', '\\%'),
            ('$', '\\$'),
            ('#', '\\#'),
            ('_', '\\_'),
            ('{', '\\{'),
            ('}', '\\}'),
            ('~', '\\textasciitilde '),
            ('^', '\\textasciicircum '),
        ]
        
        for old, new in replacements:
            text = text.replace(old, new)
        
        return text
    
    def generate_complete_document(self, template_latex: str, graph: StructureGraph) -> tuple:
        """Generate complete LaTeX document by replacing slots.
        
        Returns:
            tuple: (generated_latex, unfilled_slots_list)
        """
        result = template_latex
        unfilled_slots = []
        
        # First pass: replace filled slots and identify unfilled ones
        for node_id, node in graph.nodes.items():
            if node.ast_node and node.ast_node.is_slot:
                slot_type = node.ast_node.slot_type
                
                if node.filled_content:
                    content = node.filled_content.strip()
                    safe_content = self._escape_latex_content(content)
                    slot_pattern = r'^\s*%\s*SLOT:\s*' + re.escape(slot_type) + r'\s*$'
                    result = re.sub(slot_pattern, safe_content, result, flags=re.IGNORECASE | re.MULTILINE)
                else:
                    unfilled_slots.append(slot_type)
                    # Mark unfilled slot for removal
                    slot_pattern = r'^\s*%\s*SLOT:\s*' + re.escape(slot_type) + r'\s*$'
                    result = re.sub(slot_pattern, '% SLOT_REMOVED: ' + slot_type, result, flags=re.IGNORECASE | re.MULTILINE)
        
        
        result = self._remove_empty_sections(result)
        
        # Clean up any remaining slot markers
        result = re.sub(r'^\s*%\s*SLOT(_REMOVED)?:\s*\w+\s*\n?', '', result, flags=re.IGNORECASE | re.MULTILINE)
        
        # Clean up multiple consecutive blank lines
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result, unfilled_slots
    
    def _remove_empty_sections(self, latex: str) -> str:
        """Remove sections/environments that only contain removed slots or are empty."""
        lines = latex.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this is a section start
            section_match = re.match(r'^(\\(section|subsection|subsubsection|chapter|paragraph)\*?\{[^}]*\})', line)
            if section_match:
                section_start = i
                section_header = line
                section_content = []
                i += 1
                
                # Collect section content until next section or end of document
                while i < len(lines):
                    next_line = lines[i]
                    if re.match(r'^\\(section|subsection|subsubsection|chapter|paragraph|end\{document\}|bibliographystyle|appendix)', next_line):
                        break
                    section_content.append(next_line)
                    i += 1
                
                # Check if section has meaningful content (not just removed slots/empty)
                meaningful = False
                for content_line in section_content:
                    stripped = content_line.strip()
                    if stripped and not stripped.startswith('% SLOT_REMOVED:'):
                        meaningful = True
                        break
                
                if meaningful:
                    result_lines.append(section_header)
                    result_lines.extend(section_content)
                # else: skip this empty section entirely
                continue
            
            # Check for empty environments
            env_match = re.match(r'^\\begin\{(\w+)\}', line)
            if env_match:
                env_name = env_match.group(1)
                env_start = i
                env_content = [line]
                i += 1
                depth = 1
                
                while i < len(lines) and depth > 0:
                    current = lines[i]
                    if re.match(r'^\\begin\{' + re.escape(env_name) + r'\}', current):
                        depth += 1
                    elif re.match(r'^\\end\{' + re.escape(env_name) + r'\}', current):
                        depth -= 1
                    env_content.append(current)
                    i += 1
                
                # Check if environment has meaningful content
                meaningful = False
                for content_line in env_content[1:-1]:  # Exclude begin/end
                    stripped = content_line.strip()
                    if stripped and not stripped.startswith('% SLOT_REMOVED:'):
                        meaningful = True
                        break
                
                if meaningful:
                    result_lines.extend(env_content)
                # else: skip empty environment
                continue
            
            # Keep preamble and other lines
            result_lines.append(line)
            i += 1
        
        return '\n'.join(result_lines)
