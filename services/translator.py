"""
Malayalam to English translation using IndicTrans2 (ai4bharat).

Uses the HuggingFace IndicTrans2 model locally for offline,
free translation without any API keys.

Works with Python 3.8+ using only transformers + sentencepiece
(no IndicTransTokenizer dependency).
"""

import os
import re
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# ---------------------------------------------------------------------------
# Model loading (lazy singleton – loaded once on first call)
# ---------------------------------------------------------------------------
_MODEL_NAME = "ai4bharat/indictrans2-indic-en-1B"
_HF_TOKEN = os.environ.get("HF_TOKEN", "")
_MODEL_MAX_INPUT_TOKENS = 256
_MAX_INPUT_TOKENS = 220
_tokenizer = None
_model = None
_device = None


def _load_hf_token() -> str:
    """Load HF token from env or project .env file."""
    global _HF_TOKEN

    if _HF_TOKEN:
        return _HF_TOKEN

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("HF_TOKEN="):
                    _HF_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    return _HF_TOKEN


def _load_model():
    """Load IndicTrans2 model and tokenizer (once)."""
    global _tokenizer, _model, _device

    if _model is not None:
        return

    print("[TRANSLATE] Loading IndicTrans2 model … (first call only)")
    hf_token = _load_hf_token() or None

    _tokenizer = AutoTokenizer.from_pretrained(
        _MODEL_NAME,
        trust_remote_code=True,
        token=hf_token,
    )
    _model = AutoModelForSeq2SeqLM.from_pretrained(
        _MODEL_NAME,
        trust_remote_code=True,
        token=hf_token,
    )

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = _model.to(_device)
    _model.eval()
    print(f"[TRANSLATE] Model loaded on {_device}")


def _preprocess(text: str, src_lang: str = "mal_Mlym", tgt_lang: str = "eng_Latn") -> str:
    """
    Minimal preprocessing for IndicTrans2 tokenizer.
    The tokenizer expects: "src_lang tgt_lang text".
    """
    return f"{src_lang} {tgt_lang} {text}"


def _estimate_input_tokens(text: str, src_lang: str, tgt_lang: str) -> int:
    """Estimate token length for one input sample."""
    preprocessed = _preprocess(text, src_lang, tgt_lang)
    # Use tokenize() to avoid model_max_length warnings during chunk planning.
    # +1 accounts for EOS added in build_inputs_with_special_tokens.
    return len(_tokenizer.tokenize(preprocessed)) + 1


def _split_text_for_translation(text: str, src_lang: str, tgt_lang: str) -> list:
    """Split long text into tokenizer-safe chunks while preserving punctuation."""
    segments = [
        segment.strip()
        for segment in re.findall(r"[^,\.!?\n]+[,\.!?]?", text)
        if segment.strip()
    ]
    if not segments:
        return [text]

    chunks = []
    current_chunk = ""

    for segment in segments:
        candidate = f"{current_chunk} {segment}".strip() if current_chunk else segment
        if _estimate_input_tokens(candidate, src_lang, tgt_lang) <= _MAX_INPUT_TOKENS:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)

        if _estimate_input_tokens(segment, src_lang, tgt_lang) <= _MAX_INPUT_TOKENS:
            current_chunk = segment
            continue

        words = segment.split()
        running_text = ""
        for word in words:
            word_candidate = f"{running_text} {word}".strip() if running_text else word
            if _estimate_input_tokens(word_candidate, src_lang, tgt_lang) <= _MAX_INPUT_TOKENS:
                running_text = word_candidate
            else:
                if running_text:
                    chunks.append(running_text)
                if _estimate_input_tokens(word, src_lang, tgt_lang) <= _MAX_INPUT_TOKENS:
                    running_text = word
                    continue

                running_text = ""
                char_buffer = ""
                for char in word:
                    char_candidate = f"{char_buffer}{char}"
                    if _estimate_input_tokens(char_candidate, src_lang, tgt_lang) <= _MAX_INPUT_TOKENS:
                        char_buffer = char_candidate
                    else:
                        if char_buffer:
                            chunks.append(char_buffer)
                        char_buffer = char
                running_text = char_buffer

        current_chunk = running_text

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _translate_chunk(chunk_text: str, src_lang: str, tgt_lang: str) -> str:
    """Translate a single Malayalam chunk into English."""
    preprocessed = _preprocess(chunk_text, src_lang, tgt_lang)

    inputs = _tokenizer(
        preprocessed,
        truncation=True,
        max_length=_MODEL_MAX_INPUT_TOKENS,
        padding=True,
        return_tensors="pt",
    ).to(_device)

    with torch.no_grad():
        generated = _model.generate(
            **inputs,
            num_beams=5,
            num_return_sequences=1,
            max_new_tokens=256,
        )

    result = _tokenizer.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )

    return result[0].strip() if result else ""


def translate_malayalam_to_english(text: str) -> str:
    """
    Translate Malayalam text to English using IndicTrans2 locally.

    Args:
        text: A string of Malayalam text to translate.

    Returns:
        The translated English text.

    Raises:
        ValueError: If the input is empty or not a string.
        RuntimeError: If translation fails for any reason.
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected a string, got {type(text).__name__}")
    text = text.strip()
    if not text:
        raise ValueError("Input text is empty")

    try:
        _load_model()

        src_lang = "mal_Mlym"   # Malayalam
        tgt_lang = "eng_Latn"   # English

        text_chunks = _split_text_for_translation(text, src_lang, tgt_lang)
        translated_chunks = []
        for text_chunk in text_chunks:
            chunk_translation = _translate_chunk(text_chunk, src_lang, tgt_lang)
            if chunk_translation:
                translated_chunks.append(chunk_translation)

        translation = " ".join(translated_chunks).strip()

        if not translation:
            raise RuntimeError("Empty translation returned")

        print(f"[TRANSLATE] '{text}' -> '{translation}'")
        return translation

    except ValueError:
        raise
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Translation failed: {e}") from e


# --- Example usage ---
if __name__ == "__main__":
    sample = "എന്റെ പേര് രാഹുല്\u200d ആണ്, ഞാന്\u200d ഒരു സോഫ്റ്റ്\u200cവെയര്\u200d എഞ്ചിനീയര്\u200d ആണ്."
    print(f"Malayalam : {sample}")
    print(f"English   : {translate_malayalam_to_english(sample)}")
