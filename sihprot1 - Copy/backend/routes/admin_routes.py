from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import os
import uuid
import json
from datetime import datetime

from database.db import get_db
from database.model import (
    User, Batch, Subject, Faculty, Classroom, 
    TimetableVersion, Timetable, OptimizationLog
)
from utils.auth import require_admin
from utils.file_parser import parse_uploaded_file, validate_csv_structure
from services.ga_engine import TimetableOptimizer
from utils.websocket_manager import websocket_manager
from config import settings

router = APIRouter()

# Pydantic models
class DataUploadResponse(BaseModel):
    message: str
    records_processed: int
    file_type: str

class TimetableGenerationRequest(BaseModel):
    name: str
    description: Optional[str] = None
    ga_parameters: Optional[Dict[str, Any]] = None

class TimetableVersionResponse(BaseModel):
    version_id: str
    name: str
    description: Optional[str]
    fitness_score: Optional[float]
    is_approved: bool
    is_published: bool
    created_at: datetime

class OptimizationStatus(BaseModel):
    run_id: str
    status: str
    progress: int
    current_generation: Optional[int] = None
    best_fitness: Optional[float] = None
    estimated_time_remaining: Optional[int] = None

@router.post("/upload-batches", response_model=DataUploadResponse)
async def upload_batches(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Upload batches CSV/Excel file"""
    try:
        # Validate file
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV and Excel files are supported"
            )
        
        # Parse file
        df = await parse_uploaded_file(file)
        
        # Validate structure
        required_columns = ['department', 'level', 'semester', 'student_count', 'subjects']
        validate_csv_structure(df, required_columns, 'batches')
        
        # Clear existing data
        db.query(Batch).delete()
        
        # Insert new data
        records_processed = 0
        for _, row in df.iterrows():
            batch = Batch(
                batch_id=f"{row['department']}-{row['level']}-{row['semester']}",
                department=row['department'],
                level=row['level'],
                semester=row['semester'],
                student_count=int(row['student_count']),
                subjects=row['subjects']
            )
            db.add(batch)
            records_processed += 1
        
        db.commit()
        
        return DataUploadResponse(
            message="Batches uploaded successfully",
            records_processed=records_processed,
            file_type="batches"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )

@router.post("/upload-subjects", response_model=DataUploadResponse)
async def upload_subjects(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Upload subjects CSV/Excel file"""
    try:
        df = await parse_uploaded_file(file)
        required_columns = ['name', 'code', 'credits', 'type']
        validate_csv_structure(df, required_columns, 'subjects')
        
        db.query(Subject).delete()
        
        records_processed = 0
        for _, row in df.iterrows():
            subject = Subject(
                name=row['name'],
                code=row.get('code', ''),
                credits=int(row['credits']),
                subject_type=row['type'],
                department=row.get('department', '')
            )
            db.add(subject)
            records_processed += 1
        
        db.commit()
        
        return DataUploadResponse(
            message="Subjects uploaded successfully",
            records_processed=records_processed,
            file_type="subjects"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )

@router.post("/upload-faculty", response_model=DataUploadResponse)
async def upload_faculty(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Upload faculty CSV/Excel file"""
    try:
        df = await parse_uploaded_file(file)
        required_columns = ['Employee ID', 'full_name', 'email', 'subject_name']
        validate_csv_structure(df, required_columns, 'faculty')
        
        db.query(Faculty).delete()
        
        records_processed = 0
        for _, row in df.iterrows():
            faculty = Faculty(
                employee_id=row['Employee ID'],
                full_name=row['full_name'],
                email=row['email'],
                department=row.get('department', ''),
                designation=row.get('designation', ''),
                subjects=row['subject_name'],
                max_hours_per_week=int(row.get('max_hours_per_week', 20))
            )
            db.add(faculty)
            records_processed += 1
        
        db.commit()
        
        return DataUploadResponse(
            message="Faculty uploaded successfully",
            records_processed=records_processed,
            file_type="faculty"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )

@router.post("/upload-classrooms", response_model=DataUploadResponse)
async def upload_classrooms(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Upload classrooms CSV/Excel file"""
    try:
        df = await parse_uploaded_file(file)
        required_columns = ['Class_ID', 'room_name', 'Capacity', 'Room_Type']
        validate_csv_structure(df, required_columns, 'classrooms')
        
        db.query(Classroom).delete()
        
        records_processed = 0
        for _, row in df.iterrows():
            classroom = Classroom(
                class_id=row['Class_ID'],
                room_name=row['room_name'],
                capacity=int(row['Capacity']),
                room_type=row['Room_Type'],
                building=row.get('building', ''),
                floor=row.get('floor', ''),
                facilities=row.get('facilities', '')
            )
            db.add(classroom)
            records_processed += 1
        
        db.commit()
        
        return DataUploadResponse(
            message="Classrooms uploaded successfully",
            records_processed=records_processed,
            file_type="classrooms"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        )

async def run_timetable_generation(
    request: TimetableGenerationRequest,
    user_id: str,
    db: Session
):
    """Background task for timetable generation"""
    try:
        # Load data from database
        batches = pd.read_sql(
            db.query(Batch).statement, db.bind
        )
        subjects = pd.read_sql(
            db.query(Subject).statement, db.bind
        )
        faculty = pd.read_sql(
            db.query(Faculty).statement, db.bind
        )
        classrooms = pd.read_sql(
            db.query(Classroom).statement, db.bind
        )

        # Initialize optimizer
        optimizer = TimetableOptimizer()

        # Generate multiple solutions
        solutions = optimizer.generate_multiple_solutions(
            batches, classrooms, faculty, subjects, num_solutions=3, db=db # Pass db here
        )
        
        # Save solutions as different versions
        for i, (genes, fitness) in enumerate(solutions):
            version_id = str(uuid.uuid4())
            
            # Create timetable version
            version = TimetableVersion(
                version_id=version_id,
                name=f"{request.name} - Solution {i+1}",
                description=f"Generated solution with fitness score: {fitness:.4f}",
                fitness_score=fitness,
                generation_params=request.ga_parameters or {},
                created_by=user_id
            )
            db.add(version)
            
            # Save individual timetable entries
            for gene in genes:
                timetable_entry = Timetable(
                    version_id=version_id,
                    batch_id=gene.batch_id,
                    subject_name=gene.subject_name,
                    faculty_id=gene.faculty_id,
                    room_id=gene.room_id,
                    day=gene.day,
                    hour=gene.hour,
                    created_by=user_id
                )
                db.add(timetable_entry)
        
        db.commit()
        
        # Notify via WebSocket
        await websocket_manager.broadcast_to_admins({
            "type": "generation_complete",
            "message": "Timetable generation completed successfully",
            "solutions_count": len(solutions),
            "best_fitness": max(s[1] for s in solutions)
        })
        
    except Exception as e:
        # Update optimization log with error
        await websocket_manager.broadcast_to_admins({
            "type": "generation_error",
            "message": f"Timetable generation failed: {str(e)}"
        })
        raise

@router.post("/generate-timetables")
async def generate_timetables(
    request: TimetableGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Generate timetables using GA algorithm"""
    
    # Validate that all required data exists
    batch_count = db.query(Batch).count()
    subject_count = db.query(Subject).count()
    faculty_count = db.query(Faculty).count()
    classroom_count = db.query(Classroom).count()
    
    if not all([batch_count, subject_count, faculty_count, classroom_count]):
        missing = []
        if not batch_count: missing.append("batches")
        if not subject_count: missing.append("subjects")
        if not faculty_count: missing.append("faculty")
        if not classroom_count: missing.append("classrooms")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required data: {', '.join(missing)}"
        )
    
    # Add background task
    background_tasks.add_task(
        run_timetable_generation, request, current_user.employee_id, db
    )
    
    return {"message": "Timetable generation started", "status": "processing"}

@router.get("/timetable-versions", response_model=List[TimetableVersionResponse])
async def get_timetable_versions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all timetable versions"""
    versions = db.query(TimetableVersion).order_by(
        TimetableVersion.created_at.desc()
    ).all()
    
    return [
        TimetableVersionResponse(
            version_id=v.version_id,
            name=v.name,
            description=v.description,
            fitness_score=v.fitness_score,
            is_approved=v.is_approved,
            is_published=v.is_published,
            created_at=v.created_at
        ) for v in versions
    ]

@router.post("/approve-timetable/{version_id}")
async def approve_timetable(
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve a timetable version"""
    version = db.query(TimetableVersion).filter(
        TimetableVersion.version_id == version_id
    ).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable version not found"
        )
    
    # Disapprove all other versions
    db.query(TimetableVersion).update({"is_approved": False})
    
    # Approve this version
    version.is_approved = True
    version.approved_by = current_user.employee_id
    version.approved_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Timetable approved successfully"}

@router.post("/publish-timetable/{version_id}")
async def publish_timetable(
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Publish an approved timetable"""
    version = db.query(TimetableVersion).filter(
        TimetableVersion.version_id == version_id,
        TimetableVersion.is_approved == True
    ).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved timetable version not found"
        )
    
    # Unpublish all other versions
    db.query(TimetableVersion).update({"is_published": False})
    
    # Publish this version
    version.is_published = True
    
    # Update timetable entries status
    db.query(Timetable).filter(
        Timetable.version_id == version_id
    ).update({"status": "active"})
    
    # Deactivate other timetable entries
    db.query(Timetable).filter(
        Timetable.version_id != version_id
    ).update({"status": "inactive"})
    
    db.commit()
    
    # Broadcast to all users
    await websocket_manager.broadcast_to_all({
        "type": "timetable_published",
        "message": "New timetable has been published",
        "version_id": version_id
    })
    
    return {"message": "Timetable published successfully"}

@router.get("/optimization-logs")
async def get_optimization_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get optimization logs"""
    logs = db.query(OptimizationLog).order_by(
        OptimizationLog.created_at.desc()
    ).limit(50).all()
    
    return [
        {
            "run_id": log.run_id,
            "operation_type": log.operation_type,
            "status": log.status,
            "fitness_scores": log.fitness_scores,
            "execution_time": log.execution_time,
            "created_at": log.created_at,
            "completed_at": log.completed_at
        } for log in logs
    ]

@router.delete("/timetable-version/{version_id}")
async def delete_timetable_version(
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a timetable version"""
    version = db.query(TimetableVersion).filter(
        TimetableVersion.version_id == version_id
    ).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable version not found"
        )
    
    if version.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete published timetable"
        )
    
    # Delete timetable entries
    db.query(Timetable).filter(
        Timetable.version_id == version_id
    ).delete()
    
    # Delete version
    db.delete(version)
    db.commit()
    
    return {"message": "Timetable version deleted successfully"}

@router.get("/system-stats")
async def get_system_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system statistics"""
    stats = {
        "batches": db.query(Batch).count(),
        "subjects": db.query(Subject).count(),
        "faculty": db.query(Faculty).count(),
        "classrooms": db.query(Classroom).count(),
        "timetable_versions": db.query(TimetableVersion).count(),
        "published_versions": db.query(TimetableVersion).filter(
            TimetableVersion.is_published == True
        ).count(),
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(
            User.is_active == True
        ).count()
    }
    
    return stats