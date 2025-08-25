# Linked Claims Extraction Service - Purpose & Architecture

## Core Purpose

The key purpose of this service is to:

1. **Extract verifiable claims from PDF documents** and send them to the decentralized flow of claims managed by live.linkedtrust.us
2. **Guide users to request verifications** from those directly impacted by the claims

## Key Principles

This service follows the Linked Claims principles as defined by:
- Identity Foundation Labs: https://identity.foundation/labs-linkedclaims/
- LinkedTrust API Documentation: https://live.linkedtrust.us/api/docs/

## Architecture Philosophy

### Data Storage Strategy

**IMPORTANT**: This service uses a hybrid storage approach:

1. **Local Database (PostgreSQL)**: Used ONLY for:
   - Tracking uploaded PDF files per user (with OAuth in future)
   - Storing DRAFT claims before user approval
   - Processing status and metadata
   - User session management

2. **Decentralized Storage (live.linkedtrust.us)**: Used for:
   - ALL signed/published claims
   - ALL validation requests and responses
   - The authoritative source of truth for claims and validations
   - Graph queries to retrieve claims and their validation chains

**Critical Note**: Once claims are signed and published, they are NO LONGER stored locally. All queries for published claims and validations MUST go through the live.linkedtrust.us API using graph queries. See the talent project for an example.

### Processing Flow

1. **Upload Stage**: Immediate file storage with user feedback
2. **Processing Stage**: Background extraction using Celery workers
3. **Draft Stage**: Local storage of extracted claims pending user review
4. **Publishing Stage**: Frontend prompts user for LinkedTrust credentials and publishes directly under user's account
5. **Validation Stage**: Guide users to request validations via LinkedTrust API

### Publishing Architecture (Updated)

**Direct Frontend Publishing Approach:**
- Users authenticate directly with LinkedTrust (no service-side credentials)
- Claims published under user's own LinkedTrust identity
- Frontend handles authentication and publishing via LinkedTrust API
- Service never stores or uses LinkedTrust credentials

### Technology Stack

- **Web Framework**: Flask
- **Background Processing**: Celery + Redis
- **Database**: PostgreSQL (draft claims and metadata only)
- **PDF Processing**: PyMuPDF
- **Claim Extraction**: Claude API via linked-claims-extractor package
- **Decentralized Backend**: live.linkedtrust.us API

note that ClaimExtractor imports from the pypi linked-claim-extractor package, this is also our code and can be edited locally and published to update, is in a different repo.

## Development Guidelines

When working on this codebase, remember:

1. Never store published claims locally - always query LinkedTrust
2. The local database is for tracking documents, draft or staged claims for possible publication, and may be a VIEW of the real state that can update
3. All validation flows must go through the decentralized backend
4. **NEVER prompt users for credentials they already provided during login** - use stored OAuth tokens!
5. Prioritize user feedback and transparency in the extraction process

⚠️ **READ BEFORE CODING:** See [COMMON_MISTAKES.md](COMMON_MISTAKES.md) to avoid stupid mistakes!
