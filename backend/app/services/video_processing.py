import os
import re
import subprocess
import imageio_ffmpeg

def get_ffmpeg_binary() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()

def extract_video_metadata(file_path: str) -> dict:
    """
    Extracts duration, resolution, fps, codecs, and bitrate from a video file using FFmpeg.
    Does not modify the original media file in any way.
    """
    if not os.path.exists(file_path):
        return {}

    ffmpeg_exe = get_ffmpeg_binary()
    cmd = [ffmpeg_exe, "-hide_banner", "-i", file_path]
    
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    output = result.stderr or ""
    
    metadata = {
        "duration_seconds": None,
        "width": None,
        "height": None,
        "fps": None,
        "video_codec": None,
        "audio_codec": None,
        "container": None,
        "bitrate_kbps": None
    }
    
    # 1. Container from extension
    ext = os.path.splitext(file_path)[1].lower().strip(".")
    metadata["container"] = ext.upper() if ext else "UNKNOWN"
    
    # 2. Duration: Duration: 00:00:12.87, start: 0.000000, bitrate: 10216 kb/s
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if dur_match:
        hours = int(dur_match.group(1))
        mins = int(dur_match.group(2))
        secs = float(dur_match.group(3))
        metadata["duration_seconds"] = round(hours * 3600 + mins * 60 + secs, 2)
        
    # 3. Bitrate
    bitrate_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", output)
    if bitrate_match:
        metadata["bitrate_kbps"] = int(bitrate_match.group(1))
        
    # 4. Video Stream: Stream #0:0[0x1](und): Video: h264 (Main) ..., 1874x1378 ..., 30 fps
    video_match = re.search(r"Stream.*Video:\s*([a-zA-Z0-9_-]+)[^,]*,\s*[^,]*,\s*(\d{2,5})x(\d{2,5})", output)
    if video_match:
        metadata["video_codec"] = video_match.group(1).upper()
        metadata["width"] = int(video_match.group(2))
        metadata["height"] = int(video_match.group(3))
        
    # FPS
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", output)
    if fps_match:
        metadata["fps"] = float(fps_match.group(1))
        
    # 5. Audio Stream: Stream #0:1[0x2](und): Audio: aac ...
    audio_match = re.search(r"Stream.*Audio:\s*([a-zA-Z0-9_-]+)", output)
    if audio_match:
        metadata["audio_codec"] = audio_match.group(1).upper()
        
    return metadata

def process_derived_video(
    input_path: str,
    output_path: str,
    operation: str,
    start_time: float = None,
    end_time: float = None,
    crop: dict = None
) -> None:
    """
    Produces a derived video file from input_path.
    THE ORIGINAL FILE IS ONLY OPENED IN READ-ONLY MODE.
    Supports TRIM, CROP, and TRIM_AND_CROP.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input evidence file not found: {input_path}")
        
    ffmpeg_exe = get_ffmpeg_binary()
    cmd = [ffmpeg_exe, "-y"]
    
    # Accurate seeking: input seek if trimming
    if operation in ("TRIM", "TRIM_AND_CROP"):
        if start_time is not None:
            cmd.extend(["-ss", str(max(0.0, float(start_time)))])
        if end_time is not None:
            cmd.extend(["-to", str(float(end_time))])
            
    cmd.extend(["-i", input_path])
    
    # Spatial crop filter
    if operation in ("CROP", "TRIM_AND_CROP") and crop:
        w = int(crop.get("width", 0))
        h = int(crop.get("height", 0))
        x = int(crop.get("x", 0))
        y = int(crop.get("y", 0))
        if w > 0 and h > 0:
            cmd.extend(["-filter:v", f"crop={w}:{h}:{x}:{y}"])
            
    # Standard high-compatibility H.264 / AAC encode with faststart for web streaming
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ])
    
    # Execute ffmpeg
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg processing failed (code {result.returncode}): {result.stderr}")


def extract_frame_image(input_path: str, output_path: str, media_time: float) -> None:
    """Extracts a single high-quality still frame image at media_time.

    The original video is opened purely in read-only mode and is not modified.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input evidence file not found: {input_path}")

    ffmpeg_exe = get_ffmpeg_binary()
    seek_time = max(0.0, float(media_time))

    cmd = [
        ffmpeg_exe,
        "-y",
        "-ss", f"{seek_time:.3f}",
        "-i", input_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"Frame extraction failed: {result.stderr[-300:] if result.stderr else 'Unknown error'}")

