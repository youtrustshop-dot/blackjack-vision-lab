# Third-party notices

Blackjack Vision Lab distributes unmodified third-party components. Their
copyright notices and terms are retained in this directory. `inventory.json`
records versions and notice paths from the Python freezing inputs, React UI,
locked Cargo graph, CPython runtime, DejaVu font and official WebView2 SDK.
`source-archives/` retains exact unmodified upstream crate source for MPL portions
and packages whose crate omits a separate license file. Pinned upstream monorepo
notices retain their source URL and commit beside the original license text.
The Cargo inventory conservatively includes build dependencies and packages for
other platforms; listing a package does not assert it is linked into this EXE.

Python's license includes its Microsoft Distributable Code restrictions. Those
restrictions apply to the Microsoft runtime components and must be retained in
redistribution. The WebView2 Loader is covered by the accompanying Microsoft SDK
license. The separately installed WebView2 browser runtime is provided by
Microsoft under its own terms. These Microsoft components are supplied without
warranty by the authors of this application and remain subject to their
accompanying restrictions; do not remove the notices, misuse Microsoft's marks,
redistribute them for non-Microsoft platforms, or use them in malicious programs.

The Rust runtime notice includes GPL text and GCC Runtime Library Exception 3.1
for any applicable GNU runtime portions. The exception's terms govern those
portions; including its notice does not relicense this application's own code.
PyInstaller's accompanying license retains its bootloader distribution exception.
OpenCV/FFmpeg, NumPy/OpenBLAS and Pillow include their upstream bundled notices.

This collection does not replace the original terms or grant additional rights.
