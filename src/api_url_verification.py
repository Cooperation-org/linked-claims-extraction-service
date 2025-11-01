"""
API endpoints for URL verification workflow
"""
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)

def add_url_verification_routes(app):
    """Add URL verification routes to Flask app"""
    
    @app.route('/api/url-verification/pending', methods=['GET'])
    def get_pending_verifications():
        """Get organizations that need URL verification"""
        try:
            from url_verification import url_verification_manager
            
            limit = int(request.args.get('limit', 20))
            pending_orgs = url_verification_manager.get_pending_verifications(limit=limit)
            
            return jsonify({
                'success': True,
                'pending_verifications': pending_orgs,
                'count': len(pending_orgs)
            })
            
        except Exception as e:
            logger.error(f"Error getting pending verifications: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/url-verification/approve', methods=['POST'])
    def approve_url():
        """Approve a URL candidate as correct"""
        try:
            from url_verification import url_verification_manager
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
                
            candidate_id = data.get('candidate_id')
            user_id = data.get('user_id', 'anonymous')
            
            if not candidate_id:
                return jsonify({'error': 'candidate_id is required'}), 400
            
            success = url_verification_manager.approve_url(candidate_id, user_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'URL approved successfully',
                    'candidate_id': candidate_id
                })
            else:
                return jsonify({'error': 'Failed to approve URL - candidate not found'}), 404
                
        except Exception as e:
            logger.error(f"Error approving URL: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/url-verification/reject', methods=['POST'])
    def reject_url():
        """Reject a URL candidate as incorrect"""
        try:
            from url_verification import url_verification_manager
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
                
            candidate_id = data.get('candidate_id')
            reason = data.get('reason', 'No reason provided')
            user_id = data.get('user_id', 'anonymous')
            
            if not candidate_id:
                return jsonify({'error': 'candidate_id is required'}), 400
            
            success = url_verification_manager.reject_url(candidate_id, reason, user_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'URL rejected successfully',
                    'candidate_id': candidate_id
                })
            else:
                return jsonify({'error': 'Failed to reject URL - candidate not found'}), 404
                
        except Exception as e:
            logger.error(f"Error rejecting URL: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/url-verification/stats', methods=['GET'])
    def get_verification_stats():
        """Get URL verification statistics"""
        try:
            from url_verification import url_verification_manager
            from url_resolver import get_resolution_stats
            
            verification_stats = url_verification_manager.get_verification_stats()
            resolution_stats = get_resolution_stats()
            
            return jsonify({
                'success': True,
                'verification': verification_stats,
                'resolution': resolution_stats
            })
            
        except Exception as e:
            logger.error(f"Error getting verification stats: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/url-verification/suggest', methods=['POST'])
    def suggest_url():
        """Allow users to suggest a URL for an organization"""
        try:
            from url_verification import url_verification_manager
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
                
            organization = data.get('organization')
            suggested_url = data.get('url')
            user_id = data.get('user_id', 'anonymous')
            
            if not organization or not suggested_url:
                return jsonify({'error': 'organization and url are required'}), 400
            
            # Validate URL format
            from url_resolver import validate_url
            if not validate_url(suggested_url):
                return jsonify({'error': 'Invalid URL format'}), 400
            
            # Add as high-confidence candidate
            candidates = [(f"User suggested by {user_id}", suggested_url, 0.95)]
            url_candidates = url_verification_manager.add_url_candidates(organization, candidates)
            
            return jsonify({
                'success': True,
                'message': 'URL suggestion added for verification',
                'candidate_id': url_candidates[0].id if url_candidates else None,
                'organization': organization
            })
            
        except Exception as e:
            logger.error(f"Error adding URL suggestion: {e}")
            return jsonify({'error': str(e)}), 500
    
    logger.info("URL verification API routes added")