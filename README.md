# Migration Readiness Assessment

A diagnostic framework for engineering leaders and CTOs evaluating whether their organisation is ready for platform modernisation—and whether modernisation is even the right call.

## Overview

**Microservices are not a silver bullet.** A well-designed monolith can outperform a poorly executed distributed system any day. But when your monolith becomes the reason features take months instead of weeks, when deployments require all-hands-on-deck ceremonies, when your best engineers spend more time fighting the system than building value—that's when the conversation needs to happen.

This tool exists because migration failures are rarely technical. They're organisational. Teams misaligned on priorities. Leadership unaware of technical debt. Business stakeholders and engineers living in different realities. These gaps don't surface in architecture diagrams—they surface six months into a failed transformation when it's too late to course-correct.

**Run this assessment before you commit.** Surface the misalignments, quantify the risks, and make the investment decision with data instead of gut feel. Sometimes the answer is "not yet." Sometimes it's "never." That's valuable information too.

The tool:
- Collects structured feedback from multiple stakeholder groups (Engineering, Product, Business, Leadership)
- Analyses responses across 6 readiness domains and 12 cross-cutting themes
- Applies statistical validation to identify significant findings
- Generates risk indicators using RAG (Red/Amber/Green) classification
- Extracts qualitative themes using NLP techniques (LDA topic modelling, sentiment analysis)

## Assessment Framework

### Readiness Domains

| Domain | Focus Area |
|--------|------------|
| **Architecture & Technology** | System modularity, API maturity, technical debt, documentation |
| **Team Capability** | Skills, autonomy, collaboration, knowledge distribution |
| **Governance & Delivery** | CI/CD maturity, ownership clarity, release processes |
| **Integration & Data Readiness** | API patterns, data governance, event-driven capabilities |
| **Business Alignment & Strategy** | Executive sponsorship, ROI clarity, roadmap alignment |
| **Cultural Readiness** | Change appetite, psychological safety, cross-functional trust |

### Cross-Cutting Themes

The questionnaire maps to themes that span multiple domains:

- Technical Confidence
- Clear Ownership
- Composable Integration
- Legacy Constraints
- Delivery Friction
- Autonomy & Empowerment
- Readiness for Change
- Cross-Functional Alignment
- Platform vs. Feature Tension
- Data Trust & Stewardship
- Strategic Sponsorship
- Testing & Quality

### Stakeholder Roles

Different roles receive targeted questions relevant to their perspective:

| Role | Focus |
|------|-------|
| **Engineering** | Architecture, technical debt, team capabilities, delivery practices |
| **Product** | Delivery velocity, team autonomy, business alignment |
| **Business** | Strategy alignment, data access, platform value perception |
| **Leadership** | Sponsorship, organisational alignment, change readiness |

## Project Structure

```
Migration-Readiness-Assessment/
├── Questions/
│   └── export.csv              # Questionnaire definition (150 quantitative + 119 qualitative)
├── Responses/
│   ├── Business.csv            # Business stakeholder responses
│   ├── Engineering.csv         # Engineering team responses
│   ├── Leadership.csv          # Leadership responses
│   └── Product.csv             # Product team responses
├── Output/
│   ├── analysis_results.txt    # AI-generated theme analysis
│   ├── combined_qualitative.csv
│   ├── combined_quantitative.csv
│   └── ldavis_prepared_10.html # Interactive topic visualisation
├── Validation.ipynb            # Main analysis notebook
├── generate_sample_data.py     # Script to generate realistic sample data
├── requirements.txt
└── env                         # Environment variable template
```

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Migration-Readiness-Assessment.git
cd Migration-Readiness-Assessment

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download NLTK data (required for sentiment analysis)
python -c "import nltk; nltk.download('vader_lexicon'); nltk.download('stopwords')"
```

## Configuration

Copy the environment template and add your OpenAI API key (optional, for AI-assisted qualitative analysis):

```bash
cp env .env
# Edit .env and add: OPENAI_API_KEY=your-key-here
```

## Running the Analysis

Open `Validation.ipynb` in Jupyter Lab or VS Code:

```bash
jupyter lab Validation.ipynb
```

The notebook executes the following pipeline:

### 1. Data Import & Preprocessing
- Loads questionnaire definitions and role-based responses
- Maps Likert scale responses (Strongly Disagree=1 to Strongly Agree=5)
- Separates quantitative and qualitative data streams

### 2. Quantitative Analysis

**Domain Scoring**
- Calculates average scores per domain (excluding non-responses)
- Identifies role-based perception variance
- Highlights domains with scores below confidence threshold (default: 3.0)

**Critical Question Weighting**
- Questions marked as "Critical" receive additional analysis
- Risk flags applied: Critical Risk (<2.5), At Risk (<3.0), No Risk (>=3.0)

**Statistical Validation**
- One-sample t-tests against neutral midpoint (3.0)
- Identifies statistically insignificant results (p > 0.05)
- Power analysis calculates required sample sizes for underpowered tests

**RAG Classification**
- Overall readiness score aggregated across all domains/roles
- Red: <3.0, Amber: 3.0-3.9, Green: >=4.0

### 3. Qualitative Analysis

**Topic Modelling (LDA)**
- Extracts latent topics from free-text responses
- Uses both Gensim and sklearn implementations
- Generates interactive visualisation (pyLDAvis)

**Sentiment Analysis (VADER)**
- Analyses emotional tone of qualitative responses
- Calculates positive, neutral, negative, and compound scores
- Aggregates by role to identify sentiment differences

**AI-Assisted Theme Extraction** (Optional)
- Uploads combined responses to OpenAI
- Extracts cross-role themes with supporting evidence
- Correlates with LDA topics

## Output Interpretation

### Domain Heatmap
Visual representation of scores by role and domain. High variance between roles indicates misalignment that should be addressed before migration.

### Risk Clusters
- **Red Clusters**: Domains where multiple roles score <3.0 - significant concerns
- **Amber Clusters**: Domains scoring 3.0-3.9 - areas requiring attention

### Critical Questions Report
Lists specific questions where critical items scored poorly - these represent the highest-risk areas for migration success.

### Statistical Significance Report
Questions that lack statistical significance may indicate:
- Insufficient sample size
- High response variance
- Questions that should be investigated further

### Topic Analysis
LDA topics reveal recurring themes in qualitative feedback. Example topics from the sample data:
- Business/tech alignment challenges
- Change management concerns
- Technical constraints and planning cycles
- Modernisation opportunities and team alignment

## Methodology Notes

### Scoring Approach
- Likert scale (1-5) provides ordinal data
- Mean calculations assume interval properties (standard practice for 5+ point scales)
- Zero values (non-responses) are excluded from calculations

### Statistical Considerations
- Small sample sizes (n<30) limit statistical power
- Power analysis helps determine if additional responses are needed
- High variance within roles may indicate subgroup differences worth exploring

### Qualitative Validity
- VADER sentiment is optimised for social media; business language may be under-detected
- LDA requires tuning number of topics (default: 5-10)
- Human review recommended for actionable insights

## Customisation

### Adjusting Thresholds

In `Validation.ipynb`, modify these variables:

```python
threshold_confidence_low = 3      # Below this triggers low-confidence flag
threshold_risk_critical = 2.5     # Below this triggers critical risk
threshold_risk_average = 3        # Below this triggers at-risk
rag_score_low = 3                 # Red threshold
rag_score_average = 3.9           # Amber threshold
threshold_statistical_significance = 0.05
```

### Adding Questions

Edit `Questions/export.csv` with columns:
- `ID`: Unique question identifier
- `Question`: Question text
- `Category`: Domain name
- `Critical`: TRUE/FALSE
- `Engineering`, `Product`, `Business`, `Leadership`: TRUE/FALSE for role targeting
- `Type`: "Quantitative" or "Qualitative"
- `Theme`: Optional cross-cutting theme
- `Weight`: Score multiplier (default: 1)

## Example Use Cases

1. **Pre-Migration Assessment**: Run before committing to a platform modernisation to identify blockers
2. **Stakeholder Alignment**: Surface perception gaps between technical and business teams
3. **Progress Tracking**: Re-run quarterly to measure improvement in readiness areas
4. **Investment Justification**: Provide data-driven evidence for platform investment decisions

## Statistical Methodology

The analysis uses rigorous statistical methods appropriate for survey data:

### Corrections Applied

| Feature | Standard Approach | This Implementation |
|---------|-------------------|---------------------|
| Power analysis | Two-sample formula | One-sample t-test formula (correct for this use case) |
| Target power | Varies | 0.80 (scientific convention) |
| Confidence intervals | z = 1.96 (assumes large N) | t-distribution (accounts for small samples) |
| Effect sizes | Often omitted | Cohen's d reported for all tests |
| Multiple comparisons | Often ignored | Benjamini-Hochberg FDR correction |
| Non-parametric tests | Often omitted | Wilcoxon signed-rank as alternative |

### Executive Decision Support

The notebook includes four analysis tools specifically designed for investment decisions:

1. **Executive Scorecard** - Single-view dashboard with:
   - Overall readiness percentage
   - RAG status per domain (weighted by critical questions)
   - Top risks and strengths at a glance
   - Summary counts (RED/AMBER/GREEN domains)

2. **Alignment Gap Analysis** - Identifies perception differences between stakeholder groups:
   - Questions where roles disagree by >1.0 points
   - Heatmap visualisation of role perceptions
   - Priority flags for critical misalignments

3. **Investment Prioritisation Matrix** - 2x2 matrix mapping domains by:
   - Readiness gap (how much work needed)
   - Business impact (how critical for migration)
   - Quadrants: Fix First, Quick Wins, Plan Carefully, Monitor

4. **Actionable Recommendations** - Concrete action plan including:
   - Phased recommendations (Immediate / Short-term / Medium-term / Long-term)
   - Domain-specific actions based on RAG status
   - Budget-level guidance (Low/Medium/High)
   - Go/No-Go recommendation with criteria

### Key Statistical Outputs

1. **Statistical Significance Analysis**
   - One-sample t-tests against neutral (3.0)
   - Wilcoxon signed-rank tests (non-parametric alternative)
   - Effect size calculation (Cohen's d) with interpretation
   - FDR-corrected p-values for multiple testing
   - Practical significance assessment (mean difference > 0.5)

2. **Power Analysis** (Cell 52)
   - Achieved power with current sample sizes
   - Required sample sizes for 80% power
   - Identifies underpowered tests needing more responses

3. **Confidence Intervals** (Cell 42)
   - t-distribution critical values (not z = 1.96)
   - Bootstrap CIs for robustness
   - Visual comparison against neutral reference line

### Interpreting Results

- **Statistically significant**: p < 0.05 after FDR correction
- **Practically significant**: Mean differs from neutral by >= 0.5 points
- **Effect sizes**: negligible (<0.2), small (0.2-0.5), medium (0.5-0.8), large (>0.8)
- **Adequately powered**: Achieved power >= 0.80

## Sample Data Scenario

The included sample data represents a fictional company "TechCo" - a mid-size e-commerce company evaluating migration from a legacy monolithic platform. The scenario demonstrates:

**Company Profile:**
- 10 Engineers, 8 Product managers, 4 Business stakeholders, 4 Leadership
- Strong engineering culture but siloed teams
- Business frustrated with delivery speed
- Leadership supportive but lacks technical depth
- Legacy monolith causing friction, some early modernisation work done

**Expected Results:**
| Domain | Expected Score | RAG Status | Notes |
|--------|---------------|------------|-------|
| Architecture & Technology | ~3.2 | AMBER | Some progress, gaps remain |
| Team Capability | ~3.6 | GREEN | Strong engineering culture |
| Governance & Delivery | ~2.9 | RED/AMBER | Process friction |
| Integration & Data Readiness | ~2.8 | RED | Significant pain point |
| Business Alignment & Strategy | ~3.4 | AMBER | Improving but gaps |
| Cultural Readiness | ~3.4 | AMBER | Mixed signals |

**Key Alignment Gaps Demonstrated:**
- Business vs Engineering on technical bottleneck awareness
- Business vs Leadership on change readiness
- Product vs Engineering on delivery speed perceptions

To regenerate sample data: `python3 generate_sample_data.py`

## Limitations

- Sample data is synthetic/illustrative (regenerate with `generate_sample_data.py`)
- Requires honest, representative responses from stakeholders
- Cultural factors may affect response patterns across organisations
- Statistical methods assume normally distributed responses (improved module offers non-parametric alternatives)

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome. Please open an issue to discuss proposed changes before submitting PRs.

---

## Information for Participants

### What's this about?
Your organisation is exploring opportunities to evolve its technology platforms to better support speed, scalability, and alignment with business needs. This questionnaire helps identify strengths, gaps, and opportunities across teams and technologies.

### Who should take part?
- **Engineering**: Architecture, system maturity, team capabilities, technical bottlenecks
- **Product**: Delivery practices, team autonomy, business alignment
- **Business**: Strategy, integration readiness, platform value understanding
- **Leadership**: Sponsorship, organisational alignment, cultural support

### How it works
- Takes approximately 10-15 minutes
- Rate statements using a 1-5 scale (Strongly Disagree to Strongly Agree)
- Optional comments provide valuable context

### What happens next
Results are analysed to generate a report that:
- Summarises readiness across six domains
- Visualises alignment and gaps between roles
- Provides actionable recommendations

This is a diagnostic tool, not a performance review.
