#!/usr/bin/env python3
"""
Test all URL resolver fixes
"""
import os
import sys
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_all_url_fixes():
    """Test all URL resolver fixes"""
    try:
        from url_resolver import resolve_organization_urls
        
        logger.info("="*60)
        logger.info("TESTING ALL URL RESOLVER FIXES")
        logger.info("="*60)
        
        # Sample document context with Global Fund full name
        document_context = """
        In response, big new organizations helped accelerate progress, like
        Gavi, the Vaccine Alliance and the Global Fund to Fight AIDS,
        Tuberculosis, and Malaria. For the first time in human history,
        basic lifesaving health care was made available to hundreds of
        millions of people: AIDS medications, contraceptives, childhood
        vaccines, bed nets to prevent malaria.
        """
        
        # Sample document URL
        document_url = "https://example.com/document/123"
        
        # Test claims with different scenarios
        test_claims = [
            {
                "subject": "urn:local:org:Global_Fund",
                "claim": "impact",
                "object": "urn:local:person:John_Doe:Kenya", 
                "statement": "Global Fund provides AIDS medications",
                "howKnown": "DOCUMENT"
            },
            {
                "subject": "urn:local:org:GAVI_Vaccine_Alliance",
                "claim": "impact",
                "object": "urn:local:population:children:Global",
                "statement": "GAVI provides vaccines to children",
                "howKnown": "DOCUMENT"
            }
        ]
        
        logger.info("Original claims:")
        for i, claim in enumerate(test_claims):
            logger.info(f"Claim {i+1}:")
            logger.info(f"  Subject: {claim['subject']}")
            logger.info(f"  Object: {claim['object']}")
            logger.info(f"  Statement: {claim['statement']}")
        
        # Test resolution with context and document URL
        logger.info(f"\nResolving claims with context and document URL...")
        resolved_claims = resolve_organization_urls(
            test_claims.copy(), 
            context=document_context, 
            document_url=document_url
        )
        
        logger.info(f"\n{'='*40}")
        logger.info("RESOLVED CLAIMS ANALYSIS")
        logger.info(f"{'='*40}")
        
        for i, claim in enumerate(resolved_claims):
            logger.info(f"\nClaim {i+1} Results:")
            logger.info(f"  Subject: {claim['subject']}")
            logger.info(f"  Object: {claim['object']}")
            
            # Check if URLs need verification
            if claim.get('urls_need_verification'):
                logger.info("  ✓ URLs need verification (as expected)")
                
                # Check subject URL candidates
                if 'subject_url_candidates' in claim:
                    candidates = claim['subject_url_candidates']
                    logger.info(f"  ✓ Subject URL candidates: {len(candidates)}")
                    for j, candidate in enumerate(candidates[:3]):
                        logger.info(f"    {j+1}. {candidate.get('url', 'N/A')} (confidence: {candidate.get('confidence', 0):.3f})")
                else:
                    logger.info("  ⚠️ No subject URL candidates found")
            else:
                logger.info("  ✓ URLs resolved automatically")
            
            # Check object URL handling
            obj = claim.get('object', '')
            if obj.startswith('urn:local:person:') or obj.startswith('urn:local:population:'):
                if obj == document_url:
                    logger.info("  ✓ Object URL correctly set to document URL")
                elif obj.startswith('urn:local:'):
                    logger.info("  ⚠️ Object still has URN format - expected document URL")
                else:
                    logger.info(f"  ? Object URL: {obj}")
            
            # Check for correct URLs in candidates
            if 'subject_url_candidates' in claim:
                candidates = claim['subject_url_candidates']
                found_correct_url = False
                
                for candidate in candidates:
                    url = candidate.get('url', '')
                    if 'theglobalfund.org' in url or 'gavi.org' in url:
                        found_correct_url = True
                        logger.info(f"  ✓ Found correct URL: {url}")
                        break
                
                if not found_correct_url:
                    logger.info("  ⚠️ Correct official URL not found in candidates")
                    logger.info("  Top candidates:")
                    for j, candidate in enumerate(candidates[:3]):
                        logger.info(f"    {j+1}. {candidate.get('url', 'N/A')}")
        
        # Test Global Fund specifically
        logger.info(f"\n{'='*40}")
        logger.info("GLOBAL FUND SPECIFIC TEST")
        logger.info(f"{'='*40}")
        
        global_fund_claim = resolved_claims[0]  # First claim is Global Fund
        
        logger.info(f"Global Fund subject: {global_fund_claim['subject']}")
        
        if 'subject_url_candidates' in global_fund_claim:
            candidates = global_fund_claim['subject_url_candidates']
            logger.info(f"Global Fund candidates: {len(candidates)}")
            
            # Check if theglobalfund.org is in candidates
            found_official = False
            for candidate in candidates:
                if 'theglobalfund.org' in candidate.get('url', '').lower():
                    found_official = True
                    logger.info(f"✅ Found official Global Fund URL: {candidate['url']}")
                    logger.info(f"   Confidence: {candidate.get('confidence', 0):.3f}")
                    break
            
            if not found_official:
                logger.info("❌ Official Global Fund URL not found")
                logger.info("Available candidates:")
                for candidate in candidates[:5]:
                    logger.info(f"  - {candidate.get('url', 'N/A')} (confidence: {candidate.get('confidence', 0):.3f})")
        else:
            logger.info("❌ No URL candidates for Global Fund")
        
        # Test object URL fallback
        logger.info(f"\n{'='*40}")
        logger.info("OBJECT URL FALLBACK TEST")
        logger.info(f"{'='*40}")
        
        for i, claim in enumerate(resolved_claims):
            obj = claim.get('object', '')
            logger.info(f"Claim {i+1} object: {obj}")
            
            if obj == document_url:
                logger.info(f"  ✅ Object correctly set to document URL")
            elif obj.startswith('urn:local:'):
                logger.info(f"  ❌ Object still has URN format: {obj}")
            elif obj.startswith('http'):
                logger.info(f"  ✓ Object has URL format: {obj}")
        
        logger.info(f"\n{'='*60}")
        logger.info("ALL URL RESOLVER FIXES TEST COMPLETED")
        logger.info(f"{'='*60}")
        
        # Summary
        issues_found = []
        
        # Check if Global Fund has candidates
        if not resolved_claims[0].get('subject_url_candidates'):
            issues_found.append("Global Fund has no URL candidates")
        
        # Check if objects were converted to document URLs
        person_objects_fixed = all(
            claim['object'] == document_url 
            for claim in resolved_claims 
            if claim.get('object', '').startswith('urn:local:person:') or claim.get('object', '').startswith('urn:local:population:')
        )
        if not person_objects_fixed:
            issues_found.append("Person/population objects not converted to document URL")
        
        if issues_found:
            logger.info(f"\n⚠️ Issues found:")
            for issue in issues_found:
                logger.info(f"  - {issue}")
            return False
        else:
            logger.info(f"\n✅ All fixes working correctly!")
            return True
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_all_url_fixes()
    if success:
        print("\n🎉 All URL resolver fixes working correctly!")
    else:
        print("\n⚠️ Some fixes need additional work")