"""Opt-in research D reader under the existing absolute capture deadline.

No production wiring, hidden phase, output remapping, retries or budget reset.
The caller supplies the existing scoped transport/authorization; this adapter
only builds the byte-checked available-image request already tested in PR25.
"""
from .available_image_views import bind_available_numeric_views
from .paired_deadline_reader import CaptureDeadlineReader


class AvailableViewDeadlineReader(CaptureDeadlineReader):
    def __init__(self, config, budget, hashes, *, transport):
        super().__init__(config,budget,hashes,provider='gemini',transport=transport,
            name='gemini-json-available-images-v1')
        self.payload_reader.gemini_output='json-mode'

    def payload(self, frame):
        payload=super().payload(frame)
        payload['generationConfig']['thinkingConfig']={
            'thinkingLevel':'MINIMAL','includeThoughts':False}
        return bind_available_numeric_views(payload,frame,mode='json-mode')
