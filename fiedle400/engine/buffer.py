"""FIFO byte ring-buffer for continuous stream alignment and boundary recovery."""


class SerialByteStreamBuffer:
    """FIFO byte buffer for continuous stream alignment and HID report boundary recovery."""

    def __init__(self, max_capacity: int = 65536):
        self._buffer = bytearray()
        self._max_capacity = max_capacity

    def write(self, data: bytes) -> None:
        """Appends raw bytes to the stream buffer."""
        if len(self._buffer) + len(data) > self._max_capacity:
            overflow = (len(self._buffer) + len(data)) - self._max_capacity
            del self._buffer[:overflow]
        self._buffer.extend(data)

    def peek(self, length: int) -> bytes:
        """Peeks at the first `length` bytes without advancing the buffer offset."""
        return bytes(self._buffer[:length])

    def consume(self, length: int) -> bytes:
        """Reads and removes `length` bytes from the buffer."""
        chunk = bytes(self._buffer[:length])
        del self._buffer[:length]
        return chunk

    def clear(self) -> None:
        """Flushes the stream buffer."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
