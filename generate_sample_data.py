"""
Generate Realistic Sample Data for Migration Readiness Assessment

Scenario: "TechCo" - Mid-size e-commerce company
- 10 Engineers, 8 Product managers, 4 Business stakeholders, 4 Leadership
- Strong engineering culture but siloed teams
- Business frustrated with delivery speed
- Leadership supportive but lacks technical depth
- Legacy monolith causing friction, some early modernisation work done

This creates data that demonstrates:
- Mix of RED/AMBER/GREEN domains
- Clear alignment gaps between roles
- Realistic qualitative feedback
- Meaningful statistical patterns
"""

import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)  # Reproducible results

# Load questionnaire to understand structure
questionnaire = pd.read_csv('Questions/export.csv', index_col='ID')

# =============================================================================
# SCENARIO CONFIGURATION
# =============================================================================

# Define how each role perceives each domain (mean score, std deviation)
# Format: {domain: {role: (mean, std)}}
ROLE_PERCEPTIONS = {
    'Architecture & Technology': {
        'Engineering': (3.8, 0.7),    # Engineers see progress, some gaps
        'Product': (3.2, 0.8),        # Product sees limitations
        'Business': (2.6, 0.9),       # Business doesn't see the tech side
        'Leadership': (3.4, 0.8),     # Leadership cautiously optimistic
    },
    'Team Capability': {
        'Engineering': (4.0, 0.6),    # Engineers confident in skills
        'Product': (3.5, 0.7),        # Product sees coordination issues
        'Business': (3.0, 0.8),       # Business doesn't interact much
        'Leadership': (3.6, 0.7),     # Leadership trusts teams
    },
    'Governance & Delivery': {
        'Engineering': (3.4, 0.8),    # Engineers see process friction
        'Product': (2.8, 0.9),        # Product frustrated with delivery
        'Business': (2.5, 1.0),       # Business sees delays
        'Leadership': (3.2, 0.8),     # Leadership aware of issues
    },
    'Integration & Data Readiness': {
        'Engineering': (3.2, 0.8),    # Engineers know the tech debt
        'Product': (2.9, 0.8),        # Product sees integration pain
        'Business': (2.4, 0.9),       # Business struggles with data access
        'Leadership': (2.8, 0.9),     # Leadership hears complaints
    },
    'Business Alignment & Strategy': {
        'Engineering': (3.0, 0.9),    # Engineers feel disconnected
        'Product': (3.4, 0.7),        # Product closer to strategy
        'Business': (3.6, 0.7),       # Business owns this
        'Leadership': (4.0, 0.6),     # Leadership confident here
    },
    'Cultural Readiness': {
        'Engineering': (3.6, 0.7),    # Engineers open to change
        'Product': (3.4, 0.8),        # Product sees mixed signals
        'Business': (2.8, 0.9),       # Business more conservative
        'Leadership': (3.8, 0.6),     # Leadership pushing change
    },
}

# Specific question adjustments (question_id: {role: adjustment})
# Positive = score higher, Negative = score lower
QUESTION_ADJUSTMENTS = {
    # Critical questions that should score low (to show risk)
    8: {'Engineering': -0.5, 'Product': -0.8},   # Monolith mapping
    88: {'Engineering': -0.6, 'Business': -1.0}, # Legacy data understood
    94: {'Business': -1.2, 'Leadership': -0.8},  # Shared understanding of success

    # Questions showing alignment gaps
    56: {'Business': -1.5, 'Engineering': 0.5},  # Business aware of bottlenecks
    126: {'Engineering': 0.8, 'Business': -0.8}, # Openness to change

    # Questions that should score high (strengths)
    27: {'Engineering': 0.8},  # Engineers understand distributed systems
    28: {'Engineering': 0.7},  # Experience with APIs/microservices
    133: {'Leadership': 0.8},  # Internal champions for change
}

# Qualitative response templates by sentiment
QUALITATIVE_RESPONSES = {
    'Engineering': {
        'positive': [
            "We've made solid progress on decoupling key services. The team is energised and we're seeing real benefits from the modular approach we've taken so far.",
            "Our engineering culture is strong - people want to do the right thing. We just need clearer direction and time allocated for platform work.",
            "The new API patterns we've introduced are working well. Teams are starting to see how this enables faster delivery.",
            "We have good technical foundations in place. The challenge is getting business buy-in for the investment needed.",
            "Collaboration between squads has improved significantly. We're sharing more knowledge and patterns across teams.",
        ],
        'neutral': [
            "Progress is mixed. Some areas are well-architected, others are still tightly coupled to the monolith. We need a clearer roadmap.",
            "We have the skills, but coordination overhead is slowing us down. Too many dependencies between teams.",
            "Documentation is improving but still patchy. New joiners struggle to understand the full picture.",
            "CI/CD is good for newer services, but legacy deployments are still manual and risky.",
            "We're making incremental progress but it feels slow. Hard to carve out time from feature work.",
        ],
        'negative': [
            "Technical debt is significant and not being addressed. We keep adding to it with every release.",
            "The monolith is a major blocker. Changes in one area break things elsewhere. Testing is a nightmare.",
            "Knowledge is concentrated in a few people. If they leave, we'd be in serious trouble.",
            "Release processes are painful. Too many manual steps and approvals slow everything down.",
            "We don't have visibility into how services communicate. Debugging production issues takes forever.",
        ],
    },
    'Product': {
        'positive': [
            "Engineering has been responsive to our needs. The recent platform improvements are helping us deliver faster.",
            "Cross-functional collaboration is better than it was. We're involved earlier in technical discussions.",
            "The shift toward composable architecture makes sense for our roadmap. It will unlock features we've been waiting to build.",
            "Team autonomy has improved. Squads can make more decisions without escalating everything.",
        ],
        'neutral': [
            "Delivery speed is okay but could be better. We often have to compromise scope due to technical constraints.",
            "We understand the need for platform investment but it's hard to prioritise against feature requests.",
            "Communication with engineering is improving but we don't always understand the technical trade-offs.",
            "Some teams deliver quickly, others are constantly blocked. Consistency is the issue.",
        ],
        'negative': [
            "Platform limitations are directly impacting our ability to serve customers. Personalisation and localisation are blocked.",
            "We see slow release cycles and integration issues constantly. Hard to adapt to market changes.",
            "Technical complexity is leaking into product decisions. We have to design around system limitations.",
            "Dependencies between teams cause constant delays. Simple features take months to deliver.",
        ],
    },
    'Business': {
        'positive': [
            "Leadership is clearly committed to this transformation. We have the sponsorship we need.",
            "The potential benefits are clear - faster time to market, better customer experience, reduced costs.",
            "We're seeing early wins from the modularisation work. Integration with partners is getting easier.",
        ],
        'neutral': [
            "We understand the need for platform investment but need clearer ROI metrics to justify the cost.",
            "Technology constraints aren't always visible to us. We'd benefit from more transparency.",
            "The migration timeline feels unclear. Hard to plan business initiatives around it.",
        ],
        'negative': [
            "Platform limitations hurt us directly - especially personalisation and localisation capabilities.",
            "Technical constraints are not always communicated clearly. We get surprised by delays.",
            "Data access is a constant struggle. We rely heavily on engineering for reports that should be self-service.",
            "Release processes seem to hinder rather than help. Simple changes take too long to go live.",
            "We don't have confidence in the current platform's ability to scale with business growth.",
        ],
    },
    'Leadership': {
        'positive': [
            "We're committed to this investment. The strategic case for modernisation is clear and well-understood.",
            "Our teams have the capability to execute this. We need to create the right conditions for success.",
            "Early results from pilot projects are encouraging. The approach is sound.",
            "Cross-functional alignment is improving. Regular steering meetings help keep everyone informed.",
        ],
        'neutral': [
            "We understand the technical challenges at a high level. Need to balance platform work with business delivery.",
            "Risk is manageable if we take a phased approach. We can't afford a big-bang migration.",
            "Change management will be critical. Not everyone is equally ready for new ways of working.",
            "ROI clarity would help with board conversations. We need better metrics for platform investment.",
        ],
        'negative': [
            "Concerned about execution risk. Past initiatives have overrun timelines and budgets.",
            "Cultural resistance in some areas may slow us down. Not everyone sees the need for change.",
            "Technical debt has accumulated over years. Addressing it will require sustained investment.",
        ],
    },
}


def generate_score(base_mean, std, adjustment=0, min_val=1, max_val=5):
    """Generate a Likert score with constraints."""
    score = np.random.normal(base_mean + adjustment, std)
    score = max(min_val, min(max_val, score))
    return int(round(score))


def generate_quantitative_responses(quest_df, n_respondents, role):
    """Generate quantitative responses for a role."""

    responses = []

    for _ in range(n_respondents):
        row = {}

        for q_id in quest_df.index:
            q_row = quest_df.loc[q_id]

            # Check if this role should answer this question
            if not q_row.get(role, False):
                row[q_id] = 0  # Not applicable
                continue

            if q_row['Type'] != 'Quantitative':
                continue

            # Get base perception for this domain/role
            domain = q_row['Category']
            if domain in ROLE_PERCEPTIONS and role in ROLE_PERCEPTIONS[domain]:
                base_mean, std = ROLE_PERCEPTIONS[domain][role]
            else:
                base_mean, std = 3.0, 0.8

            # Apply question-specific adjustments
            adjustment = QUESTION_ADJUSTMENTS.get(q_id, {}).get(role, 0)

            # Generate score
            row[q_id] = generate_score(base_mean, std, adjustment)

        responses.append(row)

    return responses


def generate_qualitative_responses(quest_df, n_respondents, role):
    """Generate qualitative responses for a role."""

    responses = []
    role_templates = QUALITATIVE_RESPONSES.get(role, QUALITATIVE_RESPONSES['Engineering'])

    # Flatten all responses
    all_responses = (
        role_templates['positive'] +
        role_templates['neutral'] +
        role_templates['negative']
    )

    for resp_idx in range(n_respondents):
        row = {}

        # Determine sentiment bias for this respondent
        raw_weights = {
            'positive': 0.3 + np.random.uniform(-0.1, 0.1),
            'neutral': 0.4 + np.random.uniform(-0.1, 0.1),
            'negative': 0.3 + np.random.uniform(-0.1, 0.1),
        }
        # Normalize to sum to 1
        total = sum(raw_weights.values())
        sentiment_weights = {k: v/total for k, v in raw_weights.items()}

        for q_id in quest_df.index:
            q_row = quest_df.loc[q_id]

            if not q_row.get(role, False):
                row[q_id] = ''
                continue

            if q_row['Type'] != 'Qualitative':
                continue

            # Randomly select response based on sentiment weights
            sentiment = np.random.choice(
                ['positive', 'neutral', 'negative'],
                p=[sentiment_weights['positive'],
                   sentiment_weights['neutral'],
                   sentiment_weights['negative']]
            )

            available = role_templates.get(sentiment, role_templates['neutral'])
            if available:
                row[q_id] = np.random.choice(available)
            else:
                row[q_id] = ''

        responses.append(row)

    return responses


def generate_role_data(quest_df, role, n_respondents):
    """Generate complete dataset for a role."""

    quant_responses = generate_quantitative_responses(quest_df, n_respondents, role)
    qual_responses = generate_qualitative_responses(quest_df, n_respondents, role)

    # Merge quantitative and qualitative
    combined = []
    for i in range(n_respondents):
        row = {'Timestamp': f'2025-04-{20+i:02d} 10:{10+i:02d}:00'}
        row.update(quant_responses[i])
        row.update(qual_responses[i])
        combined.append(row)

    # Convert to DataFrame with question text as columns
    df = pd.DataFrame(combined)

    # Map question IDs back to question text for CSV
    id_to_text = quest_df['Question'].to_dict()
    df = df.rename(columns=id_to_text)

    return df


def main():
    """Generate all sample data files."""

    print("Generating sample data for Migration Readiness Assessment...")
    print("Scenario: TechCo - E-commerce company with legacy platform\n")

    # Configuration
    role_counts = {
        'Engineering': 10,
        'Product': 8,
        'Business': 4,
        'Leadership': 4,
    }

    output_dir = Path('Responses')
    output_dir.mkdir(exist_ok=True)

    for role, n in role_counts.items():
        print(f"Generating {n} {role} responses...")
        df = generate_role_data(questionnaire, role, n)

        output_file = output_dir / f'{role}.csv'
        df.to_csv(output_file, index=True)
        print(f"  Saved to {output_file}")

    print("\nSample data generation complete!")
    print("\nScenario characteristics:")
    print("  - Architecture & Technology: AMBER (3.2 avg) - some progress, gaps remain")
    print("  - Team Capability: GREEN (3.6 avg) - strong engineering culture")
    print("  - Governance & Delivery: RED/AMBER (2.9 avg) - process friction")
    print("  - Integration & Data: RED (2.8 avg) - significant pain point")
    print("  - Business Alignment: AMBER (3.4 avg) - improving but gaps")
    print("  - Cultural Readiness: AMBER (3.4 avg) - mixed signals")
    print("\nKey alignment gaps:")
    print("  - Business vs Engineering on technical bottlenecks awareness")
    print("  - Business vs Leadership on change readiness")
    print("  - Product vs Engineering on delivery speed perceptions")


if __name__ == '__main__':
    main()
