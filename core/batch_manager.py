"""
Batch Manager for Asynchronous Image Generation.

Manages batch jobs for Google Gemini API with 50% discount.
Batch jobs process asynchronously with results typically available within 24 hours.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BatchJobState(Enum):
    """Batch job states."""
    PENDING = "JOB_STATE_PENDING"
    RUNNING = "JOB_STATE_RUNNING"
    SUCCEEDED = "JOB_STATE_SUCCEEDED"
    FAILED = "JOB_STATE_FAILED"
    CANCELLED = "JOB_STATE_CANCELLED"
    EXPIRED = "JOB_STATE_EXPIRED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_api_state(cls, state_name: str) -> 'BatchJobState':
        """Convert API state name to enum."""
        for member in cls:
            if member.value == state_name:
                return member
        return cls.UNKNOWN


@dataclass
class BatchRequest:
    """A single request in a batch job."""
    key: str  # Unique identifier for this request
    prompt: str
    model: str
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    output_quality: Optional[str] = None  # 1k, 2k, 4k for NBP

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSONL-compatible dictionary."""
        # Build content structure
        contents = [{
            'parts': [{'text': self.prompt}],
            'role': 'user'
        }]

        # Build config with image settings
        config = {
            'response_modalities': ['IMAGE']
        }

        # Add image config if aspect ratio specified
        if self.aspect_ratio:
            config['image_config'] = {'aspect_ratio': self.aspect_ratio}

        return {
            'key': self.key,
            'request': {
                'contents': contents,
                'config': config
            }
        }


@dataclass
class BatchJob:
    """Represents a batch job with multiple image generation requests."""
    job_id: str
    name: str  # API name like "batches/abc123"
    display_name: str
    model: str
    state: BatchJobState
    created_at: datetime
    requests: List[BatchRequest] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)  # key -> result
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        """Check if job is in a terminal state."""
        return self.state in (
            BatchJobState.SUCCEEDED,
            BatchJobState.FAILED,
            BatchJobState.CANCELLED,
            BatchJobState.EXPIRED
        )

    @property
    def request_count(self) -> int:
        """Get number of requests in this job."""
        return len(self.requests)

    @property
    def completed_count(self) -> int:
        """Get number of completed requests."""
        return len(self.results)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job metadata."""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'display_name': self.display_name,
            'model': self.model,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'request_count': self.request_count,
            'completed_count': self.completed_count,
            'error': self.error,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class BatchManager:
    """
    Manager for batch image generation jobs.

    Uses Google Gemini Batch API for 50% discount on async processing.
    """

    COMPLETED_STATES = {
        'JOB_STATE_SUCCEEDED',
        'JOB_STATE_FAILED',
        'JOB_STATE_CANCELLED',
        'JOB_STATE_EXPIRED'
    }

    def __init__(self, client=None):
        """
        Initialize batch manager.

        Args:
            client: Google GenAI client (optional, will be created if needed)
        """
        self.client = client
        self._jobs: Dict[str, BatchJob] = {}

    def set_client(self, client):
        """Set the Google GenAI client."""
        self.client = client

    def create_batch_job(self, requests: List[BatchRequest], model: str,
                         display_name: str = None) -> BatchJob:
        """
        Create a new batch job from a list of requests.

        Args:
            requests: List of BatchRequest objects
            model: Model ID to use for all requests
            display_name: Optional human-readable name for the job

        Returns:
            BatchJob object with job details

        Raises:
            ValueError: If client not initialized or requests empty
        """
        if not self.client:
            raise ValueError("Client not initialized. Call set_client() first.")

        if not requests:
            raise ValueError("No requests provided for batch job")

        # Generate display name if not provided
        if not display_name:
            display_name = f"ImageAI-Batch-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Creating batch job '{display_name}' with {len(requests)} requests")

        # Convert requests to inline format
        inline_requests = [req.to_dict() for req in requests]

        try:
            # Create batch job via API
            api_job = self.client.batches.create(
                model=model,
                src=inline_requests,
                config={
                    'display_name': display_name,
                },
            )

            # Create our BatchJob wrapper
            job = BatchJob(
                job_id=api_job.name.split('/')[-1] if '/' in api_job.name else api_job.name,
                name=api_job.name,
                display_name=display_name,
                model=model,
                state=BatchJobState.from_api_state(api_job.state.name),
                created_at=datetime.now(),
                requests=requests
            )

            self._jobs[job.job_id] = job
            logger.info(f"Created batch job: {job.name} (state: {job.state.value})")

            return job

        except Exception as e:
            logger.error(f"Failed to create batch job: {e}", exc_info=True)
            raise

    def create_batch_job_from_file(self, jsonl_path: Path, model: str,
                                   display_name: str = None) -> BatchJob:
        """
        Create a batch job from a JSONL file.

        Args:
            jsonl_path: Path to JSONL file with requests
            model: Model ID to use
            display_name: Optional human-readable name

        Returns:
            BatchJob object
        """
        if not self.client:
            raise ValueError("Client not initialized")

        from google.genai import types

        # Generate display name if not provided
        if not display_name:
            display_name = f"ImageAI-Batch-{jsonl_path.stem}"

        logger.info(f"Uploading batch file: {jsonl_path}")

        # Upload the JSONL file
        uploaded_file = self.client.files.upload(
            file=str(jsonl_path),
            config=types.UploadFileConfig(
                display_name=display_name,
                mime_type='application/jsonl'
            )
        )

        logger.info(f"Uploaded file: {uploaded_file.name}")

        # Create batch job from uploaded file
        api_job = self.client.batches.create(
            model=model,
            src=uploaded_file.name,
            config={
                'display_name': display_name,
            },
        )

        # Read requests from file for tracking
        requests = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                # Extract prompt from request
                prompt = ""
                if 'request' in data and 'contents' in data['request']:
                    for content in data['request']['contents']:
                        if 'parts' in content:
                            for part in content['parts']:
                                if 'text' in part:
                                    prompt = part['text']
                                    break
                requests.append(BatchRequest(
                    key=data.get('key', f"req_{len(requests)}"),
                    prompt=prompt,
                    model=model
                ))

        job = BatchJob(
            job_id=api_job.name.split('/')[-1] if '/' in api_job.name else api_job.name,
            name=api_job.name,
            display_name=display_name,
            model=model,
            state=BatchJobState.from_api_state(api_job.state.name),
            created_at=datetime.now(),
            requests=requests
        )

        self._jobs[job.job_id] = job
        logger.info(f"Created batch job from file: {job.name}")

        return job

    def get_job_status(self, job_id: str) -> BatchJob:
        """
        Get current status of a batch job.

        Args:
            job_id: Job ID or name

        Returns:
            Updated BatchJob object
        """
        if not self.client:
            raise ValueError("Client not initialized")

        # Get local job if exists
        job = self._jobs.get(job_id)
        job_name = job.name if job else job_id

        # Fetch from API
        api_job = self.client.batches.get(name=job_name)

        if job:
            job.state = BatchJobState.from_api_state(api_job.state.name)
            if job.is_complete and not job.completed_at:
                job.completed_at = datetime.now()
        else:
            # Create new job object from API response
            job = BatchJob(
                job_id=api_job.name.split('/')[-1] if '/' in api_job.name else api_job.name,
                name=api_job.name,
                display_name=getattr(api_job, 'display_name', api_job.name),
                model=getattr(api_job, 'model', 'unknown'),
                state=BatchJobState.from_api_state(api_job.state.name),
                created_at=datetime.now()
            )
            self._jobs[job.job_id] = job

        logger.info(f"Job {job_id} status: {job.state.value}")
        return job

    def get_job_results(self, job_id: str) -> Tuple[List[bytes], List[str]]:
        """
        Get results from a completed batch job.

        Args:
            job_id: Job ID

        Returns:
            Tuple of (image_bytes_list, error_messages)
        """
        if not self.client:
            raise ValueError("Client not initialized")

        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Refresh status
        api_job = self.client.batches.get(name=job.name)
        job.state = BatchJobState.from_api_state(api_job.state.name)

        if not job.is_complete:
            raise ValueError(f"Job {job_id} is not complete (state: {job.state.value})")

        images = []
        errors = []

        if job.state == BatchJobState.SUCCEEDED:
            # Check for file-based results
            if hasattr(api_job, 'dest') and api_job.dest:
                if hasattr(api_job.dest, 'file_name') and api_job.dest.file_name:
                    # Download result file
                    result_file_name = api_job.dest.file_name
                    logger.info(f"Downloading results from file: {result_file_name}")

                    file_content = self.client.files.download(file=result_file_name)
                    content_str = file_content.decode('utf-8')

                    # Parse JSONL results
                    for line in content_str.strip().split('\n'):
                        if line:
                            result = json.loads(line)
                            self._process_result(result, images, errors, job)

                elif hasattr(api_job.dest, 'inlined_responses') and api_job.dest.inlined_responses:
                    # Process inline results
                    for response in api_job.dest.inlined_responses:
                        if hasattr(response, 'response') and response.response:
                            self._process_inline_response(response, images, errors, job)
                        elif hasattr(response, 'error') and response.error:
                            errors.append(str(response.error))

        elif job.state == BatchJobState.FAILED:
            job.error = "Batch job failed"
            errors.append(job.error)

        elif job.state == BatchJobState.CANCELLED:
            job.error = "Batch job was cancelled"
            errors.append(job.error)

        elif job.state == BatchJobState.EXPIRED:
            job.error = "Batch job expired (exceeded 24 hour limit)"
            errors.append(job.error)

        logger.info(f"Retrieved {len(images)} images, {len(errors)} errors from job {job_id}")
        return images, errors

    def _process_result(self, result: Dict, images: List[bytes], errors: List[str], job: BatchJob):
        """Process a single result from the batch job."""
        key = result.get('key', 'unknown')

        if 'response' in result:
            response = result['response']
            # Extract image from response
            if 'candidates' in response:
                for candidate in response['candidates']:
                    if 'content' in candidate and 'parts' in candidate['content']:
                        for part in candidate['content']['parts']:
                            if 'inline_data' in part:
                                import base64
                                image_data = part['inline_data'].get('data', '')
                                if image_data:
                                    images.append(base64.b64decode(image_data))
                                    job.results[key] = {'status': 'success'}

        if 'error' in result:
            errors.append(f"Request {key}: {result['error']}")
            job.results[key] = {'status': 'error', 'error': result['error']}

    def _process_inline_response(self, response, images: List[bytes], errors: List[str], job: BatchJob):
        """Process an inline response from the batch job."""
        if hasattr(response.response, 'candidates'):
            for candidate in response.response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            data = getattr(part.inline_data, 'data', None)
                            if data:
                                if isinstance(data, str):
                                    import base64
                                    images.append(base64.b64decode(data))
                                else:
                                    images.append(bytes(data))

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running batch job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled successfully
        """
        if not self.client:
            raise ValueError("Client not initialized")

        job = self._jobs.get(job_id)
        job_name = job.name if job else job_id

        try:
            self.client.batches.cancel(name=job_name)
            if job:
                job.state = BatchJobState.CANCELLED
                job.completed_at = datetime.now()
            logger.info(f"Cancelled batch job: {job_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def list_jobs(self) -> List[BatchJob]:
        """Get all tracked batch jobs."""
        return list(self._jobs.values())

    def save_requests_to_jsonl(self, requests: List[BatchRequest], output_path: Path):
        """
        Save batch requests to a JSONL file.

        Args:
            requests: List of BatchRequest objects
            output_path: Path to save JSONL file
        """
        with open(output_path, 'w') as f:
            for req in requests:
                f.write(json.dumps(req.to_dict()) + '\n')

        logger.info(f"Saved {len(requests)} requests to {output_path}")


# Global batch manager instance
_batch_manager: Optional[BatchManager] = None


def get_batch_manager() -> BatchManager:
    """Get the global batch manager instance."""
    global _batch_manager
    if _batch_manager is None:
        _batch_manager = BatchManager()
    return _batch_manager
