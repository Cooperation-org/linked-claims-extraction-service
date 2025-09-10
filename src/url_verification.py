"""
URL Verification System - Human-verified URL caching with approval workflow
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class VerificationStatus(Enum):
    UNVERIFIED = "unverified"
    APPROVED = "approved" 
    REJECTED = "rejected"
    PENDING = "pending"

@dataclass
class URLCandidate:
    id: str
    organization: str
    url: str
    title: str
    confidence: float
    status: VerificationStatus
    found_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    rejection_reason: Optional[str] = None

class URLVerificationManager:
    """Manages URL verification workflow with persistent caching"""
    
    def __init__(self):
        # For now use in-memory storage - will be replaced with database
        self.candidates: Dict[str, URLCandidate] = {}
        self.verified_urls: Dict[str, str] = {}  # org_name -> verified_url
        self.pending_verifications: Dict[str, List[str]] = {}  # org_name -> [candidate_ids]
    
    def add_url_candidates(self, org_name: str, candidates: List[Tuple[str, str, float]]) -> List[URLCandidate]:
        """
        Add URL candidates for an organization that need verification
        
        Args:
            org_name: Organization name (normalized)
            candidates: List of (title, url, confidence) tuples
            
        Returns:
            List of URLCandidate objects with unique IDs
        """
        url_candidates = []
        
        for title, url, confidence in candidates:
            candidate_id = str(uuid.uuid4())
            
            candidate = URLCandidate(
                id=candidate_id,
                organization=org_name,
                url=url,
                title=title,
                confidence=confidence,
                status=VerificationStatus.UNVERIFIED,
                found_at=datetime.utcnow()
            )
            
            self.candidates[candidate_id] = candidate
            url_candidates.append(candidate)
            
            # Add to pending list
            if org_name not in self.pending_verifications:
                self.pending_verifications[org_name] = []
            self.pending_verifications[org_name].append(candidate_id)
        
        logger.info(f"Added {len(url_candidates)} URL candidates for {org_name}")
        return url_candidates
    
    def get_verified_url(self, org_name: str) -> Optional[str]:
        """Get verified URL for organization if available"""
        return self.verified_urls.get(org_name)
    
    def approve_url(self, candidate_id: str, user_id: str) -> bool:
        """
        Approve a URL candidate as correct
        
        Args:
            candidate_id: ID of candidate to approve
            user_id: User who approved it
            
        Returns:
            True if successfully approved
        """
        if candidate_id not in self.candidates:
            logger.error(f"Candidate {candidate_id} not found")
            return False
        
        candidate = self.candidates[candidate_id]
        candidate.status = VerificationStatus.APPROVED
        candidate.verified_at = datetime.utcnow()
        candidate.verified_by = user_id
        
        # Store as verified URL for the organization
        self.verified_urls[candidate.organization] = candidate.url
        
        # Remove from pending
        if candidate.organization in self.pending_verifications:
            if candidate_id in self.pending_verifications[candidate.organization]:
                self.pending_verifications[candidate.organization].remove(candidate_id)
            
            # Mark other candidates for same org as rejected
            for other_id in self.pending_verifications[candidate.organization][:]:
                other_candidate = self.candidates[other_id]
                other_candidate.status = VerificationStatus.REJECTED
                other_candidate.rejection_reason = "Another URL was approved for this organization"
                self.pending_verifications[candidate.organization].remove(other_id)
        
        logger.info(f"Approved URL {candidate.url} for {candidate.organization} by user {user_id}")
        return True
    
    def reject_url(self, candidate_id: str, reason: str, user_id: Optional[str] = None) -> bool:
        """
        Reject a URL candidate as incorrect
        
        Args:
            candidate_id: ID of candidate to reject
            reason: Reason for rejection
            user_id: User who rejected it (optional)
            
        Returns:
            True if successfully rejected
        """
        if candidate_id not in self.candidates:
            logger.error(f"Candidate {candidate_id} not found")
            return False
        
        candidate = self.candidates[candidate_id]
        candidate.status = VerificationStatus.REJECTED
        candidate.verified_at = datetime.utcnow()
        candidate.verified_by = user_id
        candidate.rejection_reason = reason
        
        # Remove from pending
        if candidate.organization in self.pending_verifications:
            if candidate_id in self.pending_verifications[candidate.organization]:
                self.pending_verifications[candidate.organization].remove(candidate_id)
        
        logger.info(f"Rejected URL {candidate.url} for {candidate.organization}: {reason}")
        return True
    
    def get_pending_verifications(self, limit: int = 50) -> List[Dict]:
        """
        Get organizations that need URL verification
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of organizations with their URL candidates
        """
        pending_orgs = []
        count = 0
        
        for org_name, candidate_ids in self.pending_verifications.items():
            if count >= limit:
                break
                
            if not candidate_ids:  # Skip empty lists
                continue
            
            candidates = []
            for candidate_id in candidate_ids:
                if candidate_id in self.candidates:
                    candidate = self.candidates[candidate_id]
                    if candidate.status == VerificationStatus.UNVERIFIED:
                        candidates.append({
                            'candidate_id': candidate.id,
                            'url': candidate.url,
                            'title': candidate.title,
                            'confidence': candidate.confidence,
                            'found_at': candidate.found_at.isoformat()
                        })
            
            if candidates:  # Only include orgs with unverified candidates
                pending_orgs.append({
                    'organization': org_name,
                    'display_name': org_name.replace('_', ' ').title(),
                    'candidates': candidates,
                    'candidate_count': len(candidates)
                })
                count += 1
        
        # Sort by confidence of best candidate
        pending_orgs.sort(key=lambda x: max(c['confidence'] for c in x['candidates']), reverse=True)
        
        return pending_orgs
    
    def get_verification_stats(self) -> Dict:
        """Get statistics about URL verification"""
        total_candidates = len(self.candidates)
        approved = len([c for c in self.candidates.values() if c.status == VerificationStatus.APPROVED])
        rejected = len([c for c in self.candidates.values() if c.status == VerificationStatus.REJECTED])
        pending = len([c for c in self.candidates.values() if c.status == VerificationStatus.UNVERIFIED])
        
        return {
            'total_candidates': total_candidates,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'verified_organizations': len(self.verified_urls),
            'pending_organizations': len([org for org, ids in self.pending_verifications.items() if ids])
        }
    
    def format_candidates_for_api(self, candidates: List[URLCandidate]) -> List[Dict]:
        """Format URL candidates for API response"""
        return [
            {
                'candidate_id': candidate.id,
                'url': candidate.url,
                'title': candidate.title,
                'confidence': candidate.confidence,
                'status': candidate.status.value,
                'found_at': candidate.found_at.isoformat()
            }
            for candidate in candidates
        ]

# Global instance - will be replaced with database-backed implementation
url_verification_manager = URLVerificationManager()