import yaml
from pathlib import Path


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
        ('&',  r'\&'),
        ('%',  r'\%'),
        ('$',  r'\$'),
        ('#',  r'\#'),
        ('_',  r'\_'),
        ('{',  r'\{'),
        ('}',  r'\}'),
        ('~',  r'\textasciitilde{}'),
        ('^',  r'\textasciicircum{}'),
    ]
    for char, replacement in _LATEX_ESCAPE_MAP:
        value = value.replace(char, replacement)
    return value


class ValidationReportError(Exception):

    def __init__(self, message="Validation report failed"):
        self.message = message
        super().__init__(self.message)


def load_yml_to_dict(filepath: str | Path) -> dict:
    """
    Load a QA4SM-style YAML config/results file into a nested dictionary.

    Parameters
    ----------
    filepath: str or Path
        Path to the yml content

    Returns:
        data: dict
            The first level are the content sections names, sublevels are the
            variables in that section.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"No file found at: {filepath}")
    if filepath.suffix not in (".yml", ".yaml"):
        raise ValueError(f"Expected a .yml/.yaml file, got: {filepath.suffix}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("YAML content did not parse to a dictionary.")

    return data


def populate_latex(template, file_out,
                   placeholder="{{PLACEHOLDER}}", replacement="",
                   template_direct=False):
    """
    Read LaTeX template, replace placeholders with data and write to file.
    """
    try:
        # Read the LaTeX file
        with open(template, 'r', encoding='utf-8') as f:
            content = f.read()

        # Perform search and replace
        updated_content = content.replace(placeholder, replacement)

        # Write back to file
        with open(file_out, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        # Report number of replacements made
        num_replacements = content.count(placeholder)
        print(f"Made {num_replacements} replacement(s)")

    except FileNotFoundError:
        print(f"Error: Template '{template}' not found")
    except Exception as e:
        print(f"Error processing file: {e}")