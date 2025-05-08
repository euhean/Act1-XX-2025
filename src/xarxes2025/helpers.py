from loguru import logger
import re


# === RTSP Response Builder ===
class RTSPResponseBuilder:
    @staticmethod
    def build(cseq, code=200, status="OK", session=None):
        lines = [
            f"RTSP/1.0 {code} {status}",
            f"CSeq: {cseq}"
        ]
        if session:
            lines.append(f"Session: {session}")
        return "\r\n".join(lines) + "\r\n\r\n"


# === RTSP Request Builder ===
class RTSPRequestBuilder:
    @staticmethod
    def build(command, filename, cseq, session_id=None, client_port=None):
        lines = [
            f"{command} {filename} RTSP/1.0",
            f"CSeq: {cseq}"
        ]
        if command == "SETUP" and client_port:
            lines.append(f"Transport: RTP/UDP; client_port={client_port}")
        if command != "SETUP" and session_id:
            lines.append(f"Session: {session_id}")
        return "\r\n".join(lines) + "\r\n\r\n"


# === RTSP Parser ===
class RTSPParser:
    STATUS_LINE_REGEX = re.compile(r"^RTSP/\d+\.\d+\s+(\d+)\s+(.*)$")

    @staticmethod
    def parse_response(response: str):
        parsed = {
            "status_code": None,
            "status_message": None,
            "headers": {},
            "raw": response
        }

        lines = list(filter(None, map(str.strip, response.splitlines())))
        if not lines:
            return parsed

        match = RTSPParser.STATUS_LINE_REGEX.match(lines[0])
        if match:
            parsed["status_code"] = match.group(1)
            parsed["status_message"] = match.group(2)

        for line in lines[1:]:
            if ":" in line:
                try:
                    key, value = line.split(":", 1)
                    parsed["headers"][key.strip()] = value.strip()
                except ValueError:
                    logger.warning(f"Malformed RTSP header: {line}")

        return parsed