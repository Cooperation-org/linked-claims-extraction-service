from claim_extractor import ClaimExtractor as OriginalExtractor
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

class ClaimExtractor(OriginalExtractor):
    def make_prompt(self, custom_prompt=None):
        organizational_impact_template = """
CRITICAL CONSTRAINT: Output ONLY URN format. NO https:// URLs WHATSOEVER.

If you output ANY https:// URL, the extraction completely fails.

EXAMPLES OF WRONG vs RIGHT:
WRONG: "https://en.wikipedia.org/wiki/Ethiopia"
RIGHT: "urn:local:program:Ethiopia_Salt_Program:Ethiopia"

WRONG: "https://en.wikipedia.org/wiki/MoreMilk" 
RIGHT: "urn:local:org:MoreMilk"

CONSTRAINT: Every subject and object MUST start with "urn:local:"

Extract organizational impact claims with URN format ONLY.
Post-processing will convert to real URLs.

SUBJECT FORMAT: urn:local:org:Name or urn:local:program:Name:Location
OBJECT FORMAT: urn:local:person:Name:Location or urn:local:population:group:location

Extract from documents about organizations helping individuals/populations.
Include testimonial attribution in statements.

CRITICAL: Ensure extraction of complete stories:
- MoreMilk training programs helping farmers like Coletta Kemboi
- Government subsidy programs helping individuals like Sushama Das  
- LEAP training programs in India
- Look for MULTIPLE organizations in same document

SCHEMA:
{{
  "subject": "urn:local:org:OrganizationName",
  "claim": "impact", 
  "object": "urn:local:person:PersonName:Location",
  "statement": "Organization helped person achieve outcomes. Person testified about results.",
  "testimonial_source": "Person Name, Document Name",
  "howKnown": "DOCUMENT"
}}

MANDATORY URN EXAMPLES:
- "subject": "urn:local:org:MoreMilk"
- "subject": "urn:local:program:LEAP:Odisha_India"
- "object": "urn:local:person:Coletta_Kemboi:Maili_Nne_Kenya"
- "object": "urn:local:population:dairy_farmers:Kenya"

ABSOLUTELY FORBIDDEN:
- "subject": "https://anything..."
- "object": "https://en.wikipedia.org/wiki/Kenya"
- Any URL with https://

Output: JSON array with URN format ONLY.
        """
        
        if custom_prompt:
            human_template = custom_prompt + "\n{text}"
        else:
            human_template = "{text}"
        
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(organizational_impact_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])