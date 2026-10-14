# Azure Opentelemetry Integration

import os
import logging

from azure.monitor.opentelemetry import configure_azure_monitor

# create a dedicated logger
logger = logging.getLogger("brand-gurdian-telementry")

def setup_telemetry():
    '''
    Initilizes Azure Monitor OpenTelemetry
    Tracks: HTTP requests, database queries, errors, performance metrics
    Send this data to azure monitor
    
    It auto capture every API request
    No need to manually log each endpoint
    '''
    
    # retrive connection string
    connection_string = os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING")
    # check if configured
    if not connection_string:
        logger.warning("No APPLICATION_INSIGHTS_CONNECTION_STRING found, check it out .env or path")
        return
    
    # configure the azure monitor
    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name= "Brand-Gurdian-Tracer"
        )
        logger.info("Azure Monitor Traking Enable and Connected")
    except Exception as e:
        logger.error(f"Failed to initilize azure monitor: {e}")

'''
Why do we use Telemetry?

Without :
API is slow -> No idea which part
How many user today ? No visibility

With :
/audit endpoint average 4.5s (Indexer takes 3.8s)
Error logs show: 12% of audit fail due to the Youtube download errors
Metric Shows: 450 API calls today, 85% success rate
'''
