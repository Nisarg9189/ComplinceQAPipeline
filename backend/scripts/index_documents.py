import os
import glob
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

# document loaders and splitters 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# azure components import
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("Indexer")

def index_docs():
    '''
    read the pdfs, chunks them and upload them to Azure AI Search
    '''
    
    # define paths, we look for data folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "../../backend/data")
    
    # check on the env variables
    logger.info("="*60)
    logger.info("Environment Configuration Check: ")
    logger.info(f"AZURE_OPENAI_ENDPOINT : {os.getenv("AZURE_OPENAI_ENDPOINT")}")
    logger.info(f"AZURE_OPENAI_API_VERSION : {os.getenv("AZURE_OPENAI_API_VERSION")}")
    logger.info(f"AZURE_OPENAI_EMBEDDING_DEPLOYMENT : {os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")}")
    logger.info(f"AZURE_SEARCH_ENDPOINT : {os.getenv("AZURE_SEARCH_ENDPOINT")}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME : {os.getenv("AZURE_SEARCH_INDEX_NAME")}")
    logger.info("="*60)
    
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    # validate the required env variables
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_EMBEDDING_API_KEY",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_SEARCH_INDEX_NAME"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing Required Environment Variables : {missing_vars}")
        logger.error("Please check your .env file and ensure all the variables are set")
        return
    
    # initialize embedding model : turns text into vector
    try:
        logger.info("Initializing Azure OpenAI Embeddings ....")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment= os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
            azure_endpoint= os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key= os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY"),
        )
        logger.info("Embeddings model initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize embeddings : {e}")
        logger.error("Please Verify your Azure OpenAI Deployment Name and Endpoint.")
        return
    
    # Initialize Azure AI search
    try:
        logger.info("Initializing Azure AI Search Vector Store ....")
        vector_store = AzureSearch(
            azure_search_endpoint= os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key= os.getenv("AZURE_SEARCH_API_KEY"),
            index_name= index_name,
            embedding_function= embeddings.embed_query
        )
        logger.info(f"Vector Store initialized for index : {index_name}")
            
    except Exception as e:
        logger.error(f"Failed to initialize Azure AI search : {e}")
        logger.error("Please Verify your Azure Search Endpoint and Index Name.")
        return
        
    # find the pdf files
    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning("No PDFs found in the data folder. Please add files...")
    
    logger.info(f"Found {len(pdf_files)} PDFs to process : {[os.path.basename(f) for f in pdf_files]}")
    
    all_splits = []
    
    # process each pdf 
    for pdf_path in pdf_files:
        try:
            logger.info(f"Loading: {os.path.basename(pdf_path)}....")
            loader = PyPDFLoader(pdf_path)
            raw_docs = loader.load()
            
            # chunking strategy
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = 1000,
                chunk_overlap = 200
            )
            
            splits = text_splitter.split_documents(raw_docs)
            for split in splits:
                split.metadata["source"] = os.path.basename(pdf_path)
                
            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks.")
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_path} : {e}")
            
    # upload to azure
    if all_splits:
        logger.info(f"Uploading {len(all_splits)} chunks to Azure AI Search Index '{index_name}'")
        try:
            # Azure Search Access batches Automatically via this method
            vector_store.add_documents(documents = all_splits)
            logger.info("="*60)
            logger.info("Indexing Complete! Knowledge Base is Ready...")
            logger.info(f"Total chunks Indexed : {len(all_splits)}")
            logger.info("="*60)
        except Exception as e:
            logger.error(f"Failed to Upload the documents to azure search: {e}")
            logger.error("Please Check the Azure Search Config... and try again!")
    else:
        logger.warning("No documents were processed.")
        
if __name__ == "__main__":
    index_docs()