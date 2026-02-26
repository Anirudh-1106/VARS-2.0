"""
Malayalam to English translation using Sarvam AI Translate API.

Splits text into chunks under 1000 characters to stay within the
mayura:v1 API limit, translates each chunk, and joins the results.
"""

import requests

SARVAM_API_KEY = "sk_flskekl8_0e7n4yyHfPri4w2u8oVrx2ol"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"
MAX_CHARS = 900  # keep under the 1000-char API limit


def _split_text(text: str, max_len: int = MAX_CHARS) -> list:
    """Split text into chunks at sentence boundaries (. ! ? or |)."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    # Split on common Malayalam/Unicode sentence endings
    import re
    sentences = re.split(r'(?<=[.!?\u0D64\u0D65|])\s*', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # If a single sentence exceeds the limit, split by spaces
        if len(sentence) > max_len:
            words = sentence.split()
            for word in words:
                if len(current) + len(word) + 1 > max_len:
                    if current:
                        chunks.append(current.strip())
                    current = word
                else:
                    current = (current + " " + word) if current else word
        elif len(current) + len(sentence) + 1 > max_len:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence) if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _translate_chunk(text: str) -> str:
    """Translate a single chunk (<= 1000 chars) via Sarvam API."""
    payload = {
        "input": text,
        "source_language_code": "ml-IN",
        "target_language_code": "en-IN",
        "model": "mayura:v1",
        "enable_preprocessing": True,
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }

    response = requests.post(SARVAM_TRANSLATE_URL, json=payload, headers=headers)

    print(f"[TRANSLATE] Status: {response.status_code}")
    print(f"[TRANSLATE] Response: {response.text}")

    if response.status_code != 200:
        raise RuntimeError(f"Sarvam Translate API error {response.status_code}: {response.text}")

    result = response.json()
    return result.get("translated_text", "")


def translate_malayalam_to_english(text: str) -> str:
    """
    Translate Malayalam text to English using Sarvam AI.
    Automatically splits long text into chunks to bypass the 1000-char limit.

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
        chunks = _split_text(text)
        print(f"[TRANSLATE] Text length: {len(text)} chars, split into {len(chunks)} chunk(s)")

        translations = []
        for i, chunk in enumerate(chunks):
            print(f"[TRANSLATE] Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            translated = _translate_chunk(chunk)
            if translated:
                translations.append(translated.strip())

        full_translation = " ".join(translations)

        if not full_translation.strip():
            raise RuntimeError("Empty translation returned")

        return full_translation.strip()

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
