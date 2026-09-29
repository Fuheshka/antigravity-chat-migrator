"""Pure-Python Protobuf encoder and decoder for Antigravity metadata.

Operates without compiled .proto files or protoc binary, providing safe
serialization, deserialization, and manipulation of Antigravity trajectory
and summary metadata.
"""

from typing import Any, List, Optional, Tuple, Union

__all__ = [
    "encode_varint",
    "encode_field",
    "parse_proto",
    "build_workspace_info",
    "inject_project_id_into_metadata",
]


def encode_varint(val: int) -> bytes:
    """Encode an integer as a Protobuf varint.

    Negative values are encoded using 64-bit two's complement representation.
    """
    if val < 0:
        val &= (1 << 64) - 1

    res = bytearray()
    while val >= 0x80:
        res.append((val & 0x7F) | 0x80)
        val >>= 7
    res.append(val & 0x7F)
    return bytes(res)


def encode_field(
    field_num: int,
    wire_type: int,
    payload: Union[bytes, bytearray, int, str],
) -> bytes:
    """Encode a single Protobuf field with tag and payload.

    Supported wire types:
      - 0: Varint
      - 1: 64-bit fixed
      - 2: Length-delimited (string, bytes, embedded message)
      - 5: 32-bit fixed
    """
    tag = (field_num << 3) | (wire_type & 0x7)
    tag_bytes = encode_varint(tag)

    if wire_type == 0:
        if not isinstance(payload, int):
            raise TypeError(f"Payload for wire_type 0 must be int, got {type(payload)}")
        return tag_bytes + encode_varint(payload)

    elif wire_type == 2:
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        elif isinstance(payload, (bytes, bytearray)):
            payload_bytes = bytes(payload)
        else:
            raise TypeError(
                f"Payload for wire_type 2 must be bytes or str, got {type(payload)}"
            )
        return tag_bytes + encode_varint(len(payload_bytes)) + payload_bytes

    elif wire_type == 1:
        if isinstance(payload, int):
            payload_bytes = payload.to_bytes(8, "little", signed=payload < 0)
        elif isinstance(payload, (bytes, bytearray)):
            payload_bytes = bytes(payload)
        else:
            raise TypeError(
                f"Payload for wire_type 1 must be bytes or int, got {type(payload)}"
            )
        if len(payload_bytes) != 8:
            raise ValueError(
                f"Wire type 1 payload must be 8 bytes, got {len(payload_bytes)}"
            )
        return tag_bytes + payload_bytes

    elif wire_type == 5:
        if isinstance(payload, int):
            payload_bytes = payload.to_bytes(4, "little", signed=payload < 0)
        elif isinstance(payload, (bytes, bytearray)):
            payload_bytes = bytes(payload)
        else:
            raise TypeError(
                f"Payload for wire_type 5 must be bytes or int, got {type(payload)}"
            )
        if len(payload_bytes) != 4:
            raise ValueError(
                f"Wire type 5 payload must be 4 bytes, got {len(payload_bytes)}"
            )
        return tag_bytes + payload_bytes

    else:
        raise ValueError(f"Unsupported wire_type {wire_type}")


def parse_proto(data: Optional[bytes]) -> List[Tuple[int, int, Any]]:
    """Safely parse raw Protobuf bytes without schema.

    Returns a list of tuples: (field_number, wire_type, value)
    Handles empty, truncated, and corrupt payloads gracefully by returning
    successfully parsed fields without raising exceptions.
    """
    if not isinstance(data, (bytes, bytearray)) or not data:
        return []

    fields: List[Tuple[int, int, Any]] = []
    i = 0
    n = len(data)

    while i < n:
        # Decode field tag varint (field_number << 3 | wire_type)
        tag = 0
        shift = 0
        tag_bytes_read = 0
        tag_ok = False

        while i < n and tag_bytes_read < 10:
            b = data[i]
            i += 1
            tag_bytes_read += 1
            tag |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                tag_ok = True
                break

        if not tag_ok or tag == 0:
            break

        field_num = tag >> 3
        wire_type = tag & 0x7

        if field_num == 0:
            break

        if wire_type == 0:
            # Varint value
            val = 0
            shift = 0
            val_bytes_read = 0
            val_ok = False

            while i < n and val_bytes_read < 10:
                b = data[i]
                i += 1
                val_bytes_read += 1
                val |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    val_ok = True
                    break

            if not val_ok:
                break
            fields.append((field_num, 0, val))

        elif wire_type == 2:
            # Length-delimited payload
            length = 0
            shift = 0
            len_bytes_read = 0
            len_ok = False

            while i < n and len_bytes_read < 10:
                b = data[i]
                i += 1
                len_bytes_read += 1
                length |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    len_ok = True
                    break

            if not len_ok or length < 0:
                break
            if i + length > n:
                # Truncated payload
                break

            val_bytes = bytes(data[i : i + length])
            i += length
            fields.append((field_num, 2, val_bytes))

        elif wire_type == 1:
            # 64-bit fixed
            if i + 8 > n:
                break
            val_bytes = bytes(data[i : i + 8])
            i += 8
            fields.append((field_num, 1, val_bytes))

        elif wire_type == 5:
            # 32-bit fixed
            if i + 4 > n:
                break
            val_bytes = bytes(data[i : i + 4])
            i += 4
            fields.append((field_num, 5, val_bytes))

        else:
            # Unsupported wire type (group start/end 3, 4, or reserved 6, 7)
            break

    return fields


def build_workspace_info(
    uri: Optional[str],
    repo: Optional[str] = None,
    git_url: Optional[str] = None,
    branch: str = "main",
) -> bytes:
    """Build serialized WorkspaceInfo protobuf bytes.

    Structure:
      - Field 1 (wire 2): URI
      - Field 2 (wire 2): URI
      - Field 3 (wire 2): Git repository metadata if repo & git_url, else empty
      - Field 4 (wire 2): Branch name (if git metadata present)
    """
    if not uri:
        return b""

    b_uri = uri.encode("utf-8")
    parts = [encode_field(1, 2, b_uri), encode_field(2, 2, b_uri)]

    if repo and git_url:
        git_meta = encode_field(1, 2, repo.encode("utf-8")) + encode_field(
            2, 2, git_url.encode("utf-8")
        )
        parts.append(encode_field(3, 2, git_meta))
        parts.append(encode_field(4, 2, (branch or "main").encode("utf-8")))
    else:
        parts.append(encode_field(3, 2, b""))

    return b"".join(parts)


def inject_project_id_into_metadata(
    meta_bytes: Optional[bytes],
    project_id: str,
    new_ws_info: Optional[bytes] = None,
) -> bytes:
    """Safely update or inject project_id (field 18) and optional workspace_info (field 1).

    Preserves all existing fields in TrajectoryMetadata while replacing
    or appending field 18, and updating field 1 if new_ws_info is provided.
    """
    fields = parse_proto(meta_bytes) if meta_bytes else []

    new_fields: List[Tuple[int, int, Any]] = []
    has_field_1 = False

    for fn, wt, val in fields:
        if fn == 18:
            # Drop old project_id
            continue
        elif fn == 1 and new_ws_info is not None:
            new_fields.append((1, 2, new_ws_info))
            has_field_1 = True
        else:
            new_fields.append((fn, wt, val))

    if new_ws_info is not None and not has_field_1:
        new_fields.insert(0, (1, 2, new_ws_info))

    b_pid = project_id.encode("utf-8") if isinstance(project_id, str) else b""
    new_fields.append((18, 2, b_pid))

    return b"".join(encode_field(fn, wt, val) for fn, wt, val in new_fields)
