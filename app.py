"""
NPvert Streamlit Application
Structure-First RAG for LaTeX Document Synthesis
"""

import streamlit as st
import os
import tempfile
import subprocess
import json
import hashlib
from pathlib import Path

from parser import LaTeXParser, LaTeXASTNode
from graph_builder import StructureGraph, StructureGraphNode
from llm_placer import SemanticPlacer
from docx_converter import DOCXConverter, is_docx, read_input_file
from dotenv import load_dotenv

# Page configuration
st.set_page_config(
    page_title="NPvert - Structure-First RAG",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize session state
if 'graph' not in st.session_state:
    st.session_state.graph = None
if 'ast' not in st.session_state:
    st.session_state.ast = None
if 'template_latex' not in st.session_state:
    st.session_state.template_latex = ""
if 'input_content' not in st.session_state:
    st.session_state.input_content = ""
if 'output_latex' not in st.session_state:
    st.session_state.output_latex = ""
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None

# Widget state keys for text areas (required for programmatic updates in Streamlit >= 1.30)
if 'template_editor' not in st.session_state:
    st.session_state.template_editor = st.session_state.template_latex
if 'input_editor' not in st.session_state:
    st.session_state.input_editor = st.session_state.input_content


def init_placer():
    """Initialize the semantic placer."""
    return SemanticPlacer(GEMINI_API_KEY)


@st.cache_data
def parse_template(latex_content: str):
    """Parse LaTeX template into AST and Structure Graph."""
    parser = LaTeXParser()
    ast = parser.parse(latex_content)
    
    graph = StructureGraph()
    graph.build_from_ast(ast)
    
    return ast, graph


def find_latex_compiler() -> tuple:
    """Find available LaTeX compiler and return (command, name)."""
    compilers = [
        (['pdflatex', '-interaction=nonstopmode', '-output-directory'], "pdfLaTeX"),
        (['xelatex', '-interaction=nonstopmode', '-output-directory'], "XeLaTeX"),
        (['lualatex', '-interaction=nonstopmode', '-output-directory'], "LuaLaTeX"),
        (['tectonic', '--outdir'], "Tectonic"),
    ]
    
    for cmd, name in compilers:
        try:
            result = subprocess.run([cmd[0], '--version'], capture_output=True, timeout=5)
            if result.returncode == 0 or result.returncode == 1:  # Some compilers return 1 for --version
                return cmd, name
        except FileNotFoundError:
            continue
        except Exception:
            continue
    
    return None, None


def compile_latex(latex_content: str, output_dir: str) -> str:
    """Compile LaTeX to PDF using available compiler."""
    tex_path = os.path.join(output_dir, "output.tex")
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    
    compiler_cmd, compiler_name = find_latex_compiler()
    
    if compiler_cmd is None:
        st.error("""
        **No LaTeX compiler found!**
        
        Please install one of the following:
        
        **Option 1: Tectonic (Recommended - smallest, fastest)**
        ```bash
        brew install tectonic
        ```
        
        **Option 2: MacTeX (Full distribution)**
        ```bash
        brew install --cask mactex
        ```
        
        **Option 3: BasicTeX (Minimal)**
        ```bash
        brew install --cask basictex
        ```
        
        After installation, restart this application.
        """)
        return None
    
    try:
        # Build command
        if compiler_cmd[0] == 'tectonic':
            cmd = compiler_cmd + [output_dir, tex_path]
        else:
            cmd = compiler_cmd + [output_dir, tex_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        pdf_path = os.path.join(output_dir, "output.pdf")
        if os.path.exists(pdf_path):
            st.success(f"PDF compiled successfully using {compiler_name}!")
            return pdf_path
        else:
            st.warning(f"PDF compilation warning from {compiler_name}: " + result.stderr[:800])
            return None
    except subprocess.TimeoutExpired:
        st.error("LaTeX compilation timed out.")
        return None
    except Exception as e:
        st.error(f"Compilation error: {str(e)}")
        return None


def render_graph_visualization(graph: StructureGraph):
    """Render the structure graph as a proper hierarchical tree."""
    import plotly.graph_objects as go
    import networkx as nx
    
    G = graph.to_networkx()
    
    # Hierarchical tree layout using BFS levels
    def compute_tree_layout(graph_obj, root_id):
        """Compute top-down hierarchical positions."""
        pos = {}
        levels = {}
        
        # BFS to assign levels
        from collections import deque
        queue = deque([(root_id, 0)])
        visited = {root_id}
        
        while queue:
            node_id, level = queue.popleft()
            if level not in levels:
                levels[level] = []
            levels[level].append(node_id)
            
            if node_id in graph_obj.nodes:
                sg_node = graph_obj.nodes[node_id]
                for child_id in sg_node.children_ids:
                    if child_id not in visited:
                        visited.add(child_id)
                        queue.append((child_id, level + 1))
        
        # Position nodes: x spread by level width, y by level (top to bottom)
        max_level = max(levels.keys()) if levels else 0
        level_height = 1.0 / (max_level + 1) if max_level > 0 else 1.0
        
        for level, node_ids in levels.items():
            n_nodes = len(node_ids)
            for i, node_id in enumerate(node_ids):
                # x: spread evenly across width
                x = (i + 0.5) / n_nodes if n_nodes > 1 else 0.5
                # y: top (1.0) to bottom (0.0)
                y = 1.0 - (level * level_height) - (level_height * 0.5)
                pos[node_id] = (x, y)
        
        return pos
    
    pos = compute_tree_layout(graph, graph.root_id)
    
    # Create curved edges (Bezier-style paths)
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        # Create a curved line with a midpoint
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        
        # Add multiple points for smoother curve
        t_vals = [0, 0.25, 0.5, 0.75, 1.0]
        for t in t_vals:
            # Quadratic Bezier: (1-t)^2 * P0 + 2(1-t)t * Pmid + t^2 * P1
            # Using linear with slight curve
            px = (1-t)*x0 + t*x1
            py = (1-t)*y0 + t*y1
            edge_x.append(px)
            edge_y.append(py)
        edge_x.append(None)
        edge_y.append(None)
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#555555'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Create nodes
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    node_labels = []
    node_hover = []
    
    color_map = {
        'root': '#E74C3C',
        'section': '#27AE60',
        'environment': '#2980B9',
        'slot': '#E67E22',
        'text': '#8E44AD',
        'macro': '#16A085'
    }
    
    text_color_map = {
        'root': '#FFFFFF',
        'section': '#FFFFFF',
        'environment': '#FFFFFF',
        'slot': '#FFFFFF',
        'text': '#FFFFFF',
        'macro': '#FFFFFF'
    }
    
    for node_id in G.nodes():
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        
        node_data = graph.nodes.get(node_id)
        if node_data:
            node_type = node_data.node_type
            node_colors.append(color_map.get(node_type, '#95A5A6'))
            node_sizes.append(25 if node_type == 'slot' else 18)
            
            # Short label
            if node_data.ast_node and node_data.ast_node.is_slot and node_data.ast_node.slot_type:
                label = node_data.ast_node.slot_type[:12]
            elif node_data.semantic_anchor:
                label = node_data.semantic_anchor[:12]
            else:
                label = node_type[:12]
            node_labels.append(label)
            
            # Detailed hover text
            info = f"<b>Type:</b> {node_type}<br>"
            info += f"<b>Anchor:</b> {node_data.semantic_anchor[:60]}<br>"
            if node_data.ast_node and node_data.ast_node.is_slot:
                info += f"<b>Slot:</b> {node_data.ast_node.slot_type}<br>"
                info += f"<b>Status:</b> {'✅ Filled' if node_data.filled_content else '⬜ Empty'}"
            node_hover.append(info)
        else:
            node_colors.append('#95A5A6')
            node_sizes.append(18)
            node_labels.append(node_id[:10])
            node_hover.append(node_id)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_labels,
        textposition='bottom center',
        hovertext=node_hover,
        textfont=dict(
            size=10,
            color='#2C3E50',
            family='Arial, sans-serif'
        ),
        marker=dict(
            color=node_colors,
            size=node_sizes,
            line=dict(width=2, color='#2C3E50'),
            opacity=0.9
        )
    )
    
    # Add annotations for parent-child connections
    annotations = []
    for edge in G.edges():
        if edge[0] in pos and edge[1] in pos:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            annotations.append(dict(
                x=x1, y=y1,
                xref='x', yref='y',
                ax=x0, ay=y0,
                axref='x', ayref='y',
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor='#7F8C8D'
            ))
    
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title=dict(
                            text='NPvert Structure Graph (Hierarchical AST)',
                            font=dict(size=18, color='#2C3E50')
                        ),
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=40, l=20, r=20, t=60),
                        xaxis=dict(
                            showgrid=False, 
                            zeroline=False, 
                            showticklabels=False,
                            range=[-0.1, 1.1]
                        ),
                        yaxis=dict(
                            showgrid=False, 
                            zeroline=False, 
                            showticklabels=False,
                            range=[-0.1, 1.1]
                        ),
                        plot_bgcolor='#FFFFFF',
                        paper_bgcolor='#FFFFFF',
                        annotations=annotations,
                        dragmode='pan'
                    ))
    
    return fig


def load_template(template_name: str) -> str:
    """Load a preformatted template."""
    template_dir = Path(__file__).parent / "templates"
    template_path = template_dir / f"{template_name}.tex"
    
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def load_sample(sample_name: str) -> str:
    """Load a sample raw file."""
    sample_dir = Path(__file__).parent / "samples"
    sample_path = sample_dir / f"{sample_name}.txt"
    
    if sample_path.exists():
        with open(sample_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


# Sidebar
with st.sidebar:
    st.title("📄 NPvert")
    st.markdown("*Structure-First RAG for LaTeX Document Synthesis*")
    st.markdown("---")
    
    st.subheader("Preformatted Templates")
    template_option = st.selectbox(
        "Choose a template:",
        ["None", "Research Paper", "Technical Report", "Resume", "Letter"]
    )
    
    if template_option != "None":
        template_map = {
            "Research Paper": "research_paper",
            "Technical Report": "technical_report",
            "Resume": "resume",
            "Letter": "letter"
        }
        if st.button("Load Template"):
            st.session_state.template_editor = load_template(template_map[template_option])
            st.success(f"Loaded {template_option} template!")
            st.rerun()
    
    st.markdown("---")
    
    st.subheader("Sample Raw Files")
    sample_option = st.selectbox(
        "Choose a sample:",
        ["None", "Research Content", "Project Report", "Personal Profile"]
    )
    
    if sample_option != "None":
        sample_map = {
            "Research Content": "research_content",
            "Project Report": "project_report",
            "Personal Profile": "personal_profile"
        }
        if st.button("Load Sample"):
            st.session_state.input_editor = load_sample(sample_map[sample_option])
            st.success(f"Loaded {sample_option} sample!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### About")
    st.markdown("NPvert guarantees compilable LaTeX by separating semantic reasoning from syntactic realization.")


# Main content
st.title("NPvert: Structure-First RAG for LaTeX Document Synthesis")
st.markdown("*Guaranteed compiler-level correctness for automated document generation*")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["📝 Input", "🔍 Structure Graph", "⚙️ Processing", "📤 Output"])

# Tab 1: Input
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Target Format (LaTeX Template)")
        st.markdown("Upload a LaTeX template or paste below. Use `% SLOT: SLOT_NAME` markers for fillable regions.")
        
        template_file = st.file_uploader("Upload Template (.tex or .docx)", type=['tex', 'docx'], key="template_upload")
        
        if template_file is not None:
            file_bytes = template_file.getvalue()
            file_id = hashlib.md5(file_bytes).hexdigest()
            if st.session_state.get("_template_file_id") != file_id:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.' + template_file.name.split('.')[-1]) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                
                if is_docx(tmp_path):
                    converter = DOCXConverter()
                    st.session_state.template_editor = converter.convert(tmp_path)
                else:
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        st.session_state.template_editor = f.read()
                
                os.unlink(tmp_path)
                st.session_state._template_file_id = file_id
                st.rerun()
        
        st.text_area(
            "Template LaTeX:",
            height=400,
            key="template_editor"
        )
        st.session_state.template_latex = st.session_state.template_editor
    
    with col2:
        st.subheader("Input Content")
        st.markdown("Upload a document or paste content to be formatted.")
        
        input_file = st.file_uploader("Upload Input (.txt, .tex, .docx)", type=['txt', 'tex', 'docx'], key="input_upload")
        
        if input_file is not None:
            file_bytes = input_file.getvalue()
            file_id = hashlib.md5(file_bytes).hexdigest()
            if st.session_state.get("_input_file_id") != file_id:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.' + input_file.name.split('.')[-1]) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                
                st.session_state.input_editor = read_input_file(tmp_path)
                os.unlink(tmp_path)
                st.session_state._input_file_id = file_id
                st.rerun()
        
        st.text_area(
            "Input Content:",
            height=400,
            key="input_editor"
        )
        st.session_state.input_content = st.session_state.input_editor

# Tab 2: Structure Graph
with tab2:
    st.subheader("Structure Graph Visualization")
    
    if st.session_state.template_latex:
        if st.button("🔄 Parse Template & Build Graph", key="parse_btn"):
            with st.spinner("Parsing LaTeX and building Structure Graph..."):
                try:
                    ast, graph = parse_template(st.session_state.template_latex)
                    st.session_state.ast = ast
                    st.session_state.graph = graph
                    st.success("Graph built successfully!")
                except Exception as e:
                    st.error(f"Error parsing template: {str(e)}")
        
        if st.session_state.graph:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = render_graph_visualization(st.session_state.graph)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### Graph Statistics")
                graph = st.session_state.graph
                st.metric("Total Nodes", len(graph.nodes))
                st.metric("Slots", len(graph.get_slots()))
                st.metric("Sections", len(graph.get_sections()))
                
                st.markdown("### Slots")
                for slot in graph.get_slots():
                    status = "✅ Filled" if slot.filled_content else "⬜ Empty"
                    st.markdown(f"- **{slot.ast_node.slot_type}** ({status})")
                
                st.markdown("### Hierarchy")
                hierarchy = graph.get_node_hierarchy()
                st.json(hierarchy, expanded=False)
        else:
            st.info("Click 'Parse Template & Build Graph' to visualize the structure.")
    else:
        st.info("Please provide a LaTeX template in the Input tab first.")

# Tab 3: Processing
with tab3:
    st.subheader("Semantic Anchoring & Content Placement")
    
    if st.session_state.graph and st.session_state.input_content:
        if st.button("🚀 Run NPvert Pipeline", key="run_btn"):
            with st.spinner("Running Structure-First RAG pipeline..."):
                try:
                    placer = init_placer()
                    
                    # Step 1: Analyze content
                    st.markdown("**Step 1:** Analyzing content semantic blocks...")
                    analysis = placer.analyze_content(st.session_state.input_content)
                    blocks = analysis.get('blocks', [])
                    st.success(f"Found {len(blocks)} semantic blocks")
                    
                    with st.expander("View Semantic Blocks"):
                        for i, block in enumerate(blocks):
                            st.markdown(f"**Block {i+1}:** `{block['type']}`")
                            st.markdown(f"Summary: {block['summary']}")
                            st.markdown("---")
                    
                    # Step 2: Compute scores
                    st.markdown("**Step 2:** Computing anchoring scores...")
                    scores = placer.compute_anchoring_scores(blocks, st.session_state.graph)
                    st.success("Anchoring scores computed")
                    
                    with st.expander("View Anchoring Scores"):
                        for block_type, block_scores in scores.items():
                            st.markdown(f"**{block_type}:**")
                            for slot_id, score in block_scores[:3]:
                                slot = st.session_state.graph.nodes.get(slot_id)
                                if slot:
                                    st.markdown(f"  - {slot.semantic_anchor}: {score:.3f}")
                    
                    # Step 3: Place content
                    st.markdown("**Step 3:** Placing content into slots...")
                    updated_graph = placer.place_content(st.session_state.input_content, st.session_state.graph)
                    st.session_state.graph = updated_graph
                    st.success("Content placed successfully!")
                    
                    # Step 4: Generate output
                    st.markdown("**Step 4:** Generating LaTeX document...")
                    output, unfilled = placer.generate_complete_document(
                        st.session_state.template_latex,
                        st.session_state.graph
                    )
                    st.session_state.output_latex = output
                    st.session_state.unfilled_slots = unfilled
                    st.success("LaTeX document generated!")
                    
                    if unfilled:
                        st.warning(f"⚠️ **{len(unfilled)} slot(s) not filled:** {', '.join(unfilled)}. Empty sections were removed from output.")
                    
                except Exception as e:
                    st.error(f"Error in pipeline: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        if st.session_state.output_latex:
            st.markdown("### Processing Complete!")
            st.balloons()
    else:
        st.info("Please provide both a template and input content in the Input tab.")

# Tab 4: Output
with tab4:
    st.subheader("Generated Document")
    
    if st.session_state.output_latex:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### LaTeX Output")
            st.code(st.session_state.output_latex, language='latex')
            
            # Download buttons
            st.download_button(
                label="📥 Download .tex",
                data=st.session_state.output_latex,
                file_name="npvert_output.tex",
                mime="text/x-tex"
            )
        
        with col2:
            st.markdown("### Compile to PDF")
            
            if st.button("🔨 Compile PDF", key="compile_btn"):
                with st.spinner("Compiling LaTeX to PDF..."):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        pdf_path = compile_latex(st.session_state.output_latex, tmpdir)
                        if pdf_path:
                            st.session_state.pdf_path = pdf_path
                            with open(pdf_path, 'rb') as f:
                                pdf_bytes = f.read()
                            st.download_button(
                                label="📥 Download PDF",
                                data=pdf_bytes,
                                file_name="npvert_output.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.info("Compilation failed. You can still download the .tex file and compile it manually, or fix the issues above.")
                            with st.expander("View Generated LaTeX for Debugging"):
                                st.code(st.session_state.output_latex, language='latex')
            
            if st.session_state.pdf_path and os.path.exists(st.session_state.pdf_path):
                st.markdown("### PDF Preview")
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(st.session_state.pdf_path, first_page=1, last_page=1)
                    if images:
                        st.image(images[0], caption="Page 1", use_container_width=True)
                except Exception as e:
                    st.info("PDF preview not available. Please download the PDF.")
            
            st.markdown("### Validation")
            has_slots = bool(st.session_state.graph and st.session_state.graph.get_slots())
            filled_slots = sum(1 for s in (st.session_state.graph.get_slots() if st.session_state.graph else []) if s.filled_content)
            total_slots = len(st.session_state.graph.get_slots()) if st.session_state.graph else 0
            
            st.metric("Slots Filled", f"{filled_slots}/{total_slots}")
            st.metric("Document Length", f"{len(st.session_state.output_latex)} chars")
            
            # Check for common LaTeX issues
            issues = []
            if "\\begin{document}" not in st.session_state.output_latex:
                issues.append("Missing \\begin{document}")
            if "\\end{document}" not in st.session_state.output_latex:
                issues.append("Missing \\end{document}")
            
            if issues:
                st.warning("Potential issues: " + ", ".join(issues))
            else:
                st.success("Basic LaTeX structure checks passed!")
    else:
        st.info("Run the NPvert pipeline in the Processing tab to generate output.")

# Footer
st.markdown("---")
st.markdown("*NPvert: Combining neural retrieval with compiler-enforced determinism*")
