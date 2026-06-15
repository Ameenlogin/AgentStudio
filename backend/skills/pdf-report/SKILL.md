# PDF Report

Create clean, well-structured PDF documents.

## Approach
- Use the `pdf_create` tool with light Markdown: `#` title, `##` sections, `-` bullets, blank lines between paragraphs.
- Lead with a title and a one-line summary, then sections in a logical order.
- Keep paragraphs short; prefer bullets for lists of facts.
- For data, summarize key numbers in the text (the core font is plain — avoid wide tables; describe them or split into bullets).
- Confirm the output path so the user can download it.

## Good structure
1. Title + date + author/subject.
2. Executive summary (3–5 lines).
3. Body sections with `##` headings.
4. Key findings / recommendations as bullets.
5. Appendix / sources.

## Reading PDFs
- Use `pdf_read` to extract text, then summarize, extract data, or transform it.
- If a PDF is scanned (no extractable text), say so and suggest OCR.
