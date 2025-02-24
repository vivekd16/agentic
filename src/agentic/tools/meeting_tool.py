from typing import Any, Callable, Optional, Dict
import requests
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import json, os

from .base import BaseAgenticTool
from .registry import tool_registry, Dependency, ConfigRequirement
from agentic.agentic_secrets import agentic_secrets
from agentic.common import RunContext
import logging  

# Configure logging  
logging.basicConfig(  
    level=logging.INFO,  # Set the minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)  
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Set the log format  
    datefmt="%Y-%m-%d %H:%M:%S",  # Set the date format  
)  
logger = logging.getLogger(__name__)

Base = declarative_base()

class Meeting(Base):
    __tablename__ = 'meetings'
    
    id = Column(String, primary_key=True)
    name = Column(String)
    url = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    duration = Column(Integer)
    transcript = Column(Text)
    summary = Column(Text)
    attendees = Column(Text)
    status = Column(String)
    recording_url = Column(String)

@tool_registry.register(
    name="MeetingTool",
    description="A tool for managing video meetings, recording transcripts, and generating summaries",
    dependencies=[
        Dependency("langchain-openai", type="pip", version="0.3.6"),
        Dependency("langchain-chroma", type="pip", version="0.2.2")
    ],
    config_requirements=[
        ConfigRequirement("MEETINGBAAS_API_KEY", description="MEETINGBAAS API key", required=True),
        ConfigRequirement("OPENAI_API_KEY", description="OpenAI API key", required=True),
    ],
)


class MEETING_BAAS_Tool(BaseAgenticTool):
    openai_api_key: str = ""
    meeting_baas_api_key: str = ""

    def __init__(self, webhook_addr = ""):
        self.db_path = "meetings.db"
        # Do not initialize engine here, will be done when needed.
        self.Session = None
        self._engine = None
        self._initialized = False
        self._vector_store = None
        self._rag_initialized = False
        self.webhook_addr = webhook_addr

    def get_tools(self) -> list[Callable]:
        return [
            self.join_meeting,
            self.get_transcript,
            self.get_summary,
            self.list_meetings,
            self.get_meeting_info,
            self.answer_question,
            self.process_webhook
        ]

    def _initialize_rag(self):
        """Initialize the RAG components"""
        if not self._rag_initialized:
            self.openai_api_key = agentic_secrets.get_required_secret("OPENAI_API_KEY")
            self._vector_store = Chroma(
                collection_name="meeting_summaries",
                embedding_function=OpenAIEmbeddings(openai_api_key=self.openai_api_key)
            )
            self._rag_initialized = True

    def _get_session(self):
        """Lazy initialization of the database session."""
        if not self._initialized:
            self._engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(self._engine)
            self.Session = sessionmaker(bind=self._engine)
            self._initialized = True
        return self.Session()

    def __getstate__(self):
        """Custom serialization for Ray."""
        state = self.__dict__.copy()
        # Remove unpicklable entries
        state['Session'] = None
        state['_engine'] = None
        state['_initialized'] = False
        state['_vector_store'] = None
        state['_rag_initialized'] = False
        # Don't pickle API keys
        state['openai_api_key'] = ""
        state['meeting_baas_api_key'] = ""
        return state

    def __setstate__(self, state):
        """Custom deserialization for Ray."""
        self.__dict__.update(state)

    def join_meeting(
        self, 
        meeting_url: str,
        run_context: RunContext,
        bot_name: str = "Meeting Assistant"
    ) -> dict:
        """Join a video meeting and start recording"""
        self.meeting_baas_api_key = agentic_secrets.get_required_secret("MEETING_BAAS_API_KEY")
        try:
            headers = {
                "Content-Type": "application/json",
                "x-meeting-baas-api-key": self.meeting_baas_api_key
            }
            run_context.api_endpoint = self.webhook_addr
            webhook_url = run_context.get_webhook_endpoint("process_webhook")

            data = {
                "meeting_url": meeting_url,
                "bot_name": bot_name,
                "bot_image": None,
                "entry_message": "This is the Supercog meeting bot, sent by supercog support", 
                "recording_mode": "audio_only",
                "reserved": False,
                "speech_to_text": {
                    "provider": "Default"
                },
                "automatic_leave": {
                    "waiting_room_timeout": 600
                },
                "webhook_url": webhook_url
            }
            
            response = requests.post(
                "https://api.meetingbaas.com/bots",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                meeting_data = response.json()
                
                # Store meeting in database
                session = self._get_session()
                meeting = Meeting(
                    id=meeting_data["bot_id"],
                    url=meeting_url,
                    start_time=datetime.now().isoformat(),
                    status="joining"
                )
                session.add(meeting)
                session.commit()
                
                return {
                    "status": "success",
                    "meeting_id": meeting_data["bot_id"],
                    "message": "Bot is joining the meeting"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to join meeting: {response.text}"
                }
                
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Error joining meeting: {str(e)}"
            }

    def get_transcript(self, meeting_id: str) -> dict:  
        """Get the transcript for a specific meeting and save it to the database if not already present"""  
        try:  
            session = self._get_session()  
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()  
            
            if not meeting:  
                return {"status": "error", "message": "Meeting not found"}  
            
            if not meeting.transcript:  
                # Fetch transcript from MeetingBaaS API  
                if not self.meeting_baas_api_key:  
                    self.meeting_baas_api_key = agentic_secrets.get_required_secret("MEETING_BAAS_API_KEY")  
                    
                headers = {"x-meeting-baas-api-key": self.meeting_baas_api_key}  
                response = requests.get(  
                    f"https://api.meetingbaas.com/bots/meeting_data",  
                    headers=headers,  
                    params={"bot_id": meeting_id}  
                )  
                
                if response.status_code == 200:  
                    data = response.json()  
                    transcripts = json.dumps(data.get("bot_data", {}).get("transcripts", []))  
                    meeting.transcript = transcripts  
                    session.commit()  
                else:  
                    return {"status": "error", "message": f"Failed to fetch transcript: {response.text}"}  
            
            return {"status": "success", "transcript": json.loads(meeting.transcript)}  
        
        except Exception as e:  
            return {"status": "error", "message": f"Error fetching transcript: {str(e)}"}  


    def _ensure_openai_initialized(self):
        """Ensure OpenAI client is properly initialized"""
        if not self.openai_api_key:
            self.openai_api_key = agentic_secrets.get_required_secret("OPENAI_API_KEY")
            openai.api_key = self.openai_api_key

    def get_summary(self, meeting_id: str) -> dict:
        """Generate a detailed summary of the meeting"""
        try:
            transcript_result = self.get_transcript(meeting_id)
            if transcript_result["status"] == "error":
                return transcript_result
                
            transcript = transcript_result["transcript"]
            
            formatted_transcript = ""
            for entry in transcript:
                if entry.get('words'):
                    words = ' '.join([word['text'] for word in entry['words']])
                    speaker = entry['speaker']
                    formatted_transcript += f"{speaker}: {words}\n"

            summary_prompt = """
            Please provide a detailed summary of this meeting transcript. Include:
            1. Main topics discussed
            2. Key decisions made
            3. Action items and assignments
            4. Important points raised by each participant
            5. Timeline of major discussion points
            Format the summary in clear sections with headers.
            """
            
            self._ensure_openai_initialized()
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": summary_prompt},
                          {"role": "user", "content": formatted_transcript}],
                temperature=0
            )
            
            detailed_summary = response.choices[0].message.content
            
            session = self._get_session()
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()
            if meeting:
                meeting.summary = detailed_summary
                session.commit()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            chunks = text_splitter.split_text(detailed_summary)
            
            # Initialize RAG if needed
            self._initialize_rag()
            self._vector_store.add_texts(
                texts=chunks,
                metadatas=[{"meeting_id": meeting_id, "type": "summary"}] * len(chunks)
            )
            
            return {
                "status": "success",
                "summary": detailed_summary
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error generating summary: {str(e)}"
            }

    def list_meetings(self) -> dict:
        """List all recorded meetings"""
        try:
            session = self._get_session()
            meetings = session.query(Meeting).all()
            
            meeting_list = []
            for meeting in meetings:
                meeting_list.append({
                    "id": meeting.id,
                    "name": meeting.name,
                    "start_time": meeting.start_time,
                    "end_time": meeting.end_time,
                    "duration": meeting.duration,
                    "status": meeting.status
                })
                
            return {
                "status": "success",
                "meetings": meeting_list
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error listing meetings: {str(e)}"
            }

    def get_meeting_info(self, meeting_id: str) -> dict:  
        """  
        Retrieve detailed information about a specific meeting.  
        Includes metadata, transcript, and summary if available.  
        """  
        try:  
            # Establish a database session  
            session = self._get_session()  
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()  
            
            # Check whether the meeting exists  
            if not meeting:  
                return {"status": "error", "message": f"Meeting with ID '{meeting_id}' not found"}  

            # Fetch meeting metadata  
            meeting_info = {  
                "id": meeting.id,  
                "name": meeting.name or "Untitled",  
                "start_time": meeting.start_time,  
                "end_time": meeting.end_time,  
                "duration": str(timedelta(seconds=meeting.duration)) if meeting.duration else "Unknown",  
                "status": meeting.status,  
            }  

            # Fetch transcript  
            transcript_result = self.get_transcript(meeting_id)  
            if transcript_result["status"] == "success":  
                meeting_info["transcript"] = transcript_result["transcript"]  
            else:  
                meeting_info["transcript_error"] = transcript_result["message"]  

            # Fetch summary  
            summary_result = self.get_summary(meeting_id)  
            if summary_result["status"] == "success":  
                meeting_info["summary"] = summary_result["summary"]  
            else:  
                meeting_info["summary_error"] = summary_result["message"]  

            return {"status": "success", "meeting_info": meeting_info}  

        except Exception as e:  
            return {"status": "error", "message": f"Error fetching meeting info: {str(e)}"}

    def answer_question(self, meeting_id: str, question: str) -> dict:
        """Answer a question related to a specific meeting"""
        try:
            meeting_summary_result = self.get_summary(meeting_id)
            if meeting_summary_result["status"] == "error":
                return meeting_summary_result
                
            summary = meeting_summary_result["summary"]
            
            self._ensure_openai_initialized()
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Question: {question}\n\nSummary: {summary}"}
                ],
                temperature=0.5
            )
            
            return {
                "status": "success",
                "answer": response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error answering question: {str(e)}"
            }

    def process_webhook(self, webhook_data: dict) -> dict:  
        """  
        Process webhook data received from MeetingBaaS.  

        This function parses the webhook data and updates the meeting object in the database.  
        
        Args:  
            webhook_data (dict): The webhook data received from MeetingBaaS.  
            
        Returns:  
            dict: A dictionary containing the processing status and any updated meeting information.  
        """  
        session = None  
        try:  
            session = self._get_session()  
            meeting_id = webhook_data.get("bot_id")  

            if not meeting_id:  
                return {  
                    "status": "error",  
                    "message": "No bot_id found in webhook data"  
                }  

            # Fetch the meeting from the database.  
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()  
            if not meeting:  
                return {  
                    "status": "error",  
                    "message": f"Meeting with ID {meeting_id} not found"  
                }  

            event_type = webhook_data.get("event", "unknown_event")  
            logger.info(f"Processing webhook for Meeting ID: {meeting_id}, Event: {event_type}")  

            # Detailed handling logic based on event type.  
            if event_type == "complete":  
                logger.info(f"Webhook indicates meeting '{meeting_id}' is complete")  

                # Update recording URL and transcript from bot data.  
                bot_data = webhook_data.get("bot_data", {})  
                if bot_data:  
                    # Save the transcript.  
                    meeting.transcript = json.dumps(bot_data.get("transcripts", []))  

                    # Save the recording URL (if available).  
                    meeting.recording_url = bot_data.get("mp4", None)  

                # Set end time and calculate duration.  
                meeting.end_time = datetime.now().isoformat()  
                if meeting.start_time:  
                    start_dt = datetime.fromisoformat(meeting.start_time)  
                    end_dt = datetime.fromisoformat(meeting.end_time)  
                    meeting.duration = int((end_dt - start_dt).total_seconds())  
                
                # Fetch or generate a summary if needed.  
                if not meeting.summary and meeting.transcript:  
                    summary_result = self.get_summary(meeting_id)  
                    if summary_result.get("status") == "success":  
                        meeting.summary = summary_result["summary"]  

                meeting.status = "completed"  

            elif event_type == "failed":  
                error_code = webhook_data.get("error", "UnknownError")  
                logger.warning(f"Webhook indicates meeting '{meeting_id}' failed with error: {error_code}")  
                meeting.status = "failed"  
            
            elif event_type == "bot.status_change":  
                status_code = webhook_data.get("status", {}).get("code", "unknown_status")  
                logger.info(f"Bot status changed for meeting '{meeting_id}', new status: {status_code}")  
                meeting.status = status_code  
            
            else:  
                logger.warning(f"Unhandled webhook event type: {event_type} for meeting: {meeting_id}")  

            # Commit all updates to the database.  
            session.commit()  

            return {  
                "status": "success",  
                "message": f"Webhook processed successfully for event '{event_type}'",  
                "meeting_id": meeting_id  
            }  

        except Exception as e:  
            logger.error(f"Error processing webhook: {str(e)}")  
            return {  
                "status": "error",  
                "message": f"Error processing webhook: {str(e)}",  
                "meeting_id": webhook_data.get("bot_id", "unknown")  
            }  
        finally:  
            if session:  
                session.close()
