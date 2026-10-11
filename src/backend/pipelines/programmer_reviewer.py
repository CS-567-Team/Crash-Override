from ..models import Architecture
from .workflow import Workflow


class ProgrammerReviewerPipeline(Workflow):
    def __init__(self, provider):
        super().__init__(provider, Architecture.PROGRAMMER_REVIEWER)
