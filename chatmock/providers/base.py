from __future__ import annotations

import json
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests
from requests import Response

from ..config import CHATGPT_RESPONSES_URL
from ..session import ensure_session_id
from ..upstream import normalize_model_name
from ..utils import get_effective_chatgpt_auth, convert_chat_messages_to_responses_input

logger = logging.getLogger(__name__)

class Provider(ABC):
    @abstractmethod
    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        """Send message to provider, return upstream response and error response."""
        pass

    @abstractmethod
    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Get non-streaming response from provider."""
        pass

    def _retry_request(self, make_request, max_retries: int = 6) -> Tuple[Optional[Response], Optional[Response]]:
        delay = 0.5
        for attempt in range(max_retries):
            upstream, error_resp = make_request()
            if error_resp is not None:
                return upstream, error_resp
            if upstream is None or upstream.status_code != 429:
                if upstream is None:
                    logger.error("Upstream request failed with no response")
                return upstream, None
            # 429 retry
            ra = upstream.headers.get("retry-after")
            if ra:
                try:
                    sleep_for = float(ra)
                except ValueError:
                    sleep_for = 2.0
            else:
                sleep_for = min(15.0, delay)
                delay *= 2
            sleep_for += random.uniform(0.1, 0.4)
            time.sleep(sleep_for)
        return upstream, None