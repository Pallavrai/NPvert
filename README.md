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

## Requirements

- Python 3.10 - 3.12+ (tested on 3.12)
- Google Gemini API key

## Local Installation

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

## Local Usage

### 1. Set up your API key

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Run the Streamlit Application

```bash
streamlit run app.py
```

Or if streamlit is not on your PATH:

```bash
python3 -m streamlit run app.py
```

## Deploy to Streamlit Cloud

### 1. Prepare your repository

Ensure these files are committed to your GitHub repo:
- `requirements.txt`
- `runtime.txt` (specifies Python 3.12)
- `packages.txt` (system dependencies)
- `.streamlit/config.toml`
- All app code and assets

### 2. Set up Streamlit Secrets

In your Streamlit Cloud dashboard, go to **Settings → Secrets** and add:

```toml
GEMINI_API_KEY = "your_gemini_api_key_here"
```

### 3. Deploy

1. Connect your GitHub repo at [share.streamlit.io](https://share.streamlit.io)
2. Select the repository and branch
3. Click **Deploy**

The `runtime.txt` file tells Streamlit Cloud to use Python 3.12, and `packages.txt` installs `poppler-utils` for PDF preview support.

## Workflow

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
   - Compile to PDF (requires LaTeX distribution — not available on Streamlit Cloud free tier)
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
├── llm_placer.py          # Gemini semantic placer
├── docx_converter.py      # DOCX to LaTeX converter
├── requirements.txt       # Python dependencies
├── runtime.txt            # Streamlit Cloud Python version
├── packages.txt           # Streamlit Cloud system deps
├── .streamlit/
│   └── config.toml        # Streamlit configuration
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

## API Key Setup

The application uses Google Gemini for semantic analysis. You can provide the API key in two ways:

1. **Local development**: Create a `.env` file with `GEMINI_API_KEY=your_key`
2. **Streamlit Cloud**: Add `GEMINI_API_KEY` to your app secrets in the Streamlit dashboard

## Limitations

- PDF compilation requires a LaTeX distribution (TeX Live, MiKTeX, or MacTeX) — not available on Streamlit Cloud free tier
- Gemini API has rate limits
- Complex custom LaTeX macros may require manual adjustment
- DOCX conversion handles basic formatting; complex layouts may need cleanup

## References

Based on the research paper: *NPvert: Structure-First RAG for LaTeX Document Synthesis* by Nishant Dixit and Pallav Rai.

## License

MIT License
