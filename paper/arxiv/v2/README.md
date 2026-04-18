# arXiv v2 — pending upload

**Source manuscript:** `../../manuscripts/v2.23/`
**Send-ready docx:** `../../manuscripts/v2.23/camera_ready_fully_dynamic.docx` (also frozen at `../../correspondence/khaled/2026-04-17_sent_v2.23/attachments/PAPER_v2.23_FINAL-Dynamic.docx`)
**Status:** awaiting Khaled to upload on arXiv ("Submit a new version" flow)

## Comments field text (as planned)

> v2: added Zenodo artifact DOI (10.5281/zenodo.19625392); minor abstract revision to reference FIPS 203/204 explicitly; resolved artifact-repository URL placeholder in the Code and Data Availability section. No changes to the methodology, results, or references.

(Note: the cited DOI `10.5281/zenodo.19625392` belongs to **Paper 1** (Structural Dependency Analysis) — that's intentional. The cross-reference to Paper 1's Zenodo archive is added here. Paper 2's own Zenodo concept DOI is `10.5281/zenodo.19508454`.)

## Once Khaled uploads

1. Copy `manuscripts/v2.23/camera_ready_fully_dynamic.docx` → `arxiv/v2/manuscript.docx` (rename to drop the long name)
2. `cp ../../manuscripts/v2.23/source.md source.md`
3. Write `arxiv_metadata.md` with the exact title, full abstract used in the v2 metadata fields, and Comments field text actually submitted
4. Write `CHANGES.md` listing what changed vs. v1 (4 items per cover_email.md: title PQC acronym, Code & Data Availability section, ref [34] update, 3 in-text citations for orphaned floats)
5. Write `build_sha.txt` with `git rev-parse HEAD` at upload time
6. Update `~/qanary/papers/registry.yaml`: append `papers.paper2.arxiv.versions[]` entry for v2 with uploaded_date
7. Run `python3 ~/qanary/papers/render_registry.py`
8. Commit + tag `arxiv-v2`
9. Update `correspondence/khaled/2026-04-17_sent_v2.23/STATUS.md` from PENDING to RESPONDED (or new exchange folder if Khaled sends separate confirmation)
