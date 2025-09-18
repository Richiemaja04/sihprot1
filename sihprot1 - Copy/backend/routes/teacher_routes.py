from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from database.db import get_db
from database.model import User, Timetable, TeacherLeave, Faculty
from utils.auth import require_teacher, get_current_user
from utils.websocket_manager import websocket_manager
from services.optimization import handle_teacher_leave_optimization

router = APIRouter()

# Pydantic models
class TimetableEntry(BaseModel):
    id: int
    batch_id: str
    subject_name: str
    room_id: str
    day: str
    hour: int
    week_type: str
    status: str

class TeacherTimetableResponse(BaseModel):
    faculty_id: str
    faculty_name: str
    total_hours: int
    timetable: List[TimetableEntry]
    workload_distribution: Dict[str, int]

class LeaveRequest(BaseModel):
    start_date: date
    end_date: date
    leave_type: str  # 'sick', 'personal', 'emergency'
    reason: str
    substitute_faculty_id: Optional[str] = None

class LeaveResponse(BaseModel):
    id: int
    start_date: date
    end_date: date
    leave_type: str
    reason: str
    substitute_faculty_id: Optional[str]
    status: str
    created_at: datetime
    approved_at: Optional[datetime]

class WorkloadSummary(BaseModel):
    total_hours_per_week: int
    hours_by_day: Dict[str, int]
    subjects_taught: List[str]
    batches_handled: List[str]
    room_utilization: Dict[str, int]

class SubstituteTeacher(BaseModel):
    employee_id: str
    full_name: str
    department: str
    available_subjects: List[str]
    current_workload: int

@router.get("/my-timetable", response_model=TeacherTimetableResponse)
async def get_my_timetable(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get current teacher's timetable"""
    
    # Get faculty details
    faculty = db.query(Faculty).filter(
        Faculty.employee_id == current_user.employee_id
    ).first()
    
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found"
        )
    
    # Get active timetable entries
    timetable_entries = db.query(Timetable).filter(
        Timetable.faculty_id == current_user.employee_id,
        Timetable.status == "active"
    ).order_by(Timetable.day, Timetable.hour).all()
    
    # Convert to response format
    timetable = [
        TimetableEntry(
            id=entry.id,
            batch_id=entry.batch_id,
            subject_name=entry.subject_name,
            room_id=entry.room_id,
            day=entry.day,
            hour=entry.hour,
            week_type=entry.week_type,
            status=entry.status
        ) for entry in timetable_entries
    ]
    
    # Calculate workload distribution
    workload_dist = {}
    for entry in timetable_entries:
        day = entry.day
        workload_dist[day] = workload_dist.get(day, 0) + 1
    
    return TeacherTimetableResponse(
        faculty_id=current_user.employee_id,
        faculty_name=faculty.full_name,
        total_hours=len(timetable_entries),
        timetable=timetable,
        workload_distribution=workload_dist
    )

@router.get("/workload-summary", response_model=WorkloadSummary)
async def get_workload_summary(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get teacher's workload summary"""
    
    timetable_entries = db.query(Timetable).filter(
        Timetable.faculty_id == current_user.employee_id,
        Timetable.status == "active"
    ).all()
    
    # Calculate statistics
    hours_by_day = {}
    subjects = set()
    batches = set()
    rooms = {}
    
    for entry in timetable_entries:
        # Hours by day
        day = entry.day
        hours_by_day[day] = hours_by_day.get(day, 0) + 1
        
        # Subjects and batches
        subjects.add(entry.subject_name)
        batches.add(entry.batch_id)
        
        # Room utilization
        room = entry.room_id
        rooms[room] = rooms.get(room, 0) + 1
    
    return WorkloadSummary(
        total_hours_per_week=len(timetable_entries),
        hours_by_day=hours_by_day,
        subjects_taught=list(subjects),
        batches_handled=list(batches),
        room_utilization=rooms
    )

@router.post("/request-leave", response_model=LeaveResponse)
async def request_leave(
    leave_request: LeaveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Submit a leave request"""
    
    # Validate dates
    if leave_request.start_date > leave_request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date"
        )
    
    # Check for overlapping leave requests
    existing_leave = db.query(TeacherLeave).filter(
        TeacherLeave.faculty_id == current_user.employee_id,
        TeacherLeave.status.in_(["pending", "approved"]),
        TeacherLeave.start_date <= leave_request.end_date,
        TeacherLeave.end_date >= leave_request.start_date
    ).first()
    
    if existing_leave:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overlapping leave request already exists"
        )
    
    # Create leave request
    teacher_leave = TeacherLeave(
        faculty_id=current_user.employee_id,
        start_date=datetime.combine(leave_request.start_date, datetime.min.time()),
        end_date=datetime.combine(leave_request.end_date, datetime.min.time()),
        leave_type=leave_request.leave_type,
        reason=leave_request.reason,
        substitute_faculty_id=leave_request.substitute_faculty_id
    )
    
    db.add(teacher_leave)
    db.commit()
    db.refresh(teacher_leave)
    
    # Trigger optimization in background if substitute is provided
    if leave_request.substitute_faculty_id:
        background_tasks.add_task(
            handle_teacher_leave_optimization,
            teacher_leave.id,
            current_user.employee_id,
            leave_request.substitute_faculty_id
        )
    
    # Notify admins
    await websocket_manager.broadcast_to_admins({
        "type": "leave_request",
        "message": f"New leave request from {current_user.full_name}",
        "faculty_id": current_user.employee_id,
        "leave_id": teacher_leave.id,
        "start_date": leave_request.start_date.isoformat(),
        "end_date": leave_request.end_date.isoformat()
    })
    
    return LeaveResponse(
        id=teacher_leave.id,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        leave_type=leave_request.leave_type,
        reason=leave_request.reason,
        substitute_faculty_id=leave_request.substitute_faculty_id,
        status=teacher_leave.status,
        created_at=teacher_leave.created_at,
        approved_at=teacher_leave.approved_at
    )

@router.get("/my-leave-requests", response_model=List[LeaveResponse])
async def get_my_leave_requests(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get teacher's leave requests"""
    
    leave_requests = db.query(TeacherLeave).filter(
        TeacherLeave.faculty_id == current_user.employee_id
    ).order_by(TeacherLeave.created_at.desc()).all()
    
    return [
        LeaveResponse(
            id=leave.id,
            start_date=leave.start_date.date(),
            end_date=leave.end_date.date(),
            leave_type=leave.leave_type,
            reason=leave.reason,
            substitute_faculty_id=leave.substitute_faculty_id,
            status=leave.status,
            created_at=leave.created_at,
            approved_at=leave.approved_at
        ) for leave in leave_requests
    ]

@router.get("/available-substitutes", response_model=List[SubstituteTeacher])
async def get_available_substitutes(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get list of available substitute teachers"""
    
    # Get current teacher's subjects
    faculty = db.query(Faculty).filter(
        Faculty.employee_id == current_user.employee_id
    ).first()
    
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found"
        )
    
    current_subjects = [s.strip() for s in faculty.subjects.split(',')]
    
    # Find other faculty who can teach the same subjects
    potential_substitutes = db.query(Faculty).filter(
        Faculty.employee_id != current_user.employee_id,
        Faculty.is_available == True
    ).all()
    
    substitutes = []
    for sub_faculty in potential_substitutes:
        sub_subjects = [s.strip() for s in sub_faculty.subjects.split(',')]
        common_subjects = list(set(current_subjects) & set(sub_subjects))
        
        if common_subjects:
            # Calculate current workload
            current_workload = db.query(Timetable).filter(
                Timetable.faculty_id == sub_faculty.employee_id,
                Timetable.status == "active"
            ).count()
            
            substitutes.append(SubstituteTeacher(
                employee_id=sub_faculty.employee_id,
                full_name=sub_faculty.full_name,
                department=sub_faculty.department,
                available_subjects=common_subjects,
                current_workload=current_workload
            ))
    
    # Sort by workload (ascending)
    substitutes.sort(key=lambda x: x.current_workload)
    
    return substitutes

@router.delete("/cancel-leave/{leave_id}")
async def cancel_leave_request(
    leave_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Cancel a leave request"""
    
    leave_request = db.query(TeacherLeave).filter(
        TeacherLeave.id == leave_id,
        TeacherLeave.faculty_id == current_user.employee_id
    ).first()
    
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel approved leave request"
        )
    
    # Delete the leave request
    db.delete(leave_request)
    db.commit()
    
    return {"message": "Leave request cancelled successfully"}

@router.get("/schedule-conflicts")
async def check_schedule_conflicts(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Check for any schedule conflicts"""
    
    # Get current teacher's timetable
    timetable_entries = db.query(Timetable).filter(
        Timetable.faculty_id == current_user.employee_id,
        Timetable.status == "active"
    ).all()
    
    conflicts = []
    time_slots = {}
    
    # Check for double bookings
    for entry in timetable_entries:
        time_key = f"{entry.day}-{entry.hour}"
        
        if time_key in time_slots:
            conflicts.append({
                "type": "double_booking",
                "time_slot": f"{entry.day} Hour {entry.hour}",
                "conflicting_subjects": [
                    time_slots[time_key]["subject_name"],
                    entry.subject_name
                ],
                "conflicting_batches": [
                    time_slots[time_key]["batch_id"],
                    entry.batch_id
                ]
            })
        else:
            time_slots[time_key] = {
                "subject_name": entry.subject_name,
                "batch_id": entry.batch_id
            }
    
    # Check for excessive consecutive classes
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        day_entries = [e for e in timetable_entries if e.day == day]
        day_entries.sort(key=lambda x: x.hour)
        
        consecutive_count = 0
        for i, entry in enumerate(day_entries):
            if i == 0 or entry.hour == day_entries[i-1].hour + 1:
                consecutive_count += 1
            else:
                consecutive_count = 1
            
            if consecutive_count > 4:  # More than 4 consecutive classes
                conflicts.append({
                    "type": "excessive_consecutive",
                    "day": day,
                    "consecutive_hours": consecutive_count,
                    "recommendation": "Consider rescheduling some classes"
                })
                break
    
    return {
        "total_conflicts": len(conflicts),
        "conflicts": conflicts,
        "status": "clean" if not conflicts else "has_conflicts"
    }

@router.get("/teaching-analytics")
async def get_teaching_analytics(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get teaching analytics and insights"""
    
    timetable_entries = db.query(Timetable).filter(
        Timetable.faculty_id == current_user.employee_id,
        Timetable.status == "active"
    ).all()
    
    # Calculate various metrics
    total_hours = len(timetable_entries)
    unique_subjects = len(set(entry.subject_name for entry in timetable_entries))
    unique_batches = len(set(entry.batch_id for entry in timetable_entries))
    unique_rooms = len(set(entry.room_id for entry in timetable_entries))
    
    # Daily distribution
    daily_hours = {}
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        daily_hours[day] = len([e for e in timetable_entries if e.day == day])
    
    # Subject distribution
    subject_hours = {}
    for entry in timetable_entries:
        subject = entry.subject_name
        subject_hours[subject] = subject_hours.get(subject, 0) + 1
    
    # Peak teaching hours
    hour_distribution = {}
    for entry in timetable_entries:
        hour = f"Hour {entry.hour}"
        hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
    
    # Workload balance (standard deviation of daily hours)
    daily_values = list(daily_hours.values())
    if daily_values:
        avg_daily = sum(daily_values) / len(daily_values)
        variance = sum((x - avg_daily) ** 2 for x in daily_values) / len(daily_values)
        balance_score = round(100 - (variance * 10), 1)  # Higher is better
    else:
        balance_score = 0
    
    return {
        "summary": {
            "total_hours_per_week": total_hours,
            "subjects_taught": unique_subjects,
            "batches_handled": unique_batches,
            "rooms_utilized": unique_rooms
        },
        "distribution": {
            "daily_hours": daily_hours,
            "subject_hours": subject_hours,
            "hour_distribution": hour_distribution
        },
        "insights": {
            "workload_balance_score": balance_score,
            "busiest_day": max(daily_hours, key=daily_hours.get) if daily_hours else None,
            "most_taught_subject": max(subject_hours, key=subject_hours.get) if subject_hours else None,
            "peak_teaching_hour": max(hour_distribution, key=hour_distribution.get) if hour_distribution else None
        }
    }

@router.post("/feedback")
async def submit_feedback(
    feedback_data: Dict[str, Any],
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Submit feedback about timetable"""
    
    # Here you could store feedback in a dedicated table
    # For now, we'll just log it and notify admins
    
    await websocket_manager.broadcast_to_admins({
        "type": "teacher_feedback",
        "message": f"New feedback from {current_user.full_name}",
        "faculty_id": current_user.employee_id,
        "feedback": feedback_data.get("message", ""),
        "rating": feedback_data.get("rating", 0),
        "category": feedback_data.get("category", "general")
    })
    
    return {"message": "Feedback submitted successfully"}

@router.get("/notification-preferences")
async def get_notification_preferences(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Get teacher's notification preferences"""
    
    # This could be stored in a separate table
    # For now, return default preferences
    return {
        "email_notifications": True,
        "push_notifications": True,
        "timetable_changes": True,
        "leave_updates": True,
        "system_maintenance": False
    }

@router.post("/notification-preferences")
async def update_notification_preferences(
    preferences: Dict[str, bool],
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Update teacher's notification preferences"""
    
    # Store preferences (you might want to create a separate table for this)
    # For now, just return success
    return {"message": "Notification preferences updated successfully"}