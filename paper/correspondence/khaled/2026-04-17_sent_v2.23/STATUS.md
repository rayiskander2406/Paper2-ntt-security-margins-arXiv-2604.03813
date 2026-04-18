PENDING

Last updated: 2026-04-18 (no response yet from Khaled)

## State machine

- 2026-04-17 — SENT (cover email composed; v2.23 docx attached; asks: sanity-check, refresh-citations-in-Word, upload-as-arXiv-v2)
- → next expected: ACKNOWLEDGED, RESPONDED (with feedback or with upload confirmation), or ARXIV_V2_UPLOADED

## On Khaled's response

- If he uploads arXiv v2 directly: update STATUS to `ARXIV_V2_UPLOADED`, populate `../../arxiv/v2/` with frozen manuscript + metadata, mint a new Zenodo deposit, update registry
- If he sends a `_KK`-suffixed edited copy: create `2026-04-DD_received_v2.23_KK/` exchange folder with his attachment + `diff_vs_sent.md`; merge his edits into a v2.27 (or higher) bump
- If he sends approvals/queries via plain email: create `2026-04-DD_received_email/` with paraphrased message + STATUS update
