# RCB System Index
## Files uploaded to chat but NOT in repo
## Last updated: Session 19 (February 13, 2026)

These files were discussed/uploaded during sessions but never committed to the repository.
They may contain useful code that should be reviewed before deploying.

---

| File | Description | Session | Status |
|------|-------------|---------|--------|
| `fix_silent_classify.py` | CC emails silently classified without sending response. Adds learning from CC'd emails where RCB is not the primary recipient. | Session 18 | NOT DEPLOYED -- needs review |
| `patch_tracker_v2.py` | Tracker v2 patch with improved phase detection and document mapping. | Session 18 | NOT REVIEWED |
| `pupil_v05_final.py` | Original pupil code -- devil's advocate classification checker. Could be wired as a second opinion after Agent 2. | Pre-session 18 | NOT WIRED -- roadmap item |

---

## Notes

- **fix_silent_classify.py**: Would enable RCB to learn from emails where it's CC'd on commercial correspondence. No email sent back, just silent extraction and learning. High value for building supplier/product knowledge.
- **patch_tracker_v2.py**: Improvements to shipment phase tracking. Current tracker (v1) is already wired into the pipeline and working.
- **pupil_v05_final.py**: Contains the original "pupil" logic that challenges classifications. Could serve as the "devil's advocate" in the roadmap's cross-check feature (Claude vs Gemini vs GPT consensus).
