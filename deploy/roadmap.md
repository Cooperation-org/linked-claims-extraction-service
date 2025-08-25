# Development Roadmap - Week of Aug 25, 2025

## ⚠️ CRITICAL: Data Quality Requirements

**NEVER use fake/placeholder URLs in real claims:**
- NO example.com, test.com, or placeholder domains
- Claims create REAL data - must use actual verifiable URLs
- Use dev.linkedtrust.us backend (not live) during development
- Subject/object URIs must be real: Wikipedia, LinkedIn, official websites, etc.

## Overview
Transform the extraction service into a professional demo for donor funds showcasing verifiable impact extraction and visualization.

## Phase 1: Core Functionality (Days 1-3)

### Day 1: Backend Publishing & URI Quality
- [ ] **Fix URI generation quality**
  - Update ClaimExtractor prompts to use Wikipedia, LinkedIn, official sites
  - NEVER generate example.com or placeholder URLs
  - Add fallback to prompt user for correct URLs if uncertain
  
- [ ] **Implement claim review interface**
  - Show full claim details: subject, statement, object URIs
  - Allow users to edit/correct URIs before publishing
  - Display statement text for verification

- [ ] **Implement LinkedTrust publishing**
  - Add publishing to `https://dev.linkedtrust.us/api` (NOT live during dev)
  - Include PDF URL as source in claims
  - Handle authentication (see talent repo patterns)
  - Test end-to-end: PDF → extraction → review → publishing

### Day 2: Frontend Foundation
- [ ] **Get LinkedTrust branding access**
  - Request access to linkedtrust.us website repo for branding assets
  - Copy styling, colors, fonts, layout patterns

- [ ] **Create professional landing page**
  - Hero section explaining verifiable impact extraction
  - Demo upload area for PDFs
  - Professional copy targeting donor funds/foundations

### Day 3: Claim Visualization
- [ ] **Implement graph visualization**
  - Study talent repo graph implementation
  - Use LinkedTrust graph API to display extracted claims
  - Show claim relationships and verification status

## Phase 2: Polish & Demo Prep (Days 4-5)

### Day 4: UX & Quality
- [ ] **Improve extraction feedback**
  - Progress indicators during processing
  - Clear success/error states
  - Preview of extracted claims before publishing

- [ ] **Add claim signing**
  - Sign claims according to LinkedClaims spec
  - Include PDF URL as proper source attribution

### Day 5: Demo Ready
- [ ] **Final testing & polish**
  - Test with various PDF types
  - Ensure professional appearance
  - Verify all claims are properly signed and published

## Technical Requirements

### API Integration
- Use LinkedTrust shared trust claim API
- Follow Identity Foundation LinkedClaims patterns
- Reference talent repo for graph API usage patterns

### Quality Standards
- Claims must have verifiable URIs (not placeholder text)
- PDF source must be properly attributed
- Professional UI suitable for donor presentation

### Future (Phase 2)
- Factor out common graph API patterns into `create-trust-app` starter repo
- Shared libraries for common LinkedTrust integration patterns

## Success Criteria
✅ Professional demo ready for donor funds  
✅ Real PDFs → quality claims → published to LinkedTrust  
✅ Claims displayed in convincing graph visualization  
✅ Proper branding matching linkedtrust.us  
✅ All claims signed with PDF source attribution