# LOCAL MODELS — locator only

Use local OCR and small local models only to find pages. They never write a row.

For each PDF in the open custody list, write:

`file | page | hit_phrase | confidence_is_irrelevant`

Hit phrases: `T45N`, `45N`, `R76W`, `76W`, `Section 12`, `Section 14`, `Sec. 12`, `Sec. 14`, `12-45N-76W`, `14-45N-76W`.

A hit sends that page to Gemini. A miss does not prove the page is out of scope. Image-only pages with no text layer stay UNKNOWN and go to vision anyway.

Do not output grantor, grantee, or dates from OCR into the index. Do not “clean up” names.
