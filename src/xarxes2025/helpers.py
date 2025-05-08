class RTSPRequestBuilder:
    @staticmethod
    def build(command, filename, cseq, session_id=None, client_port=None):
        """Build an RTSP request."""
        if not filename.startswith('/'):
            filename = '/' + filename
            
        request = [f"{command} {filename} RTSP/1.0", f"CSeq: {cseq}"]
        
        if client_port and command == "SETUP":
            request.append(f"Transport: RTP/UDP;client_port={client_port}")
            
        if session_id and command != "SETUP":
            request.append(f"Session: {session_id}")
            
        return "\r\n".join(request) + "\r\n\r\n"


class RTSPResponseBuilder:
    @staticmethod
    def build(cseq, code=200, status="OK", session_id=None):
        """Build an RTSP response."""
        response = [f"RTSP/1.0 {code} {status}", f"CSeq: {cseq}"]
        
        if session_id:
            response.append(f"Session: {session_id}")
            
        return "\r\n".join(response) + "\r\n\r\n"


class RTSPParser:
    @staticmethod
    def parse_response(data):
        """Parse an RTSP response or request."""
        if not data:
            return {"status_code": "400", "status_message": "Empty Request", "headers": {}}
            
        lines = data.strip().split('\r\n')
        if not lines:
            return {"status_code": "400", "status_message": "Empty Request", "headers": {}}
            
        # First line is special - either status line or request line
        first_line = lines[0].strip()
        
        # Check if this is a response
        if first_line.startswith('RTSP/'):
            parts = first_line.split(' ', 2)
            if len(parts) < 3:
                return {"status_code": "400", "status_message": "Bad Request", "headers": {}}
                
            status_code = parts[1]
            status_message = parts[2] if len(parts) > 2 else ""
        else:
            # Assume it's a request
            parts = first_line.split(' ')
            status_code = parts[0] if parts else ""
            status_message = parts[1] if len(parts) > 1 else ""
        
        # Parse headers
        headers = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            try:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
            except ValueError:
                # Invalid header line
                continue
                
        return {
            "status_code": status_code,
            "status_message": status_message,
            "headers": headers
        }