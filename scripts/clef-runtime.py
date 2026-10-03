"""Optional local Clef classifier, isolated from the fast blackjack engine.

Run with the separate CUDA environment created by install-clef.ps1.
Only the pinned official model head is imported. No external API key is needed.
"""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
import time

REVISION = '17f0b0ad64efb65d273590632833508766b2aae6'
HEAD_HASH = '0e304cf7c6500e8bb59bef7e2afd2c6373f82596dfb3b57d1aa93c175e2dc3a3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--port', type=int, default=9051)
    parser.add_argument('--test-image', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--serve-after-test', action='store_true', help='Keep the tested model available without loading it twice.')
    args = parser.parse_args()
    root = args.model.resolve()
    head = root / 'joint_schema_model.py'
    if hashlib.sha256(head.read_bytes()).hexdigest() != HEAD_HASH:
        raise ValueError('Official model head differs from the audited pinned revision.')
    import os
    os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")
    import torch
    torch.set_num_threads(4)
    from transformers import BitsAndBytesConfig, Qwen3_5ForConditionalGeneration, AutoProcessor
    if not torch.cuda.is_available():
        raise RuntimeError('This optional runtime needs a working NVIDIA CUDA installation.')
    sys.path.insert(0, str(root))
    from joint_schema_model import ClefModel, JointSchemaHead, systemone
    from safetensors.torch import load_file
    from types import SimpleNamespace
    from PIL import Image
    # Validate all processor dependencies before the expensive model load.
    processor = AutoProcessor.from_pretrained(str(root), local_files_only=True)
    print('Processor ready; loading the pinned quantized backbone.', flush=True)
    started = time.perf_counter()
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16,
        llm_int8_enable_fp32_cpu_offload=True)
    from clef_vocabulary import VocabularyRows, DiskEmbedding, DiskOutput
    input_rows = VocabularyRows(root, 'model.language_model.embed_tokens.weight')
    output_rows = VocabularyRows(root, 'lm_head.weight')

    class SmallMemoryBackbone(Qwen3_5ForConditionalGeneration):
        def __init__(self, config):
            super().__init__(config)
            self.model.language_model.embed_tokens = DiskEmbedding(input_rows)
            self.lm_head = DiskOutput(output_rows)

    # The official head needs only selected vocabulary rows. Read those unchanged
    # rows from the checkpoint instead of loading both full matrices into RAM.
    backbone = SmallMemoryBackbone.from_pretrained(str(root), dtype=torch.float16,
        device_map='cuda', quantization_config=quantization, local_files_only=True,
        attn_implementation='eager')
    backbone.config.use_cache = False
    head = JointSchemaHead(**json.loads((root / 'joint_head_config.json').read_text()))
    head.load_state_dict(load_file(str(root / 'joint_head.safetensors')), strict=True)
    model = ClefModel(backbone, head.to(device='cuda', dtype=torch.float16)).eval()
    load_seconds = time.perf_counter() - started
    lock = threading.Lock()

    def classify(image=None):
        request = {'model': 'clef-flash', 'state': {'purpose': 'Classify the visible scene only. Do not estimate game outcomes.'},
            'questions': {'scene': {'type': 'choice', 'instructions': 'What kind of scene is visible?',
                'criteria': {'blackjack': 'A blackjack table with player and dealer cards.',
                             'poker': 'A poker table with a shared community board.',
                             'other': 'No readable blackjack or poker table.'}}}}
        if image is not None:
            image.thumbnail((512, 512))
            request['images'] = [image]
        else:
            request['state'] = {'scene': 'An empty office desktop with no card table.'}
        with lock:
            started = time.perf_counter()
            result = systemone(model, processor, request, max_length=4096)
            result['latency_ms'] = (time.perf_counter() - started) * 1000
        result['scope'] = 'Experimental scene classification. Confidence is not a blackjack outcome probability.'
        return result

    health = {'status': 'ready', 'model': 'Cloudflare/clef-flash', 'revision': REVISION,
        'device': torch.cuda.get_device_name(0), 'quantization': 'NF4 / float16; unchanged vocabulary rows read from checkpoint on demand',
        'load_seconds': load_seconds, 'allocated_vram_mib': torch.cuda.memory_allocated() / 1048576,
        'scope': 'Optional experimental classifier; core card recognition and mathematics are independent.'}
    if args.test_image:
        print('Classifying the controlled text case.', flush=True)
        text_result = classify()
        print('Classifying the controlled image case.', flush=True)
        evidence = {'runtime': health, 'text': text_result, 'image': classify(Image.open(args.test_image).convert('RGB')),
                    'peak_allocated_vram_mib': torch.cuda.max_memory_allocated() / 1048576}
        print(json.dumps(evidence, indent=2), flush=True)
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        if not args.serve_after_test:
            return
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import uvicorn
    app = FastAPI(docs_url=None, redoc_url=None)

    class ImageBody(BaseModel):
        image_base64: str = Field(max_length=12_000_000)

    @app.get('/health')
    def status():
        return health

    @app.post('/classify')
    def inspect(body: ImageBody):
        try:
            raw = base64.b64decode(body.image_base64, validate=True)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Image exceeds 8 MiB.')
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 5_000_000:
                    raise ValueError('Image exceeds five megapixels.')
                return classify(image.convert('RGB'))
        except (ValueError, OSError, Image.DecompressionBombError) as error:
            raise HTTPException(422, str(error)) from error

    print(json.dumps(health), flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
