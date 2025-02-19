from typing import Any, Callable, Optional, Dict
import requests
from datetime import datetime, timedelta
from pydantic import BaseModel
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
        Dependency("langchain-chromadb", type="pip", version="0.2.2")
    ],
    config_requirements=[
        ConfigRequirement("MEETINGBAAS_API_KEY", description="MEETINGBAAS API key", required=True),
        ConfigRequirement("OPENAI_API_KEY", description="OpenAI API key", required=True),
    ],
)
class MEETING_BAAS_Tool(BaseAgenticTool):
    openai_api_key: str = ""
    meeting_baas_api_key: str = ""

    def __init__(self):
        self.db_path = "meetings.db"
        # Do not initialize engine here, will be done when needed.
        self.Session = None

    def get_tools(self) -> list[Callable]:
        return [
            self.join_meeting,
            self.get_transcript,
            self.get_summary,
            self.list_meetings,
            self.get_meeting_status,
            self.answer_question
        ]

    def _initialize_rag(self):
        """Initialize the RAG components"""
        self.openai_api_key = agentic_secrets.get_required_secret("OPENAI_API_KEY")
        self.vector_store = Chroma(
            collection_name="meeting_summaries",
            embedding_function=OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        )

    def _get_session(self):
        """Lazy initialization of the database session."""
        if self.Session is None:
            engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(engine)
            self.Session = sessionmaker(bind=engine)
        return self.Session()

    def join_meeting(
        self, 
        meeting_url: str,
        bot_name: str = "Meeting Assistant"
    ) -> dict:
        """Join a video meeting and start recording"""
        self.meeting_baas_api_key = agentic_secrets.get_required_secret("MEETING_BAAS_API_KEY")
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.meeting_baas_api_key}"
            }
            
            data = {
                "meeting_url": meeting_url,
                "bot_name": bot_name,
                "recording_mode": "audio_video"
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
        """Get the transcript for a specific meeting"""
        try:
            session = self._get_session()
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()
            
            if not meeting:
                return {"status": "error", "message": "Meeting not found"}
                
            if not meeting.transcript:
                headers = {"Authorization": f"Bearer {self.meeting_baas_api_key}"}
                response = requests.get(
                    f"https://api.meetingbaas.com/bots/meeting_data",
                    headers=headers,
                    params={"bot_id": meeting_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    meeting.transcript = json.dumps(data["bot_data"]["transcripts"])
                    session.commit()
                else:
                    return {
                        "status": "error",
                        "message": "Failed to fetch transcript from API"
                    }
            
            return {
                "status": "success",
                "transcript": json.loads(meeting.transcript)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting transcript: {str(e)}"
            }

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
            
            response = openai.ChatCompletion.acreate(
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
            
            self.vector_store.add_texts(
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

    def get_meeting_status(self, meeting_id: str) -> dict:
        """Get the current status of a meeting"""
        try:
            session = self._get_session()
            meeting = session.query(Meeting).filter_by(id=meeting_id).first()
            
            if not meeting:
                return {"status": "error", "message": "Meeting not found"}
                
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                f"https://api.meetingbaas.com/bots/{meeting_id}/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status_data = response.json()
                meeting.status = status_data["status"]
                session.commit()
                
                return {
                    "status": "success",
                    "meeting_status": status_data["status"]
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to fetch meeting status: {response.text}"
                }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Error getting meeting status: {str(e)}"
            }

    def answer_question(self, meeting_id: str, question: str) -> dict:
        """Answer a question related to a specific meeting"""
        try:
            meeting_summary_result = self.get_summary(meeting_id)
            if meeting_summary_result["status"] == "error":
                return meeting_summary_result
                
            summary = meeting_summary_result["summary"]
            
            response = openai.ChatCompletion.acreate(
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
