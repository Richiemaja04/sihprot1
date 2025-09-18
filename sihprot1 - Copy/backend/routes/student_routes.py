from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from database.db import get_db
from database.model import Timetable, Batch, Subject, Faculty, Classroom
from config import settings

router = APIRouter()

# Pydantic models
class ProgramInfo(BaseModel):
    department: str
    levels: List[str]

class SemesterInfo(BaseModel):
    level: str
    semesters: List[str]

class TimetableEntry(BaseModel):
    subject_name: str
    faculty_name: str
    room_name: str
    room_id: str
    day: str
    hour: int
    subject_type: str
    credits: Optional[int] = None

class StudentTimetableResponse(BaseModel):
    batch_id: str
    department: str
    level: str
    semester: str
    student_count: int
    timetable: List[TimetableEntry]
    weekly_summary: Dict[str, int]
    subjects_summary: List[Dict[str, Any]]

class BatchInfo(BaseModel):
    batch_id: str
    department: str
    level: str
    semester: str
    student_count: int

@router.get("/programs", response_model=List[ProgramInfo])
async def get_available_programs(db: Session = Depends(get_db)):
    """Get all available programs/departments"""
    
    # Get unique departments and their levels
    batches = db.query(Batch).all()
    
    programs_dict = {}
    for batch in batches:
        dept = batch.department
        level = batch.level
        
        if dept not in programs_dict:
            programs_dict[dept] = set()
        programs_dict[dept].add(level)
    
    # Convert to response format
    programs = []
    for dept, levels in programs_dict.items():
        programs.append(ProgramInfo(
            department=dept,
            levels=sorted(list(levels))
        ))
    
    return sorted(programs, key=lambda x: x.department)

@router.get("/semesters/{department}/{level}", response_model=List[str])
async def get_available_semesters(
    department: str,
    level: str,
    db: Session = Depends(get_db)
):
    """Get available semesters for a department and level"""
    
    batches = db.query(Batch).filter(
        Batch.department == department,
        Batch.level == level
    ).all()
    
    if not batches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No semesters found for {department} {level}"
        )
    
    semesters = sorted(list(set(batch.semester for batch in batches)))
    return semesters

@router.get("/batch-info/{department}/{level}/{semester}", response_model=BatchInfo)
async def get_batch_info(
    department: str,
    level: str,
    semester: str,
    db: Session = Depends(get_db)
):
    """Get batch information"""
    
    batch = db.query(Batch).filter(
        Batch.department == department,
        Batch.level == level,
        Batch.semester == semester
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    return BatchInfo(
        batch_id=batch.batch_id,
        department=batch.department,
        level=batch.level,
        semester=batch.semester,
        student_count=batch.student_count
    )

@router.get("/timetable/{department}/{level}/{semester}", response_model=StudentTimetableResponse)
async def get_timetable(
    department: str,
    level: str,
    semester: str,
    db: Session = Depends(get_db)
):
    """Get timetable for a specific batch"""
    
    # Find the batch
    batch = db.query(Batch).filter(
        Batch.department == department,
        Batch.level == level,
        Batch.semester == semester
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    batch_id = batch.batch_id
    
    # Get active timetable entries
    timetable_entries = db.query(Timetable).filter(
        Timetable.batch_id == batch_id,
        Timetable.status == "active"
    ).order_by(Timetable.day, Timetable.hour).all()
    
    if not timetable_entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timetable found for this batch"
        )
    
    # Get additional information for each entry
    timetable = []
    subjects_info = {}
    
    for entry in timetable_entries:
        # Get faculty information
        faculty = db.query(Faculty).filter(
            Faculty.employee_id == entry.faculty_id
        ).first()
        faculty_name = faculty.full_name if faculty else "TBD"
        
        # Get room information
        room = db.query(Classroom).filter(
            Classroom.class_id == entry.room_id
        ).first()
        room_name = room.room_name if room else entry.room_id
        
        # Get subject information
        subject = db.query(Subject).filter(
            Subject.name == entry.subject_name
        ).first()
        
        subject_type = "Theory"
        credits = None
        if subject:
            subject_type = subject.subject_type
            credits = subject.credits
            
            # Collect subjects info for summary
            if entry.subject_name not in subjects_info:
                subjects_info[entry.subject_name] = {
                    'name': entry.subject_name,
                    'type': subject_type,
                    'credits': credits,
                    'hours_per_week': 0,
                    'faculty': faculty_name
                }
            subjects_info[entry.subject_name]['hours_per_week'] += 1
        
        timetable.append(TimetableEntry(
            subject_name=entry.subject_name,
            faculty_name=faculty_name,
            room_name=room_name,
            room_id=entry.room_id,
            day=entry.day,
            hour=entry.hour,
            subject_type=subject_type,
            credits=credits
        ))
    
    # Calculate weekly summary
    weekly_summary = {}
    for day in settings.DAYS:
        weekly_summary[day] = len([e for e in timetable_entries if e.day == day])
    
    # Convert subjects info to list
    subjects_summary = list(subjects_info.values())
    
    return StudentTimetableResponse(
        batch_id=batch_id,
        department=batch.department,
        level=batch.level,
        semester=batch.semester,
        student_count=batch.student_count,
        timetable=timetable,
        weekly_summary=weekly_summary,
        subjects_summary=subjects_summary
    )

@router.get("/timetable-grid/{department}/{level}/{semester}")
async def get_timetable_grid(
    department: str,
    level: str,
    semester: str,
    db: Session = Depends(get_db)
):
    """Get timetable in grid format for visualization"""
    
    # Get timetable data
    timetable_response = await get_timetable(department, level, semester, db)
    
    # Create grid structure
    grid = {}
    for day in settings.DAYS:
        grid[day] = {}
        for hour in range(1, settings.HOURS_PER_DAY + 1):
            grid[day][hour] = None
    
    # Fill the grid
    for entry in timetable_response.timetable:
        grid[entry.day][entry.hour] = {
            'subject_name': entry.subject_name,
            'faculty_name': entry.faculty_name,
            'room_name': entry.room_name,
            'room_id': entry.room_id,
            'subject_type': entry.subject_type,
            'credits': entry.credits
        }
    
    return {
        'batch_info': {
            'batch_id': timetable_response.batch_id,
            'department': timetable_response.department,
            'level': timetable_response.level,
            'semester': timetable_response.semester,
            'student_count': timetable_response.student_count
        },
        'grid': grid,
        'time_slots': [f"Hour {i}" for i in range(1, settings.HOURS_PER_DAY + 1)],
        'days': settings.DAYS,
        'weekly_summary': timetable_response.weekly_summary,
        'subjects_summary': timetable_response.subjects_summary
    }

@router.get("/subjects/{department}/{level}/{semester}")
async def get_batch_subjects(
    department: str,
    level: str,
    semester: str,
    db: Session = Depends(get_db)
):
    """Get all subjects for a batch with detailed information"""
    
    batch = db.query(Batch).filter(
        Batch.department == department,
        Batch.level == level,
        Batch.semester == semester
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Parse subjects from batch
    subject_names = [s.strip() for s in batch.subjects.split(',')]
    
    subjects_details = []
    for subject_name in subject_names:
        subject = db.query(Subject).filter(
            Subject.name == subject_name
        ).first()
        
        if subject:
            # Get faculty teaching this subject
            faculty_entries = db.query(Timetable).filter(
                Timetable.batch_id == batch.batch_id,
                Timetable.subject_name == subject_name,
                Timetable.status == "active"
            ).first()
            
            faculty_name = "TBD"
            if faculty_entries:
                faculty = db.query(Faculty).filter(
                    Faculty.employee_id == faculty_entries.faculty_id
                ).first()
                if faculty:
                    faculty_name = faculty.full_name
            
            # Count hours per week
            hours_per_week = db.query(Timetable).filter(
                Timetable.batch_id == batch.batch_id,
                Timetable.subject_name == subject_name,
                Timetable.status == "active"
            ).count()
            
            subjects_details.append({
                'name': subject.name,
                'code': subject.code,
                'credits': subject.credits,
                'type': subject.subject_type,
                'faculty': faculty_name,
                'hours_per_week': hours_per_week,
                'department': subject.department
            })
    
    return {
        'batch_id': batch.batch_id,
        'total_subjects': len(subjects_details),
        'total_credits': sum(s['credits'] for s in subjects_details),
        'total_hours': sum(s['hours_per_week'] for s in subjects_details),
        'subjects': subjects_details
    }

@router.get("/faculty-info/{faculty_id}")
async def get_faculty_info(
    faculty_id: str,
    db: Session = Depends(get_db)
):
    """Get faculty information (public profile)"""
    
    faculty = db.query(Faculty).filter(
        Faculty.employee_id == faculty_id
    ).first()
    
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty not found"
        )
    
    # Get subjects taught by this faculty
    subjects_taught = [s.strip() for s in faculty.subjects.split(',')]
    
    # Get current teaching load
    current_classes = db.query(Timetable).filter(
        Timetable.faculty_id == faculty_id,
        Timetable.status == "active"
    ).count()
    
    return {
        'employee_id': faculty.employee_id,
        'full_name': faculty.full_name,
        'department': faculty.department,
        'designation': faculty.designation,
        'subjects_taught': subjects_taught,
        'current_teaching_hours': current_classes,
        'max_hours_per_week': faculty.max_hours_per_week
    }

@router.get("/room-info/{room_id}")
async def get_room_info(
    room_id: str,
    db: Session = Depends(get_db)
):
    """Get classroom information"""
    
    room = db.query(Classroom).filter(
        Classroom.class_id == room_id
    ).first()
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    
    # Get current utilization
    current_usage = db.query(Timetable).filter(
        Timetable.room_id == room_id,
        Timetable.status == "active"
    ).count()
    
    max_possible_slots = len(settings.DAYS) * settings.HOURS_PER_DAY
    utilization_percentage = round((current_usage / max_possible_slots) * 100, 1)
    
    return {
        'class_id': room.class_id,
        'room_name': room.room_name,
        'capacity': room.capacity,
        'room_type': room.room_type,
        'building': room.building,
        'floor': room.floor,
        'facilities': room.facilities,
        'current_utilization': {
            'slots_used': current_usage,
            'total_slots': max_possible_slots,
            'utilization_percentage': utilization_percentage
        }
    }

@router.get("/search")
async def search_timetable(
    query: str,
    department: Optional[str] = None,
    level: Optional[str] = None,
    semester: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Search timetable entries"""
    
    # Build query filters
    filters = [Timetable.status == "active"]
    
    if department:
        # Get batches for department
        batch_ids = [b.batch_id for b in db.query(Batch).filter(Batch.department == department)]
        if batch_ids:
            filters.append(Timetable.batch_id.in_(batch_ids))
        else:
            return {"results": [], "total": 0}
    
    if level and department:
        batch_ids = [b.batch_id for b in db.query(Batch).filter(
            Batch.department == department, Batch.level == level
        )]
        if batch_ids:
            filters.append(Timetable.batch_id.in_(batch_ids))
    
    if semester and level and department:
        batch_ids = [b.batch_id for b in db.query(Batch).filter(
            Batch.department == department, 
            Batch.level == level,
            Batch.semester == semester
        )]
        if batch_ids:
            filters.append(Timetable.batch_id.in_(batch_ids))
    
    # Search in various fields
    search_filters = []
    if query:
        search_filters.append(Timetable.subject_name.ilike(f"%{query}%"))
        search_filters.append(Timetable.faculty_id.ilike(f"%{query}%"))
        search_filters.append(Timetable.room_id.ilike(f"%{query}%"))
        search_filters.append(Timetable.batch_id.ilike(f"%{query}%"))
    
    # Combine filters
    if search_filters:
        from sqlalchemy import or_
        filters.append(or_(*search_filters))
    
    # Execute search
    if len(filters) > 1:
        from sqlalchemy import and_
        results = db.query(Timetable).filter(and_(*filters)).limit(50).all()
    else:
        results = db.query(Timetable).filter(filters[0]).limit(50).all()
    
    # Format results
    search_results = []
    for result in results:
        # Get additional info
        faculty = db.query(Faculty).filter(Faculty.employee_id == result.faculty_id).first()
        room = db.query(Classroom).filter(Classroom.class_id == result.room_id).first()
        batch = db.query(Batch).filter(Batch.batch_id == result.batch_id).first()
        
        search_results.append({
            'batch_id': result.batch_id,
            'batch_info': {
                'department': batch.department if batch else 'Unknown',
                'level': batch.level if batch else 'Unknown',
                'semester': batch.semester if batch else 'Unknown'
            },
            'subject_name': result.subject_name,
            'faculty_name': faculty.full_name if faculty else result.faculty_id,
            'room_name': room.room_name if room else result.room_id,
            'day': result.day,
            'hour': result.hour,
            'schedule': f"{result.day} Hour {result.hour}"
        })
    
    return {
        'results': search_results,
        'total': len(search_results),
        'query': query,
        'filters': {
            'department': department,
            'level': level,
            'semester': semester
        }
    }

@router.get("/stats")
async def get_system_stats(db: Session = Depends(get_db)):
    """Get public system statistics"""
    
    # Get basic counts
    total_batches = db.query(Batch).count()
    total_subjects = db.query(Subject).count()
    total_faculty = db.query(Faculty).count()
    total_rooms = db.query(Classroom).count()
    active_classes = db.query(Timetable).filter(Timetable.status == "active").count()
    
    # Get department statistics
    departments = {}
    batches = db.query(Batch).all()
    for batch in batches:
        dept = batch.department
        if dept not in departments:
            departments[dept] = {
                'batches': 0,
                'total_students': 0
            }
        departments[dept]['batches'] += 1
        departments[dept]['total_students'] += batch.student_count
    
    return {
        'overview': {
            'total_batches': total_batches,
            'total_subjects': total_subjects,
            'total_faculty': total_faculty,
            'total_rooms': total_rooms,
            'active_classes': active_classes
        },
        'departments': departments,
        'system_info': {
            'days_per_week': len(settings.DAYS),
            'hours_per_day': settings.HOURS_PER_DAY,
            'total_time_slots': len(settings.DAYS) * settings.HOURS_PER_DAY
        }
    }