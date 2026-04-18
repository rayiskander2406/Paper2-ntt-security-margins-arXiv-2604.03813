# arXiv v1 — published, bytes recovery TODO

This is the original arXiv:2604.03813 v1 submission. The exact bytes of the upload are not yet captured here.

## Recovery options

1. **arXiv source download:** `wget https://arxiv.org/e-print/2604.03813v1` (gives the .tar.gz of the LaTeX source if uploaded as TeX, or the .docx/.pdf if uploaded as a single file)
2. **Local backup:** check `~/Desktop/Archive*` and email "Sent" folder for the original attachment
3. **Khaled's inbox:** he received the v1 manuscript before submission

## Once recovered

Place files in this folder following the convention:

```
v1/
├── README.md                this file
├── manuscript.docx          (or .pdf — frozen exact bytes uploaded)
├── source.md                matching markdown source (if known)
├── arxiv_metadata.md        title, abstract as v1, categories, comments field
├── CHANGES.md               "First arXiv version"
└── build_sha.txt            git SHA of paper/build/ at v1 upload (or "unknown")
```
