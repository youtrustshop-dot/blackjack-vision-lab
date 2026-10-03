"""Read only requested official vocabulary rows; avoid resident 2-GiB matrices."""
import copy
import json
from pathlib import Path
import struct

import numpy as np
import torch


class VocabularyRows:
    def __init__(self, root, key, device="cuda"):
        root = Path(root)
        index = json.loads((root / "model.safetensors.index.json").read_text())
        name = index["weight_map"][key]
        if Path(name).name != name:
            raise ValueError("Vocabulary shard must be inside the model directory.")
        path = root / name
        with path.open("rb") as stream:
            header_size = struct.unpack("<Q", stream.read(8))[0]
            if header_size > 2 * 1024 * 1024:
                raise ValueError("Oversized safetensors header.")
            header = json.loads(stream.read(header_size))
        metadata = header[key]
        self.shape = tuple(metadata["shape"])
        if len(self.shape) != 2:
            raise ValueError("Expected a two-dimensional vocabulary matrix.")
        kinds = {"BF16": (np.uint16, torch.bfloat16), "F16": (np.float16, torch.float16),
                 "F32": (np.float32, torch.float32)}
        dtype, self.storage_dtype = kinds[metadata["dtype"]]
        start, end = metadata["data_offsets"]
        expected = int(np.prod(self.shape)) * np.dtype(dtype).itemsize
        if end - start != expected or 8 + header_size + end > path.stat().st_size:
            raise ValueError("Vocabulary matrix layout is invalid.")
        self.values = np.memmap(path, dtype=dtype, mode="r", offset=8 + header_size + start,
                                shape=self.shape)
        self.device = torch.device(device)
        self.dtype = torch.float16
        self.requires_grad = False

    def __deepcopy__(self, memo):
        # Read-only mapping is shared. Model inspection must not copy the full vocabulary.
        return self

    def __getitem__(self, indices):
        ids = indices.detach().to(device="cpu", dtype=torch.int64).numpy()
        if ids.size and (ids.min() < 0 or ids.max() >= self.shape[0]):
            raise ValueError("Vocabulary token is out of range.")
        rows = torch.from_numpy(np.array(self.values[ids], copy=True))
        if self.storage_dtype == torch.bfloat16:
            rows = rows.view(torch.bfloat16)
        return rows.to(device=self.device, dtype=torch.float16)


class DiskEmbedding(torch.nn.Module):
    def __init__(self, rows):
        super().__init__()
        self.weight = rows
        self.num_embeddings, self.embedding_dim = rows.shape

    def forward(self, input_ids):
        return self.weight[input_ids]


class DiskOutput(torch.nn.Module):
    def __init__(self, rows):
        super().__init__()
        self.weight = rows


def self_test():
    import tempfile
    from safetensors.torch import save_file
    checked = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for dtype in (torch.bfloat16, torch.float16, torch.float32):
            weights = torch.arange(512).reshape(32, 16).to(dtype) / 7
            save_file({"vocabulary": weights}, str(root / "rows.safetensors"))
            (root / "model.safetensors.index.json").write_text(
                json.dumps({"weight_map": {"vocabulary": "rows.safetensors"}}))
            rows = VocabularyRows(root, "vocabulary", device="cpu")
            ids = torch.tensor([[1, 2, 1], [31, 0, 16]])
            assert torch.equal(rows[ids], weights[ids].to(torch.float16))
            assert torch.equal(DiskEmbedding(rows)(ids), weights[ids].to(torch.float16))
            assert copy.deepcopy(rows) is rows
            try:
                rows[torch.tensor([32])]
            except ValueError:
                pass
            else:
                raise AssertionError("Out-of-range token accepted")
            rows.values._mmap.close()
            checked.append(str(dtype))
    print(json.dumps({"status": "pass", "selected_rows_match_checkpoint": checked,
                      "repeated_batched_tokens_checked": True, "full_matrix_not_copied": True}))


if __name__ == "__main__":
    self_test()
