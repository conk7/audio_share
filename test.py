# from pydantic import BaseModel

# class TestModel(BaseModel):
#     name: str


# a = TestModel(name="test")

# a = a.model_dump_json()

# b = TestModel.model_validate_json(a)

# print(b.name)


import os
from pathlib import Path
from pydub import AudioSegment, playback
from src.mp3_handles import path_to_ffmpeg
from io import BytesIO

AudioSegment.ffmpeg = path_to_ffmpeg()
os.environ["PATH"] += os.pathsep + str(Path(path_to_ffmpeg()).parent)


song = AudioSegment.from_mp3("audio.mp3")

# playback.play(song)

export_bytes = BytesIO()
song.export(export_bytes, format="wav")
export_bytes = export_bytes.getvalue()
print(export_bytes[:10])
export_bytes = BytesIO(export_bytes)
song = AudioSegment.from_wav(export_bytes)
# playback.play(song)
# print(export_bytes.getvalue())
