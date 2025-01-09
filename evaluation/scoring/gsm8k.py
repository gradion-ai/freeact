import re


def get_question_score_gsm8k(answer: str, true_answer: str) -> bool:
    numbers_answer = extract_numbers(answer)
    if len(numbers_answer) == 0:
        return False
    return float(numbers_answer[-1]) == float(true_answer)


def extract_numbers(text: str) -> list[str]:
    """This pattern matches:
    - Optional negative sign
    - Numbers with optional comma thousand separators
    - Optional decimal points with decimal numbers
    """
    pattern = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

    return [el.replace(",", "") for el in re.findall(pattern, text)]
