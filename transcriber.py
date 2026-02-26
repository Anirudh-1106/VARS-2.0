import io
import requests
from pydub import AudioSegment

SARVAM_API_KEY = "sk_flskekl8_0e7n4yyHfPri4w2u8oVrx2ol"
CHUNK_MS = 25000  # 25 seconds per chunk (under the 30s API limit)


def _transcribe_chunk(audio_segment: AudioSegment) -> str:
    """Send a single audio chunk (<=30s) to Sarvam STT and return transcript."""
    wav_buffer = io.BytesIO()
    audio_segment.export(wav_buffer, format="wav")
    wav_buffer.seek(0)

    files = {"file": ("recording.wav", wav_buffer, "audio/wav")}
    data = {"model": "saaras:v3", "language_code": "ml-IN"}
    headers = {"api-subscription-key": SARVAM_API_KEY}

    response = requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers=headers, files=files, data=data
    )

    print(f"[SARVAM] Status: {response.status_code}")
    print(f"[SARVAM] Response: {response.text}")

    if response.status_code != 200:
        raise Exception(f"Sarvam API error {response.status_code}: {response.text}")

    result = response.json()
    return result.get("transcript") or result.get("text") or result.get("transcription", "")


def transcribe_audio(audio_bytes: bytes) -> str:
    # Save raw webm to disk for inspection
    with open("debug_recording.webm", "wb") as f:
        f.write(audio_bytes)
    print(f"[DEBUG] Audio bytes received: {len(audio_bytes)}")

    # Convert webm -> wav (mono 16kHz)
    audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
    audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    duration_ms = len(audio_segment)
    print(f"[DEBUG] Audio duration: {duration_ms}ms")
    print(f"[DEBUG] Max amplitude: {audio_segment.max}")

    # Split into chunks if longer than 25 seconds
    if duration_ms <= CHUNK_MS:
        chunks = [audio_segment]
    else:
        chunks = []
        start = 0
        while start < duration_ms:
            end = min(start + CHUNK_MS, duration_ms)
            chunks.append(audio_segment[start:end])
            start = end
        print(f"[DEBUG] Split into {len(chunks)} chunks")

    # Transcribe each chunk and combine
    transcripts = []
    for i, chunk in enumerate(chunks):
        print(f"[DEBUG] Transcribing chunk {i+1}/{len(chunks)} ({len(chunk)}ms)")
        text = _transcribe_chunk(chunk)
        if text:
            transcripts.append(text)

    full_transcript = " ".join(transcripts)

    if not full_transcript.strip():
        raise Exception("Empty transcript -- please speak clearly and try again.")

    return full_transcript