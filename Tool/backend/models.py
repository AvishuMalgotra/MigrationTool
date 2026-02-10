from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    primary_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("AssessmentJob", back_populates="tenant")

class AssessmentJob(Base):
    __tablename__ = "assessment_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    inventory_snapshot = Column(JSON, nullable=True)
    blockers = Column(JSON, nullable=True)
    ai_generated_summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="jobs")
    migration_plan = relationship("MigrationPlan", back_populates="job", uselist=False)

class MigrationPlan(Base):
    __tablename__ = "migration_plans"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("assessment_jobs.id"))
    ordered_batches = Column(JSON, nullable=True)
    execution_log = Column(JSON, nullable=True)
    status = Column(String, default="DRAFT") # DRAFT, IN_PROGRESS, COMPLETED, FAILED
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("AssessmentJob", back_populates="migration_plan")
