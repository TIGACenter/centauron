class MessageSendException(Exception):

    def __init__(self, address, status_code, error, response, **kwargs):
        self.status_code = status_code
        self.address = address
        self.error = error
        self.response = response
        super().__init__(**kwargs)
