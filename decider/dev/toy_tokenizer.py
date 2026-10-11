"""Build a small byte-level BPE tokenizer with Qwen-style control tokens, for tests and
GPU-less dev. Same moving parts as the real Qwen tokenizer: specials (<|im_start|>,
<|im_end|>, <|endoftext|>) and NON-special added tokens (<think>, <tool_call>, ...).

  python -m dev.toy_tokenizer /tmp/toy-tokenizer.json
"""
import sys
from pathlib import Path

from tokenizers import AddedToken, Tokenizer, decoders, models, pre_tokenizers, trainers

CORPUS = [
    "Guvernul a aprobat bugetul. Parlamentul, NATO, UE, Bucureşti, PIB, inflaţia.",
    "domestic_politics international_relations elections defense_military cybersecurity",
    "crime_justice terrorism_extremism disinformation economy finance_markets business energy",
    "technology science health environment_climate natural_disasters accidents_emergencies",
    "transport_infrastructure agriculture_food education labor_social migration human_rights",
    "law_regulation law_enforcement religion culture_arts entertainment sports lifestyle_other",
    "You are a decision function. Read the document and answer the question. Options Rules",
    "system user assistant document politics yes no Topic Question",
] * 20


def build(path: str) -> str:
    tok = Tokenizer(models.BPE())
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=1200, initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
                                  show_progress=False)
    tok.train_from_iterator(CORPUS, trainer)
    tok.add_special_tokens([AddedToken(t, special=True) for t in ("<|endoftext|>", "<|im_start|>", "<|im_end|>")])
    tok.add_tokens([AddedToken(t, special=False) for t in ("<think>", "</think>", "<tool_call>", "</tool_call>")])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tok.save(path)
    return path


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/toy-tokenizer.json"))
