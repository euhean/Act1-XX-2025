from loguru import logger


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


class RTSPParser:
    @staticmethod
    def parse_response(response: str) -> dict:
        result = {
            "status_code": None,
            "status_message": None,
            "headers": {},
            "raw": response
        }

        lines = response.strip().splitlines()
        if not lines:
            return result

        status_parts = lines[0].split(" ", 2)
        if len(status_parts) >= 2:
            result["status_code"] = status_parts[1]
        if len(status_parts) == 3:
            result["status_message"] = status_parts[2]

        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                result["headers"][key.strip()] = value.strip()

        return result