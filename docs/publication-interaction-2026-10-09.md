# Publisher mouse and keyboard repair — October 9, 2026

Baseline: `b6093050dafe9a8d5b2ad4d958fdae742bc06624`.

## Reproduced defects

The original mouse-down handler prevents text boxes from receiving an editable caret. Real double-click and keyboard input leave the text unchanged. Template assignments replace the original resize span, leaving selected template text without a working handle. The old selection border can also become part of saved design data.

## Changes

Only `admin/publication-designer.php` changes at runtime. Double-click or Enter/F2 enters text editing; Escape returns to moving the object. While editing, native caret placement and selection are not intercepted. The resize handle is outside the editable text operation and is restored afterwards; delegated mouse events use the current handle. Arrow keys nudge selected objects (Shift moves ten pixels). Clipboard insertion is plain text and external HTML/image drops into text are blocked. Selection decoration is not serialized as a design border.

The exact seven replacements are pinned in `tests/fixtures/publication-interaction-reviewed.json`. Existing preservation proofs reconstruct the reviewed baseline before applying this delta. No public hero, image, shared-storage endpoint, mail module, credential, timecard, private record, or `data/content.json` changes are permitted by this slice. PR #110 is separate and unchanged.

## Verification

`python3 tests/publication-interaction-browser.py` uses real mouse, keyboard and caret behavior against the actual editor and PHP validators, with synthetic project/media endpoints. It covers typing, all six templates, move/resize for text/images/shapes, save/reopen, page duplication, literal paste, and print preparation. Pinned previous source must fail independently for typing and missing handles. Existing text round-trip, fidelity, save-race and PHP contracts are retained.

This is not production acceptance. The local execution environment blocks localhost browser navigation, so authenticated PHP/browser integration is evaluated by the repository's existing CI suite. No production requests, real uploads, outgoing mail, merge, or deployment are performed by these tests.
