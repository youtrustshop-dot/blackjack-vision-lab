"""Receipts for pinned MGP PDF/license and CardSharp architectural source inspection."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.references import _pin, _checkout_provenance, _sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=('mgp', 'cardsharp'))
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--work-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    repository = 'Neurobaby/MGPs-BJ-CA' if args.engine == 'mgp' else 'mmichie/cardsharp'
    pin = _pin(repository)
    checkout = Path(args.checkout).resolve()
    provenance = _checkout_provenance(checkout, pin)
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': 1, 'status': 'source_inspected', 'comparison_executed': False,
              'engine': args.engine, 'provenance': provenance,
              'inspected_at': datetime.now(timezone.utc).isoformat()}
    if args.engine == 'mgp':
        import pymupdf as fitz
        pdf = checkout / "BJ CA/MGP's BJ CA Help.pdf"
        document = fitz.open(pdf)
        text = '\n'.join(f'\n=== PAGE {index+1} ===\n' + page.get_text()
                         for index, page in enumerate(document))
        text_path = work / 'mgp-help.txt'
        text_path.write_text(text, encoding='utf-8')
        hits = []
        for index, page in enumerate(document):
            content = page.get_text()
            if re.search(r'example|accuracy|exact|export|command.line|s17|h17|0\.\d{3}', content, re.I):
                hits.append({'page': index+1, 'character_count': len(content),
                             'has_numbers': bool(re.search(r'[-+]?0\.\d{3}', content))})
        rendered = []
        for page_number in (2, 8, 9, 10, 12):
            image = work / f'mgp-page-{page_number}.png'
            document[page_number-1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(image)
            rendered.append({'page': page_number, 'path': str(image), 'sha256': _sha256(image)})
        result.update({'help_pdf_sha256': _sha256(pdf), 'help_pdf_pages': len(document),
                       'help_pdf_metadata': document.metadata, 'relevant_pages': hits,
                       'text_extract': str(text_path), 'rendered_pages': rendered,
                       'help_pdf_source_url': f"https://github.com/{repository}/blob/{pin['commit']}/BJ%20CA/MGP%27s%20BJ%20CA%20Help.pdf",
                       'manual_scope': [
                           {'page': 2, 'finding': 'Distinguishes total-dependent, two-card and composition-dependent continuation. Top-of-deck single-player calculations described as thought exact except BBO.'},
                           {'page': 7, 'finding': 'Real-time analysis can optionally substitute single-split estimates plus a baseline correction.'},
                           {'page': 8, 'finding': 'Three busted-bet conventions explicitly approximate; conditioning varies with hole-card/dealer-check convention.'},
                           {'page': 9, 'finding': 'Post-split CDZ-, CD-P and CD-PN attention differs from full jointly observed sequential split context.'},
                           {'page': 10, 'finding': 'N-card analysis uses existing EVs and does not recalculate them after policy changes.'}
                       ],
                       'published_numeric_goldens': [],
                       'golden_note': 'All 13 manual pages inspected: no published hand-action EV or full-game EV table suitable for a reproducible numeric golden found.',
                       'license_source_url': f"https://github.com/{repository}/blob/{pin['commit']}/LICENSE.md",
                       'license_sha256': _sha256(checkout/'LICENSE.md'),
                       'license_inspection': 'Permits redistribution and use in source and binary forms with three retention/nonendorsement conditions and disclaimer; BSD-3-Clause-style text. GitHub NOASSERTION is incomplete classification.',
                       'project_sha256': _sha256(checkout/'BJ CA/BJ CA.vbproj'),
                       'runtime': 'Visual Basic Windows Forms WinExe, .NET Framework 3.5, startup BJCAMainForm; no command-line handler found by source search.',
                       'execution_status': 'not_executed',
                       'direct_cli_status': 'unsupported: pinned project is a Windows Forms executable with no inspected command-line entrypoint; GUI/manual export remains possible, not validated here.'})
    else:
        paths = ['cardsharp/events/emitter.py', 'cardsharp/state/models.py',
                 'cardsharp/state/transitions.py', 'cardsharp/engine/base.py', 'cardsharp/api/flow.py']
        result['source_hashes'] = {name: _sha256(checkout/name) for name in paths}
        result['source_urls'] = {name: f"https://github.com/{repository}/blob/{pin['commit']}/{name}" for name in paths}
        result['patterns'] = [
            {'path': paths[0], 'symbols': ['EventEmitter.on', 'EventEmitter.once', 'EventEmitter.emit', 'EventEmitter.remove_all_listeners'], 'observed': 'Priority-sorted subscriptions; unsubscribe closures; RLock protects listener lists; recorder game/round context.'},
            {'path': paths[1], 'symbols': ['HandState', 'PlayerState', 'DealerState', 'GameState'], 'observed': 'Frozen dataclasses and explicit dealer visible-card projection; nested list members remain mutable, so immutability is shallow.'},
            {'path': paths[2], 'symbols': ['StateTransitionEngine', 'change_stage', 'resolve_hands'], 'observed': 'dataclasses.replace builds new states and publishes transitions through global EventBus. Functions have event side effects, so pure state-function claim needs qualification.'},
            {'path': paths[4], 'symbols': ['EventWaiter.wait_for', 'EventWaiter.wait_for_any'], 'observed': 'Future-based event waits with predicates, timeout handling and finally unsubscribe; engine/UI can await events rather than poll.'}
        ]
        result['execution_status'] = 'not_executed; architecture inspected only, no EV validation claim'
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
