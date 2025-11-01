FILTERING PRIORITY: Extract only completed, verifiable outcomes from organizational reports.



CRITICAL FILTERING RULES:

NEVER extract statements containing future tense indicators:

\- "will", "plans", "exploring", "aims", "hopes", "seeks"

\- "could", "would", "may", "might", "potential" 

\- "in the future", "next year", "upcoming", "planned"



NEVER extract broad mission statements or aspirational language:

\- Organizational purposes without specific outcomes

\- General goals without measurable results

\- Vague improvement claims without concrete data



PRIORITIZE claims with:

\- Past tense action verbs ("built", "trained", "provided", "reduced")

\- Specific numbers, quantities, dates, locations

\- Concrete outcomes someone could verify by visiting or checking records

\- Completed activities with measurable results



SUBJECT and OBJECT must be valid URIs (URLs or URN format acceptable)

CLAIM should focus on "impact", "provided", "trained", "built", "reduced" - completed actions

STATEMENT should preserve specific numbers and completed outcomes only



EXAMPLE ACCEPTABLE:

\- "Trained 500 farmers between 2020-2022 in Kenya"

\- "Built 12 schools serving 3,000 students in rural Ethiopia" 

\- "Provided clean water to 50 villages, serving 25,000 people in 2023"



EXAMPLE REJECTED:

\- "Plans to train additional farmers next year"

\- "Working to improve healthcare access"

\- "Will provide access to 1,000 more people"

\- "Committed to ending poverty in our communities"



If no verifiable completed outcomes exist, return empty array \[].

Focus on quality over quantity - fewer verifiable claims are better than many unverifiable ones.

