# Goal Command Length Receipt

The fenced bodies were measured on 2026-08-01 with their terminating newline
included. Markdown headings and fences are excluded. Every command is below
both the 3,500 Unicode-character and 3,500 UTF-8-byte limits.

| Phase | Unicode characters | UTF-8 bytes | Lines |
| --- | ---: | ---: | ---: |
| R0 | 2,504 | 2,504 | 13 |
| R1 | 2,689 | 2,689 | 15 |
| R2 | 2,774 | 2,774 | 15 |
| R3 | 2,817 | 2,817 | 15 |
| R4 | 2,697 | 2,697 | 15 |
| R5 | 3,225 | 3,225 | 15 |
| R6 | 3,239 | 3,239 | 15 |

Measurement definition: extract lines strictly between `~~~text` and the
closing `~~~`, retain each line's newline, count Unicode characters in a UTF-8
locale, and separately count encoded bytes. The command bodies are ASCII, so
the two totals coincide.
