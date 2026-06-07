"""Title Report Factory.

A reusable, automated cursory title report pipeline.

The package gathers records, OCRs documents, classifies instruments, builds a
verified full-text index, analyzes the chain of title, fills an Excel workbook
template, and exports a finished report -- with a source, confidence score, and
issue note attached to every material conclusion.

Guiding rule: never fake perfection. "Unknown" is better than "wrong".
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
