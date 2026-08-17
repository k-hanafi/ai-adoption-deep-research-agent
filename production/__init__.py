"""Batch runner for SGS, PCS, or UAS over the P4+P5 production set.

CLI: ``python -m production {run,dry-run,status,dedupe,verify}``.
Live writes land under ``outputs/prod/{sgs,pcs,uas}/``.
``dedupe`` writes ``findings_deduplicated.csv``.
``verify`` reads that file and appends ``findings_verified.csv``.
"""
