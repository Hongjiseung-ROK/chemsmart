# Goal Command Length Receipt

Measured on 2026-08-02 with each fenced body's terminating newline included.
Headings and fences are excluded. The command bodies are ASCII, so Unicode
character and UTF-8 byte counts are equal.

| Phase | Unicode characters | UTF-8 bytes | Lines |
| --- | ---: | ---: | ---: |
| M0 | 2,414 | 2,414 | 9 |
| M1 | 2,220 | 2,220 | 9 |
| M2 | 2,166 | 2,166 | 9 |
| M3 | 2,287 | 2,287 | 9 |
| M4 | 2,383 | 2,383 | 9 |

Measurement: extract bytes strictly between `~~~text` and the closing `~~~`,
preserve line endings, decode as UTF-8 for character count, and separately
count encoded bytes. Every command is below the 3,500-character limit.
