from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doc_id = Column(String(64), unique=True, index=True, nullable=False)
    client_id = Column(String(64), unique=True, index=True, nullable=False)

    # File info
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, xlsx, csv, txt
    file_size = Column(Integer, default=0)  # bytes

    # Extracted account info
    bank_name = Column(String(100), default="")
    account_holder_name = Column(String(255), default="")
    account_number = Column(String(50), default="")
    ifsc_code = Column(String(20), default="")
    statement_period_from = Column(String(20), default="")
    statement_period_to = Column(String(20), default="")

    # Processing status
    status = Column(String(20), default=DocumentStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    password_used = Column(String(100), nullable=True)  # for password-protected PDFs

    # Analysis data (stored as JSON text)
    raw_extraction_json = Column(Text, nullable=True)  # statement-result equivalent
    analysis_json = Column(Text, nullable=True)  # analysis-json equivalent

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Document {self.doc_id} - {self.filename} ({self.status})>"
