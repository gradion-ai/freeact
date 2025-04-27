from dataclasses import dataclass


@dataclass
class Usage:
    total_tokens: int = 0
    input_tokens: int = 0
    thinking_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost: float | None = None

    def update(self, other: "Usage"):
        self.total_tokens += other.total_tokens
        self.input_tokens += other.input_tokens
        self.thinking_tokens += other.thinking_tokens
        self.output_tokens += other.output_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cache_read_tokens += other.cache_read_tokens

        if self.cost is None and other.cost is not None:
            self.cost = other.cost
        elif self.cost is not None and other.cost is not None:
            self.cost += other.cost
