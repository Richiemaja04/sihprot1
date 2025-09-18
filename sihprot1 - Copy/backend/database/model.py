from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    user_type = Column(String, nullable=False)  # 'admin', 'teacher', 'student'
    employee_id = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=False)
    department = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, unique=True, index=True, nullable=False)
    department = Column(String, nullable=False)
    level = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    student_count = Column(Integer, nullable=False)
    subjects = Column(Text)  # Comma-separated subject names
    created_at = Column(DateTime, server_default=func.now())

class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, index=True)
    credits = Column(Integer, nullable=False)
    subject_type = Column(String, nullable=False)  # 'Theory', 'Lab', 'Practical'
    department = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class Faculty(Base):
    __tablename__ = "faculty"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    department = Column(String)
    designation = Column(String)
    subjects = Column(Text)  # Comma-separated subject names
    max_hours_per_week = Column(Integer, default=20)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Classroom(Base):
    __tablename__ = "classrooms"
    
    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(String, unique=True, index=True, nullable=False)
    room_name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String, nullable=False)  # 'Laboratory', 'Lecture Hall', 'Classroom'
    building = Column(String)
    floor = Column(String)
    facilities = Column(Text)  # JSON string of facilities
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Timetable(Base):
    __tablename__ = "timetables"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String, unique=True, index=True, nullable=False)
    batch_id = Column(String, nullable=False)
    subject_name = Column(String, nullable=False)
    faculty_id = Column(String, nullable=False)
    room_id = Column(String, nullable=False)
    day = Column(String, nullable=False)
    hour = Column(Integer, nullable=False)
    week_type = Column(String, default="all")  # 'all', 'odd', 'even'
    status = Column(String, default="active")  # 'active', 'draft', 'cancelled'
    created_by = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class TimetableVersion(Base):
    __tablename__ = "timetable_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    fitness_score = Column(Float)
    generation_params = Column(JSON)  # GA parameters used
    is_approved = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    created_by = Column(String)
    approved_by = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    approved_at = Column(DateTime)

class OptimizationLog(Base):
    __tablename__ = "optimization_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, index=True, nullable=False)
    version_id = Column(String, ForeignKey('timetable_versions.version_id'))
    operation_type = Column(String, nullable=False)  # 'initial', 'reoptimize', 'substitute'
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed'
    progress = Column(Integer, default=0)
    fitness_scores = Column(JSON)  # List of fitness scores per generation
    execution_time = Column(Float)
    error_message = Column(Text)
    parameters = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

class TeacherLeave(Base):
    __tablename__ = "teacher_leaves"
    
    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    leave_type = Column(String, nullable=False)  # 'sick', 'personal', 'emergency'
    reason = Column(Text)
    substitute_faculty_id = Column(String)
    status = Column(String, default="pending")  # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, server_default=func.now())
    approved_at = Column(DateTime)

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(Text)
    updated_by = Column(String)
    updated_at = Column(DateTime, onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    action = Column(String, nullable=False)
    entity_type = Column(String)
    entity_id = Column(String)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime, server_default=func.now())