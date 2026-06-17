# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 TU Wien & AWST
# SPDX-FileCopyrightText: For a full list of authors, see the AUTHORS file.


def escape_latex(value: str) -> str:
    """
    Escape LaTeX special characters in a plain-text string so that it
    can be safely embedded in a .tex document without breaking compilation.

    Parameters
    ----------
    value : str
        The raw string value to escape.

    Returns
    -------
    str
        The escaped string, safe for use in LaTeX text mode.
    """
    _LATEX_ESCAPE_MAP = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for char, replacement in _LATEX_ESCAPE_MAP:
        value = value.replace(char, replacement)
    return value


class ValidationReportError(Exception):

    def __init__(self, message="Validation report failed"):
        self.message = message
        super().__init__(self.message)
