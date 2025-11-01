"""
Trust Policy filter implementation for the RCRAG service.
"""

from typing import List, Dict, Any


def apply_trust_policy(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters a list of documents based on the trust policy.

    Trust policy criteria:
    - 'kind' must be one of ['execution_report', 'fact', 'artifact']
    - 'verified.status' must be 'accepted'

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries to filter.

    Returns:
        List[Dict[str, Any]]: List of documents that satisfy the trust policy.
    """
    allowed_kinds = {'execution_report', 'fact', 'artifact'}
    filtered_docs = []

    for doc in documents:
        kind = doc.get('kind')
        verified = doc.get('verified', {})
        status = verified.get('status')

        if kind in allowed_kinds and status == 'accepted':
            filtered_docs.append(doc)

    return filtered_docs
