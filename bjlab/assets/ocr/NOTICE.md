# Bundled OCR model

`ch_PP-OCRv4_rec_infer.onnx` is an unmodified PaddleOCR PP-OCRv4 recognition
model converted and distributed by RapidOCR. Upstream model rights belong to
Baidu and/or the respective PaddleOCR rights holders. Copyright (c) 2016
PaddlePaddle Authors. RapidOCR engineering components are copyright RapidOCR
Authors. The model is distributed under Apache License 2.0; see `LICENSE.txt`.

The exact bytes were extracted from the official PyPI
[rapidocr-onnxruntime 1.4.4 wheel](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/).
Its SHA-256 is `971d7d5f223a7a808662229df1ef69893809d8457d834e6373d3854bc1782cbf`.
The model SHA-256 is
`48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`.

Model attribution and conversion terms:
[RapidOCR](https://github.com/RapidAI/RapidOCR#license),
[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR).
The accompanying license is the upstream PaddleOCR license text. Blackjack
Vision Lab's adapter implements the documented resize, BGR normalization and
CTC decoding contract. It does not modify the weights or download models at
runtime. ONNX Runtime CPU executes the model locally.

No artwork or assets from third-party blackjack games are distributed.
