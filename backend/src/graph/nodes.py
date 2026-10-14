import json
import os
import logging
import re
from typing import Any, Dict

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.messages import SystemMessage, HumanMessage

# import state schema
from backend.src.graph.state import VideoAuditState

# import service
from backend.src.services.video_indexer import VideoIndexerService

# configure logger
logger = logging.getLogger("brand-guardian")
logging.basicConfig(level=logging.INFO)

# Node 1: Indexer
# function responsible for converting video-to-text
def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    '''
    Download the video from the YouTube URL
    Uploads to the Azure Video Indexer
    extracts the insights
    '''
    
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "vid_demo")
    
    logger.info(f"------[Node Indexer] Processing : {video_url}")
    
    local_filename = "temp_audit_video.mp4"
    
    try:
        vi_service = VideoIndexerService()
        
        # download : yt-dlp
        
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise Exception("Please provide a valid YouTube URL for test.")
        
        # upload
        azure_video_id = vi_service.upload_video(local_path, video_name= video_id_input)
        logger.info(f"Upload success. Azure Video ID: {azure_video_id}")
        
        # clean up
        if os.path.exists(local_path):
            os.remove(local_path)
        
        # wait
        raw_insights = vi_service.wait_for_processing(azure_video_id)
        
        # extract
        clean_data = vi_service.extract_data(raw_insights)
        logger.info(f"------[Node Indexer] Extraction complete.")
        
        return clean_data
    
    except Exception as e:
        logger.error(f"Video Indexer Node failed: {e}")
        
        return {
            "errors" : [str(e)],
            "final_status" : "FAIL",
            "transcript" : "",
            "ocr_text" : []
        }
        
# Node 2: Compliance Auditor

def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    '''
    Performs Retrieval Augmented Generation to audit the content - brand video
    '''
    
    logger.info(f"------[Node: Auditor] querying the knowledge base & LLM")
    transcript = state.get("transcript", "")
    
    if not transcript:
        logger.warning("Transcript is empty. Skipping audio content audit.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped because video processing failed (No transcript).",
            
        }
        
    # initialize clients
    
    llm = AzureChatOpenAI(
        azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature = 0.0
    )
    
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
        api_key = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY")
    )
    
    vector_store = AzureSearch(
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function=embeddings.embed_query
    )
    
    # RAG retrieval part
    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {''.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3)
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])
    
    system_prompt = f"""
        You are a senior brand compliance auditor.
        OFFICIAL REGULATORY RULES: {retrieved_rules} "\n"
        INSTRUCTIONS:
        1. Analyze the Transcript and OCR text below.
        2. Identify any potential rule violations.
        3. Return strictly JSON in the following format:
        
        {{
            "compliance_results": [
                {{
                    "category": "Claim Validation"
                    "description": "Explanation of the violation..."
                    "severity": "CRITICAL"
                }}
            ],
            
            "status" : "FAIL",
            "final_report" : "Summary of findings..."
        }}
        
        if no violations found, set "status" to "PASS" and "compliance_results" to [].
        
    """     
    
    user_message = f"""
        VIDEO_METADATA : {state.get("video_metadata", {})}
        TRANSCRIPT : {transcript}
        ON-SCREEN TEXT : {ocr_text}
    """
      
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        
        content = response.content
        
        if "```" in content:
            content = re.search(r"```(?:json)?(.*?)```", content, re.DOTALL).group(1)
        
        audit_data = json.loads(content.strip())
        
        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No Report Generated.")
        }
        
    except Exception as e:
        logger.error(f"Compliance Auditor Node failed: {e}")
        
        # logging the raw response
        logger.error(f"Raw LLM response: {response.content if 'response' in locals() else 'None'}")
        return {
            "errors": [str(e)],
            "final_status" : "FAIL"
        }