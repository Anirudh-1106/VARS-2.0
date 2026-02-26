# services/speech_to_text.py

import torch
from transformers import pipeline

print("Loading IndicWhisper Malayalam model...")

device = 0 if torch.cuda.is_available() else -1

whisper_asr = pipeline(
    "automatic-speech-recognition",
    model="ai4bharat/indic-whisper-medium-ml",
    device=device
)

# Force Malayalam transcription
whisper_asr.model.config.forced_decoder_ids = (
    whisper_asr.tokenizer.get_decoder_prompt_ids(
        language="ml",
        task="transcribe"
    )
)

print("Model loaded successfully.")

def transcribe_audio(audio_path: str) -> str:
    """
    Takes path to audio file and returns Malayalam transcript.
    """
    result = whisper_asr(audio_path)
    return result["text"]
