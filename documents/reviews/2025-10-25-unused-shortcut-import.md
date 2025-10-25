# Review: Remove unused QtGui shortcut imports

## Summary
- Removes the unused `QKeySequence` import from `app/ui/main_window.py`.
- Keeps the required `QUndoStack` import.

## Assessment
- The diff only deletes an unused symbol, improving clarity and avoiding lint warnings.
- `QKeySequence` is not referenced anywhere in the repository, so its removal is safe.

## Testing
- Not run (import-only cleanup).

## Decision
- **Approve**
