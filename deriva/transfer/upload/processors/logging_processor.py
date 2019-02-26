import logging
from deriva.transfer.upload.processors import BaseProcessor

logger = logging.getLogger(__name__)


class LoggingProcessor(BaseProcessor):
    """
    Simple upload processor example that dumps input variables to the logging facility at the DEBUG level.
    """
    def __init__(self, **kwargs):
        super(LoggingProcessor, self).__init__(**kwargs)

    def process(self):
        if logger.isEnabledFor(logging.DEBUG):
            input_context = dict()
            for k, v in self.kwargs.items():
                input_context[k] = v
            logger.debug("%s input context: %s" % (self.__class__.__name__, input_context))

        return {}

