# M1 — Coordinate and Preview Custody

## Objective

Make molecular geometry and generated preview bytes content-addressed evidence
without allowing a model to invent or repair coordinates or native inputs.

## Required work

1. For PRP-10, admit only exact official single-frame XYZ in angstrom.
2. Bind source/archive member, source and imported-byte hashes, frame count,
   units, atom order, molecular identity approval, and access/license record in
   `CoordinateImportReceipt`.
3. Reject SI-table transcription, OCR, SMILES-to-3D, model coordinate
   generation, model repair, and overwrite. Missing geometry blocks dependent
   nodes.
4. Keep SDF/MOL/PDB conversion as a separately validated general-input path;
   it cannot satisfy PRP-10 eligibility.
5. Store ChemSmart-generated safe-preview input bytes in a private evidence
   store and expose only approved metadata and exact-byte hashes publicly.

## Gate

Positive and negative fixtures deterministically prove byte identity, atom
order, units, source binding, non-overwrite, and blocked behavior. No chemistry
engine, scheduler, or HPC process runs. New work reaches at most `previewed`.
Run one focused milestone suite and at most one evidence-driven rerun.
