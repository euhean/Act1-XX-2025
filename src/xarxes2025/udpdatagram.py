from time import time

    
class UDPDatagram:	
    HEADER_SIZE = 12
	
    def __init__(self, seqnum, payload):
        self.encode(seqnum, payload)        
        pass
        
    def encode(self, seqnum, payload):
        """Encode the RTP packet with header fields and payload."""
        header = bytearray(self.HEADER_SIZE)

        timestamp: int = int(time())
        ssrc: int = 0

        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26 

        # Hader bytearray with RTP header fields
        header[0] = (version << 6) | (padding << 5) | (extension << 4) | cc
        header[1] = (marker << 7) | pt
        header[2] = (seqnum >> 8) & 0xFF
        header[3] = seqnum & 0xFF

        # Bytes 4-7 are for the timestamp
        header[4] = (timestamp >> 24) & 0xFF
        header[5] = (timestamp >> 16) & 0xFF
        header[6] = (timestamp >> 8) & 0xFF
        header[7] = timestamp & 0xFF

        # Bytes 8-11 are for the SSRC
        header[8] = (ssrc >> 24) & 0xFF
        header[9] = (ssrc >> 16) & 0xFF
        header[10] = (ssrc >> 8) & 0xFF
        header[11] = ssrc & 0xFF
        
        self.header = header
        
        # Get the payload from the argument
        self.payload = payload
        
    def decode(self, byteStream):
        """Decode the RTP packet."""
        self.header = bytearray(byteStream[:self.HEADER_SIZE])
        self.payload = byteStream[self.HEADER_SIZE:]

    def get_version(self):
        """Return RTP version."""
        return int(self.header[0] >> 6)

    def get_seqnum(self):
        """Return sequence (frame) number."""
        seqnum = self.header[2] << 8 | self.header[3]
        return int(seqnum)

    def timestamp(self):
        """Return timestamp."""
        timestamp = self.header[4] << 24 | self.header[5] << 16 | self.header[6] << 8 | self.header[7]
        return int(timestamp)

    def get_payload(self):
        """Return payload."""
        return self.payload
        
    def get_datagram(self):
        """Return RTP datagram."""
        return self.header + self.payload