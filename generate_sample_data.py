"""
Generate realistic sample data for the Migration Readiness Assessment.

Scenario: "TechCo" - mid-size e-commerce company
- 18 Engineers, 10 Product managers, 8 Business stakeholders, 6 Leadership
- Strong engineering culture but siloed teams
- Business frustrated with delivery speed
- Leadership supportive but lacks technical depth
- Legacy monolith causing friction, some early modernisation work done

Unlike independent random answers, each simulated person has a consistent outlook:
- a general optimism offset and a per-domain offset (so domain scales are internally consistent)
- some respondents agree with everything (acquiescence), a few straight-line
- ~6% of answers are skipped and ~2% are "Don't know"
- free-text tone follows the person's own scores

Answers are written as labels ("Agree"), as a Google Forms export would.
"""

import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)  # Reproducible results

LABELS = {1: 'Strongly Disagree', 2: 'Disagree', 3: 'Neutral', 4: 'Agree', 5: 'Strongly Agree'}
ROLE_COUNTS = {'Engineering': 18, 'Product': 10, 'Business': 8, 'Leadership': 6}

PERSON_SD = 0.35        # general optimism / pessimism of a person
PERSON_DOMAIN_SD = 0.35 # person-specific view of a domain
ITEM_NOISE = 0.55       # item-level noise relative to the role's domain spread
P_ACQUIESCENT = 0.10
P_STRAIGHT_LINER = 0.04
P_SKIP = 0.06
P_DONT_KNOW = 0.02
P_TEXT_ANSWER = 0.6

# Load questionnaire to understand structure
questionnaire = pd.read_csv("Questions/export.csv", index_col="ID")
questionnaire["Question"] = questionnaire["Question"].fillna("")

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


def simulate_person(role, quest_df):
    """Return ({item_id: answer}, overall_optimism) for one respondent."""
    optimism = rng.normal(0, PERSON_SD)
    domain_view = {d: rng.normal(0, PERSON_DOMAIN_SD) for d in ROLE_PERCEPTIONS}
    acquiescent = rng.random() < P_ACQUIESCENT
    straight_line = rng.random() < P_STRAIGHT_LINER
    straight_value = int(np.clip(round(3.5 + optimism), 1, 5))

    answers, latent = {}, []
    for q_id, q_row in quest_df.iterrows():
        if q_row['Type'] != 'Quantitative' or not q_row[role]:
            continue
        domain = q_row['Category']
        mean, sd = ROLE_PERCEPTIONS.get(domain, {}).get(role, (3.0, 0.8))
        mu = mean + QUESTION_ADJUSTMENTS.get(q_id, {}).get(role, 0) + optimism + domain_view.get(domain, 0)
        mu += 0.5 if acquiescent else 0
        latent.append(mu)
        if rng.random() < P_SKIP:
            continue
        if rng.random() < P_DONT_KNOW:
            answers[q_id] = "Don't know"
            continue
        score = straight_value if straight_line else int(np.clip(round(rng.normal(mu, sd * ITEM_NOISE)), 1, 5))
        answers[q_id] = LABELS[score]
    return answers, float(np.mean(latent)) if latent else 3.0


def simulate_text(role, quest_df, person_level):
    """Free-text answers whose tone follows the person's own outlook."""
    templates = QUALITATIVE_RESPONSES.get(role, QUALITATIVE_RESPONSES['Engineering'])
    tilt = np.clip((person_level - 3.2) / 1.2, -1, 1)          # -1 pessimist .. +1 optimist
    p = np.array([0.3 + 0.25 * tilt, 0.4, 0.3 - 0.25 * tilt])
    p = p / p.sum()
    answers = {}
    for q_id, q_row in quest_df.iterrows():
        if q_row['Type'] != 'Qualitative' or not q_row[role] or rng.random() > P_TEXT_ANSWER:
            continue
        tone = rng.choice(['positive', 'neutral', 'negative'], p=p)
        options = templates.get(tone) or templates['neutral']
        answers[q_id] = options[rng.integers(len(options))]
    return answers


def generate_role_data(quest_df, role, n_respondents):
    rows = []
    for i in range(n_respondents):
        quant, level = simulate_person(role, quest_df)
        row = {'Timestamp': f'2026-10-{1 + i % 28:02d} 10:{i % 60:02d}:00'}
        row.update(quant)
        row.update(simulate_text(role, quest_df, level))
        rows.append(row)
    df = pd.DataFrame(rows)
    applicable = [q for q in quest_df.index if quest_df.at[q, role] and quest_df.at[q, 'Question'].strip()]
    df = df.reindex(columns=['Timestamp', *applicable])
    return df.rename(columns=quest_df['Question'].to_dict())


def main():
    print("Generating sample data for Migration Readiness Assessment...")
    print("Scenario: TechCo - E-commerce company with legacy platform\n")
    output_dir = Path('Responses')
    output_dir.mkdir(exist_ok=True)
    for role, n in ROLE_COUNTS.items():
        df = generate_role_data(questionnaire, role, n)
        output_file = output_dir / f'{role}.csv'
        df.to_csv(output_file, index=False)
        print(f"  {n:>3} {role:<12} -> {output_file}")
    print("\nDone. Run `mra report` to analyse it.")


if __name__ == '__main__':
    main()
