"""
LinkedTrust API client for claim publishing and retrieval
Following the pattern from the talent project
"""
import os
import requests
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LinkedTrustClient:
    """Client for interacting with LinkedTrust API"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.base_url = os.getenv('LINKEDTRUST_BASE_URL', 'https://dev.linkedtrust.us')
        self.access_token = access_token
        self.refresh_token = None
        
    def set_tokens(self, access_token: str, refresh_token: str = None):
        """Set authentication tokens"""
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make authenticated request to LinkedTrust API"""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        
        # Log the request for debugging
        logger.info(f"Making {method} request to {url}")
        if data and endpoint == '/auth/login':
            # Don't log password, but log that we're attempting login
            logger.info(f"Attempting login with email: {data.get('email')}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            )
            
            # Log response status for debugging
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 401:
                # Try to get error message from response
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'Authentication failed')
                    logger.error(f"401 Authentication failed: {error_msg}")
                    raise AuthenticationError(f"401: {error_msg}")
                except:
                    logger.error(f"401 with non-JSON response: {response.text}")
                    raise AuthenticationError("Authentication token expired")
            
            if not response.ok:
                # Log the actual error for debugging
                logger.error(f"API error {response.status_code}: {response.text}")
                response.raise_for_status()
            
            if response.text:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LinkedTrust API request failed: {e}")
            raise
    
    def authenticate(self, email: str, password: str) -> Dict:
        """
        Authenticate with LinkedTrust backend
        Returns user info and tokens
        """
        try:
            response = self._make_request(
                'POST',
                '/auth/login',
                data={
                    'email': email,
                    'password': password
                }
            )
            
            if response.get('accessToken'):
                self.access_token = response['accessToken']
                self.refresh_token = response.get('refreshToken')
            
            return response
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def oauth_callback(self, provider: str, code: str) -> Dict:
        """
        Handle OAuth callback from provider (Google, GitHub, etc)
        """
        try:
            response = self._make_request(
                'POST',
                f'/auth/{provider}',
                data={'code': code}
            )
            
            if response.get('accessToken'):
                self.access_token = response['accessToken']
                self.refresh_token = response.get('refreshToken')
            
            return response
            
        except Exception as e:
            logger.error(f"OAuth callback failed: {e}")
            raise
    
    def create_claim(self, claim_data: Dict) -> Dict:
        """
        Create a new claim on LinkedTrust
        
        Args:
            claim_data: Dictionary containing claim fields
                - subject (required): URI of the subject
                - statement (required): The claim statement
                - object (optional): URI of the object
                - sourceURI: Source document URL
                - effectiveDate: When the claim is effective
                - howKnown: How the claim was observed
                - confidence: Confidence score
                - etc.
        
        Returns:
            Response from LinkedTrust API including claim URL
        """
        if not self.access_token:
            raise AuthenticationError("Authentication required to create claims")
        
        # Ensure required fields
        if 'subject' not in claim_data or 'statement' not in claim_data:
            raise ValueError("Claims require 'subject' and 'statement' fields")
        
        # Add issuer info
        claim_data['issuerId'] = 'https://extract.linkedtrust.us'
        claim_data['issuerIdType'] = 'URL'
        
        try:
            response = self._make_request(
                'POST',
                '/api/claims',
                data=claim_data
            )
            
            return {
                'success': True,
                'data': response
            }
            
        except Exception as e:
            logger.error(f"Failed to create claim: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_claims(self, filters: Dict = None) -> List[Dict]:
        """
        Retrieve claims with optional filters
        
        Args:
            filters: Dictionary of filters
                - subject: Filter by subject URI
                - issuer_id: Filter by issuer
                - sourceURI: Filter by source
                - page: Page number
                - limit: Results per page
        
        Returns:
            List of claims
        """
        try:
            response = self._make_request(
                'GET',
                '/api/claim',
                params=filters or {}
            )
            
            return response.get('claims', [])
            
        except Exception as e:
            logger.error(f"Failed to retrieve claims: {e}")
            return []
    
    def get_claim_by_url(self, claim_url: str) -> Optional[Dict]:
        """
        Retrieve a specific claim by its URL
        """
        try:
            # Extract claim ID from URL if needed
            claim_id = claim_url.split('/')[-1] if '/' in claim_url else claim_url
            
            response = self._make_request(
                'GET',
                f'/api/claim/{claim_id}'
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to retrieve claim {claim_url}: {e}")
            return None
    
    def get_validations_for_claim(self, claim_url: str) -> List[Dict]:
        """
        Get validation claims for a specific claim
        
        Args:
            claim_url: The URL of the claim to get validations for
        
        Returns:
            List of validation claims
        """
        try:
            # Query for claims where the object is this claim URL
            response = self._make_request(
                'GET',
                '/api/claim',
                params={
                    'object': claim_url,
                    'limit': 100
                }
            )
            
            return response.get('claims', [])
            
        except Exception as e:
            logger.error(f"Failed to retrieve validations for {claim_url}: {e}")
            return []
    
    def graph_query(self, query: Dict) -> Dict:
        """
        Execute a graph query on LinkedTrust
        
        Args:
            query: Graph query parameters
        
        Returns:
            Graph query results
        """
        try:
            response = self._make_request(
                'POST',
                '/api/graph',
                data=query
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return {}


class AuthenticationError(Exception):
    """Raised when authentication is required or fails"""
    pass