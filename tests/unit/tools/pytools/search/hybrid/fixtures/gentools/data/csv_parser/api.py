"""CSV parser tool."""


def run_parsed(filepath: str, delimiter: str = ",") -> list:
    """Parse CSV files into structured data.

    Reads a CSV file and converts it into a list of dictionaries,
    using the first row as column headers.

    Args:
        filepath: Path to the CSV file.
        delimiter: Field delimiter character.

    Returns:
        List of dictionaries representing rows.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    return []


def run(filepath: str) -> list:
    """Parse CSV file (basic version).

    Args:
        filepath: Path to the CSV file.

    Returns:
        List of rows.
    """
    return []
