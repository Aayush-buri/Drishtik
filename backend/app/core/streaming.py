import os
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

def range_requests_response(
    request: Request, file_path: str, content_type: str
) -> Response:
    """
    Returns a StreamingResponse that correctly handles HTTP Range requests
    for HTML5 video streaming.
    """
    file_size = os.stat(file_path).st_size
    range_header = request.headers.get("range")

    headers = {
        "content-type": content_type,
        "accept-ranges": "bytes",
        "content-encoding": "identity",
        "content-length": str(file_size),
        "access-control-expose-headers": (
            "content-type, accept-ranges, content-length, "
            "content-range, content-encoding"
        ),
    }

    if range_header is None:
        def file_iterator(path: str):
            with open(path, "rb") as f:
                yield from f
        return StreamingResponse(
            file_iterator(file_path),
            headers=headers,
            media_type=content_type,
            status_code=200,
        )

    start, end = 0, file_size - 1
    range_parts = range_header.replace("bytes=", "").split("-")
    
    if range_parts[0]:
        start = int(range_parts[0])
    if len(range_parts) > 1 and range_parts[1]:
        end = int(range_parts[1])
        
    if start > end or start >= file_size:
        headers["content-range"] = f"bytes */{file_size}"
        return Response(status_code=416, headers=headers)

    chunk_size = end - start + 1
    headers["content-length"] = str(chunk_size)
    headers["content-range"] = f"bytes {start}-{end}/{file_size}"

    def ranged_file_iterator(path: str, start_byte: int, chunk: int):
        with open(path, "rb") as f:
            f.seek(start_byte)
            bytes_read = 0
            while bytes_read < chunk:
                read_size = min(65536, chunk - bytes_read)
                data = f.read(read_size)
                if not data:
                    break
                bytes_read += len(data)
                yield data

    return StreamingResponse(
        ranged_file_iterator(file_path, start, chunk_size),
        headers=headers,
        status_code=206,
        media_type=content_type,
    )
