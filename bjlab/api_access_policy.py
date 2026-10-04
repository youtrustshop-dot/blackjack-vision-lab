"""Inference authorization lives in the existing matrix, not in key presence."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

MATRIX = Path(__file__).resolve().parents[1]/'docs/VISION_EXPERIMENTS.json'


def require_inference_authorization(expected_epoch=None):
    try:
        policy = json.loads(MATRIX.read_text(encoding='utf-8'))['api_access_policy']
    except (OSError, ValueError, KeyError, TypeError):
        raise PermissionError('blocked_api_policy_unavailable') from None
    if not isinstance(policy, dict) or policy.get('inference_authorized') is not True:
        raise PermissionError('blocked_zero_api_budget')
    try:
        limit = Decimal(str(policy['max_usd']))
        requests = policy['max_requests']
        if not limit.is_finite() or limit <= 0 or type(requests) is not int or requests <= 0:
            raise ValueError('No positive explicit allowance.')
    except (InvalidOperation, ValueError, KeyError, TypeError):
        raise PermissionError('blocked_zero_api_budget') from None
    epoch = policy.get('authorization_epoch')
    if not isinstance(epoch, str) or not epoch or (expected_epoch is not None and expected_epoch != epoch):
        raise PermissionError('blocked_stale_spending_authorization')
    return epoch
