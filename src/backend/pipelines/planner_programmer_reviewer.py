from ..models import Architecture
from .workflow import Workflow


class PlannerProgrammerReviewerPipeline(Workflow):
    def __init__(self, provider):
        super().__init__(provider, Architecture.PLANNER_PROGRAMMER_REVIEWER)