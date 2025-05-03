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
