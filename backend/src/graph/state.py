import operator
from typing import Any, Annotated, Dict, List, Optional, TypedDict


# schema for single compliance result
# Error Report
class ComplianceIssue(TypedDict):
    category: str 
    description: str # specific details of the violation
    severity: str # CRITICAL | WARNING
    timestamp: Optional[str]
    

# define the global graph state 
# this define the state that gets passed around the agentic workflow
class VideoAuditState(TypedDict):
    '''
    define the data schema for langgraph execution content
    Main container: holds all the information about the audit
    right from the URL to the final report
    '''
    # input parameter
    video_url: str
    video_id: str
    
    # injection and extraction of data
    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]
    transcript: Optional[str] # fully extracted speech-to-text
    ocr_text: List[str]
    
    # analysis results
    # stores the list of all the violations found by AI  
    compliance_results: Annotated[List[ComplianceIssue], operator.add]
    
    # final deliverables
    final_status: str # PASS | FAIL
    final_report: str # markdown format
    
    # system observability
    # errors: API timeout, system level errors
    # list of system level crashes 
    errors: Annotated[List[str], operator.add]