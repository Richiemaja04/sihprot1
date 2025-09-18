import pandas as pd
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import logging

from database.db import get_db_session
from database.model import (
    Timetable, TimetableVersion, OptimizationLog, TeacherLeave,
    Faculty, Batch, Subject, Classroom
)
from services.ga_engine import TimetableOptimizer, Gene
from utils.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

class OptimizationService:
    """Service for handling timetable optimization and re-optimization"""

    def __init__(self):
        self.optimizer = TimetableOptimizer()
        self.active_optimizations = {}

    async def handle_teacher_leave_optimization(
        self,
        leave_id: int,
        original_faculty_id: str,
        substitute_faculty_id: str
    ):
        """Handle timetable optimization when teacher takes leave"""

        db = get_db_session()

        try:
            # Get leave details
            leave = db.query(TeacherLeave).filter(
                TeacherLeave.id == leave_id
            ).first()

            if not leave:
                logger.error(f"Leave request {leave_id} not found")
                return

            # Create optimization log
            run_id = str(uuid.uuid4())
            log_entry = OptimizationLog(
                run_id=run_id,
                operation_type='substitute',
                status='running',
                parameters={
                    'leave_id': leave_id,
                    'original_faculty': original_faculty_id,
                    'substitute_faculty': substitute_faculty_id
                }
            )
            db.add(log_entry)
            db.commit()

            # Get affected timetable entries
            affected_entries = db.query(Timetable).filter(
                Timetable.faculty_id == original_faculty_id,
                Timetable.status == "active"
            ).all()

            if not affected_entries:
                logger.info(f"No timetable entries found for faculty {original_faculty_id}")
                return

            # Check substitute availability
            if not await self._check_substitute_availability(
                substitute_faculty_id, affected_entries, db
            ):
                raise Exception("Substitute teacher has scheduling conflicts")

            # Update timetable entries
            success_count = 0
            for entry in affected_entries:
                entry.faculty_id = substitute_faculty_id
                success_count += 1

            db.commit()

            # Update optimization log
            log_entry.status = 'completed'
            log_entry.completed_at = datetime.utcnow()
            db.commit()

            # Notify users
            await websocket_manager.notify_teacher_leave_update(
                original_faculty_id,
                {
                    'substitute_faculty_id': substitute_faculty_id,
                    'affected_classes': success_count,
                    'status': 'completed'
                }
            )

            logger.info(f"Successfully updated {success_count} classes with substitute teacher")

        except Exception as e:
            logger.error(f"Error in teacher leave optimization: {e}")

            # Update log with error
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.utcnow()
            db.commit()

        finally:
            db.close()

    async def _check_substitute_availability(
        self,
        substitute_faculty_id: str,
        affected_entries: List[Timetable],
        db: Session
    ) -> bool:
        """Check if substitute teacher is available for all affected time slots"""

        # Get substitute's current timetable
        substitute_entries = db.query(Timetable).filter(
            Timetable.faculty_id == substitute_faculty_id,
            Timetable.status == "active"
        ).all()

        # Create set of occupied time slots
        occupied_slots = set()
        for entry in substitute_entries:
            occupied_slots.add((entry.day, entry.hour))

        # Check if any affected slots conflict
        for entry in affected_entries:
            if (entry.day, entry.hour) in occupied_slots:
                logger.warning(
                    f"Conflict found: {substitute_faculty_id} already has class on "
                    f"{entry.day} hour {entry.hour}"
                )
                return False

        return True

    async def optimize_for_room_change(
        self,
        old_room_id: str,
        new_room_id: str,
        affected_batches: List[str] = None
    ):
        """Optimize timetable when a room is changed or unavailable"""

        db = get_db_session()
        run_id = str(uuid.uuid4())

        try:
            # Create optimization log
            log_entry = OptimizationLog(
                run_id=run_id,
                operation_type='room_change',
                status='running',
                parameters={
                    'old_room_id': old_room_id,
                    'new_room_id': new_room_id,
                    'affected_batches': affected_batches
                }
            )
            db.add(log_entry)
            db.commit()

            # Get affected entries
            query = db.query(Timetable).filter(
                Timetable.room_id == old_room_id,
                Timetable.status == "active"
            )

            if affected_batches:
                query = query.filter(Timetable.batch_id.in_(affected_batches))

            affected_entries = query.all()

            # Check new room availability and capacity
            new_room = db.query(Classroom).filter(
                Classroom.class_id == new_room_id
            ).first()

            if not new_room:
                raise Exception(f"New room {new_room_id} not found")

            # Update entries
            success_count = 0
            capacity_issues = []

            for entry in affected_entries:
                # Get batch to check capacity
                batch = db.query(Batch).filter(
                    Batch.batch_id == entry.batch_id
                ).first()

                if batch and batch.student_count > new_room.capacity:
                    capacity_issues.append({
                        'batch_id': entry.batch_id,
                        'student_count': batch.student_count,
                        'room_capacity': new_room.capacity
                    })
                    continue

                entry.room_id = new_room_id
                success_count += 1

            db.commit()

            # Update log
            log_entry.status = 'completed'
            log_entry.completed_at = datetime.utcnow()

            if capacity_issues:
                log_entry.error_message = f"Capacity issues for {len(capacity_issues)} entries"

            db.commit()

            # Notify users
            await websocket_manager.broadcast_to_all({
                "type": "room_change_complete",
                "message": f"Room change optimization completed",
                "success_count": success_count,
                "capacity_issues": capacity_issues
            })

            logger.info(f"Room change optimization completed: {success_count} entries updated")

        except Exception as e:
            logger.error(f"Error in room change optimization: {e}")

            # Update log with error
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.utcnow()
            db.commit()

        finally:
            db.close()

    async def reoptimize_timetable(
        self,
        constraints: Dict[str, Any],
        version_name: str
    ) -> Optional[str]:
        """Re-optimize existing timetable with new constraints"""

        db = get_db_session()
        run_id = str(uuid.uuid4())

        try:
            # Create optimization log
            log_entry = OptimizationLog(
                run_id=run_id,
                operation_type='reoptimize',
                status='running',
                parameters=constraints
            )
            db.add(log_entry)
            db.commit()

            # Load current data
            batches_df = pd.read_sql(
                db.query(Batch).statement, db.bind
            )
            subjects_df = pd.read_sql(
                db.query(Subject).statement, db.bind
            )
            faculty_df = pd.read_sql(
                db.query(Faculty).statement, db.bind
            )
            classrooms_df = pd.read_sql(
                db.query(Classroom).statement, db.bind
            )

            # Apply constraints to data
            if constraints.get('exclude_faculty'):
                faculty_df = faculty_df[
                    ~faculty_df['employee_id'].isin(constraints['exclude_faculty'])
                ]

            if constraints.get('exclude_rooms'):
                classrooms_df = classrooms_df[
                    ~classrooms_df['class_id'].isin(constraints['exclude_rooms'])
                ]

            # Run optimization
            solutions = self.optimizer.generate_multiple_solutions(
                batches_df, classrooms_df, faculty_df, subjects_df, num_solutions=1
            )

            if not solutions:
                raise Exception("Failed to generate optimized solution")

            best_genes, best_fitness = solutions[0]

            # Create new timetable version
            version_id = str(uuid.uuid4())
            version = TimetableVersion(
                version_id=version_id,
                name=version_name,
                description=f"Re-optimized timetable with fitness: {best_fitness:.4f}",
                fitness_score=best_fitness,
                generation_params=constraints,
                created_by="system"
            )
            db.add(version)

            # Save timetable entries
            for gene in best_genes:
                timetable_entry = Timetable(
                    version_id=version_id,
                    batch_id=gene.batch_id,
                    subject_name=gene.subject_name,
                    faculty_id=gene.faculty_id,
                    room_id=gene.room_id,
                    day=gene.day,
                    hour=gene.hour,
                    status='draft',
                    created_by="system"
                )
                db.add(timetable_entry)

            db.commit()

            # Update log
            log_entry.status = 'completed'
            log_entry.version_id = version_id
            log_entry.fitness_scores = [best_fitness]
            log_entry.completed_at = datetime.utcnow()
            db.commit()

            # Notify admins
            await websocket_manager.broadcast_to_admins({
                "type": "reoptimization_complete",
                "message": "Timetable re-optimization completed",
                "version_id": version_id,
                "fitness_score": best_fitness
            })

            logger.info(f"Re-optimization completed: {version_id}")
            return version_id

        except Exception as e:
            logger.error(f"Error in re-optimization: {e}")

            # Update log with error
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.utcnow()
            db.commit()

            return None

        finally:
            db.close()

    async def handle_emergency_optimization(
        self,
        emergency_type: str,
        affected_entities: List[str],
        replacement_entities: List[str] = None
    ):
        """Handle emergency timetable changes"""

        db = get_db_session()
        run_id = str(uuid.uuid4())

        try:
            logger.info(f"Starting emergency optimization: {emergency_type}")

            # Create optimization log
            log_entry = OptimizationLog(
                run_id=run_id,
                operation_type='emergency',
                status='running',
                parameters={
                    'emergency_type': emergency_type,
                    'affected_entities': affected_entities,
                    'replacement_entities': replacement_entities
                }
            )
            db.add(log_entry)
            db.commit()

            if emergency_type == 'faculty_unavailable':
                await self._handle_faculty_emergency(
                    affected_entities, replacement_entities, db
                )
            elif emergency_type == 'room_unavailable':
                await self._handle_room_emergency(
                    affected_entities, replacement_entities, db
                )
            elif emergency_type == 'batch_schedule_change':
                await self._handle_batch_emergency(
                    affected_entities, replacement_entities, db
                )

            # Update log
            log_entry.status = 'completed'
            log_entry.completed_at = datetime.utcnow()
            db.commit()

            # Broadcast emergency update
            await websocket_manager.broadcast_to_all({
                "type": "emergency_update",
                "message": f"Emergency timetable update: {emergency_type}",
                "affected_entities": affected_entities,
                "status": "completed"
            })

        except Exception as e:
            logger.error(f"Error in emergency optimization: {e}")

            # Update log
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.utcnow()
            db.commit()

        finally:
            db.close()

    async def _handle_faculty_emergency(
        self,
        faculty_ids: List[str],
        substitute_ids: List[str],
        db: Session
    ):
        """Handle faculty emergency (sudden unavailability)"""

        for i, faculty_id in enumerate(faculty_ids):
            # Find affected classes
            affected_entries = db.query(Timetable).filter(
                Timetable.faculty_id == faculty_id,
                Timetable.status == "active"
            ).all()

            if substitute_ids and i < len(substitute_ids):
                substitute_id = substitute_ids[i]

                # Check availability
                if await self._check_substitute_availability(
                    substitute_id, affected_entries, db
                ):
                    # Assign substitute
                    for entry in affected_entries:
                        entry.faculty_id = substitute_id
                else:
                    # Cancel classes if no substitute available
                    for entry in affected_entries:
                        entry.status = "cancelled"
            else:
                # Cancel classes
                for entry in affected_entries:
                    entry.status = "cancelled"

        db.commit()

    async def _handle_room_emergency(
        self,
        room_ids: List[str],
        replacement_room_ids: List[str],
        db: Session
    ):
        """Handle room emergency (sudden unavailability)"""

        for i, room_id in enumerate(room_ids):
            # Find affected classes
            affected_entries = db.query(Timetable).filter(
                Timetable.room_id == room_id,
                Timetable.status == "active"
            ).all()

            if replacement_room_ids and i < len(replacement_room_ids):
                replacement_room_id = replacement_room_ids[i]

                # Get replacement room details
                replacement_room = db.query(Classroom).filter(
                    Classroom.class_id == replacement_room_id
                ).first()

                if replacement_room:
                    for entry in affected_entries:
                        # Check capacity
                        batch = db.query(Batch).filter(
                            Batch.batch_id == entry.batch_id
                        ).first()

                        if not batch or batch.student_count <= replacement_room.capacity:
                            entry.room_id = replacement_room_id
                        else:
                            entry.status = "cancelled"
                else:
                    # Cancel if replacement room not found
                    for entry in affected_entries:
                        entry.status = "cancelled"
            else:
                # Cancel classes
                for entry in affected_entries:
                    entry.status = "cancelled"

        db.commit()

    async def _handle_batch_emergency(
        self,
        batch_ids: List[str],
        alternative_slots: List[str],
        db: Session
    ):
        """Handle batch emergency (schedule change required)"""

        # This would implement batch-specific emergency handling
        # For now, just mark affected classes for manual review
        for batch_id in batch_ids:
            affected_entries = db.query(Timetable).filter(
                Timetable.batch_id == batch_id,
                Timetable.status == "active"
            ).all()

            for entry in affected_entries:
                entry.status = "review_required"

        db.commit()

# Global optimization service instance
optimization_service = OptimizationService()

# Background task functions
async def handle_teacher_leave_optimization(
    leave_id: int,
    original_faculty_id: str,
    substitute_faculty_id: str
):
    """Background task wrapper for teacher leave optimization"""
    await optimization_service.handle_teacher_leave_optimization(
        leave_id, original_faculty_id, substitute_faculty_id
    )