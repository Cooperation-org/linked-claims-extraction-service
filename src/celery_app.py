"""
Celery configuration for background task processing
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

def create_celery_app(app=None):
    """Create and configure Celery app"""
    
    # Redis configuration
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', '6379')
    redis_db = os.getenv('REDIS_DB', '0')
    redis_password = os.getenv('REDIS_PASSWORD', '')
    
    if redis_password:
        redis_url = f'redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}'
    else:
        redis_url = f'redis://{redis_host}:{redis_port}/{redis_db}'
    
    celery = Celery(
        'linked_claims_extraction',
        broker=redis_url,
        backend=redis_url,
        include=['tasks']  # Include our tasks module
    )
    
    # Celery configuration
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes max per task
        task_soft_time_limit=25 * 60,  # Soft limit at 25 minutes
        worker_prefetch_multiplier=1,  # Process one task at a time per worker
        worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
        result_expires=3600,  # Results expire after 1 hour
    )
    
    if app:
        # Initialize with Flask app context
        celery.conf.update(app.config)
        
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery

# Create the celery app instance
celery_app = create_celery_app()