# NPvert: Structure-First RAG for LaTeX Document Synthesis

NPvert is a Structure-First Retrieval-Augmented Generation (RAG) framework that reconceptualizes document generation as a constrained symbolic placement problem rather than an unconstrained text generation task. It guarantees compilable LaTeX and consistently produces high-fidelity PDF outputs by separating semantic reasoning from syntactic realization.

## Features

- **AST-Based LaTeX Parser**: Parses templates into hierarchical Abstract Syntax Trees
- **Structure Graph (DAG)**: Encodes document hierarchy, constraints, and semantic anchors
- **Semantic Anchoring**: Uses Gemini Pro LLM for intelligent content placement
- **Graph Visualization**: Interactive visualization of document structure
- **DOCX Support**: Converts DOCX files to LaTeX before processing
- **PDF Compilation**: Compile generated LaTeX to PDF with one click
- **Preformatted Templates**: Research Paper, Technical Report, Resume, Letter
- **Sample Content**: Ready-to-use sample files for testing

## Architecture

```
LaTeX Template + Incoming Content → AST Parser → Structure Graph (DAG)
                                              ↓
                                        Semantic Anchoring (LLM)
                                              ↓
                                        Graph Validation
                                              ↓
                                     LaTeX-Safe Realization
                                              ↓
                                       Verified PDF Output
```

## Installation

```bash
# Install Python dependencies
python3 -m pip install -r requirements.txt

# Install LaTeX compiler for PDF generation (choose one)

# Option 1: Tectonic (Recommended - smallest, downloads packages on demand)
brew install tectonic  # macOS
# See https://tectonic-typesetting.github.io/ for other platforms

# Option 2: MacTeX (Full distribution, ~4GB)
brew install --cask mactex  # macOS

# Option 3: BasicTeX (Minimal, ~1GB)
brew install --cask basictex  # macOS

# Optional: Install pandoc for enhanced DOCX support
brew install pandoc  # macOS
```

## Usage

### Run the Streamlit Application

```bash
streamlit run app.py
```

Or if streamlit is not on your PATH:

```bash
python3 -m streamlit run app.py
```

### Workflow

1. **Input Tab**: 
   - Upload or paste a LaTeX template with `% SLOT: SLOT_NAME` markers
   - Upload or paste content to be formatted
   - Or load from preformatted templates and sample files in the sidebar

2. **Structure Graph Tab**:
   - Click "Parse Template & Build Graph" to visualize the document structure
   - View slots, sections, and hierarchy

3. **Processing Tab**:
   - Click "Run NPvert Pipeline" to:
     - Analyze content into semantic blocks
     - Compute anchoring scores
     - Place content into appropriate slots
     - Generate compilable LaTeX

4. **Output Tab**:
   - Review generated LaTeX
   - Download `.tex` file
   - Compile to PDF (requires LaTeX distribution)
   - Download PDF

### Template Slot Syntax

Mark fillable regions in your LaTeX templates with slot comments:

```latex
\section{Introduction}
% SLOT: INTRODUCTION

\begin{abstract}
% SLOT: ABSTRACT
\end{abstract}
```

## Project Structure

```
NPvert/
├── app.py                 # Streamlit application
├── parser.py              # LaTeX AST parser
├── graph_builder.py       # Structure Graph (DAG) builder
├── llm_placer.py          # Gemini Pro semantic placer
├── docx_converter.py      # DOCX to LaTeX converter
├── requirements.txt       # Python dependencies
├── templates/             # Preformatted LaTeX templates
│   ├── research_paper.tex
│   ├── technical_report.tex
│   ├── resume.tex
│   └── letter.tex
└── samples/               # Sample raw content files
    ├── research_content.txt
    ├── project_report.txt
    └── personal_profile.txt
```

## Key Concepts

### Execution Illusion
The discrepancy between linguistic plausibility and executable validity. LLMs often generate LaTeX that looks correct but fails to compile due to structural violations.

### Structure-First Approach
Instead of treating document synthesis as text generation, NPvert:
1. Parses the template into a verified structural representation
2. Uses LLMs only for semantic reasoning (where content belongs)
3. Delegates syntactic realization to deterministic graph operations

### Semantic Anchoring
Content is embedded and compared against semantic anchors associated with Structure Graph nodes. Each node receives an anchoring score reflecting semantic compatibility.

### Graph-Based Validation
All candidate placements undergo validation to ensure compliance with structural constraints, including environment legality and hierarchical consistency.

## API Key

The application uses Google Gemini Pro for semantic analysis. The API key is embedded in `app.py` for demonstration. For production use, consider using environment variables:

```python
import os
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-key-here")
```

## Limitations

- PDF compilation requires a LaTeX distribution (TeX Live, MiKTeX, or MacTeX)
- Gemini Pro API has rate limits
- Complex custom LaTeX macros may require manual adjustment
- DOCX conversion handles basic formatting; complex layouts may need cleanup

## References

Based on the research paper: *NPvert: Structure-First RAG for LaTeX Document Synthesis* by Nishant Dixit and Pallav Rai.

## License

MIT License
