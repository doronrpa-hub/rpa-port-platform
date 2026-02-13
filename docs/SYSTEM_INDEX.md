# RCB System Index
## Files uploaded to chat but NOT in repo
## Last updated: Session 19 (February 13, 2026)

These files were discussed/uploaded during sessions but never committed to the repository.
They contain critical functionality that exists ONLY in chat uploads and could be lost.

**ACTION REQUIRED:** These must be committed to the repo ASAP (Task 1 in SESSION19_BACKUP.md).

---

## Files to Commit

| File | Lines | Description | Session | Target Path |
|------|-------|-------------|---------|-------------|
| `tracker_email.py` | 316 | TaskYam HTML progress bar emails per container | Session 18 | `functions/lib/tracker_email.py` |
| `fix_silent_classify.py` | 67 | CC emails silently classified, stores in rcb_silent_classifications | Session 18 | `functions/lib/fix_silent_classify.py` |
| `fix_tracker_crash.py` | 16 | Patches None bug in _derive_current_step | Session 18 | `functions/lib/fix_tracker_crash.py` |
| `patch_tracker_v2.py` | 300 | Tracker v2 patch with improved phase detection | Session 18 | `functions/lib/patch_tracker_v2.py` |
| `pupil_v05_final.py` | ??? | Original pupil -- devil's advocate, CC email learning | Pre-Session 17 | `functions/lib/pupil_v05_final.py` |

---

## Notes

- **tracker_email.py**: Builds TaskYam-style HTML progress bar emails showing import/export steps per shipment. Ready to wire once tracker is stable.
- **fix_silent_classify.py**: Would enable RCB to learn from emails where it's CC'd on commercial correspondence. No email sent back, just silent extraction and learning. High value for building supplier/product knowledge.
- **fix_tracker_crash.py**: Fixes None bug in `_derive_current_step()` when import_proc or export_proc is None. 16 lines, simple patch.
- **patch_tracker_v2.py**: Improvements to shipment phase tracking. Current tracker (v1) is already wired into the pipeline and working.
- **pupil_v05_final.py**: Contains the original "pupil" logic that challenges classifications. Could serve as the "devil's advocate" in the roadmap's cross-check feature (Claude vs Gemini vs GPT consensus).

---

## Transcripts (available at /mnt/user-data/uploads/ or /mnt/transcripts/)

16 transcript files + journal, totaling 3.2MB (~500,000+ words).
These are the source of truth for all plans, promises, and decisions across sessions.
See SESSION19_BACKUP.md for the full transcript inventory.
