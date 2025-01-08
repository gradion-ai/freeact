"""
SimpleQA scoring system using GPT-4o
This scoring system is based on the guidelines described in the following article:
- https://openai.com/index/introducing-simpleqa/
"""

from openai import OpenAI

JUDGE_SYSTEM_PROMPT = """Evaluate the given predicted answer to the question by assigning a grade according to the provided grading guidelines.

Grade the predicted answer as "Correct", "Incorrect", or "Not attempted" based on these criteria:

- **Correct**: The predicted answer fully contains the ground-truth answer without contradicting the reference answer. Numbers in the predicted answer must match numbers in the true answer exactly (including decimal places). Units can be omitted in the predicted answer.
- **Incorrect**: The predicted answer contradicts the ground-truth answer in any way, even if the contradiction is hedged.
- **Not attempted**: The ground truth target is not fully given in the answer, and there are no contradictions with the reference answer.

# Examples

Question: Which Dutch player scored an open-play goal in the 2022 Netherlands vs Argentina game in the men's FIFA World Cup
True answer: Wout Weghorst

**Correct answers:**
* Wout Weghorst
* Wout Weghorst scored at 83' and 90+11' in that game

**Incorrect answers:**
* Virgil van Dijk
* Virgil van Dijk and Wout Weghorst
* Wout Weghorst and I think van Dijk scored, but I am not totally sure

**Not attempted answers:**
* I don't know the answer to that question
* To find which Dutch player scored in that game, please browse the internet yourself

Remember:
* Numbers in the predicted answer must match numbers in the true answer exactly (including decimal places). Units can be omitted in the predicted answer.
"""

USER_PROMPT = """
Question: {question}
True answer: {true_answer}
Predicted answer: {answer}

Only respond with "Correct", "Incorrect", or "Not attempted".
"""


class SimpleQAScorer:
    def __init__(self):
        self.client = OpenAI()

    def score(self, question: str, answer: str, true_answer: str) -> bool:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=128,
            temperature=0.0,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT.format(question=question, answer=answer, true_answer=true_answer),
                },
            ],
        )

        response_message = response.choices[0].message.content
        return response_message.lower().strip() == "correct"
