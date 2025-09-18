import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import base64
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
import logging

from database.db import get_db_session
from database.model import Timetable, Batch, Subject, Faculty, Classroom, TimetableVersion
from config import settings

logger = logging.getLogger(__name__)

class TimetableReportingService:
    """Service for generating reports and analytics"""
    
    def __init__(self):
        self.output_dir = settings.REPORTS_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up matplotlib for server environment
        plt.switch_backend('Agg')
        sns.set_style("whitegrid")
        
    def generate_timetable_pdf(
        self, 
        batch_id: str, 
        version_id: Optional[str] = None
    ) -> str:
        """Generate PDF timetable for a specific batch"""
        
        db = get_db_session()
        
        try:
            # Get batch info
            batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
            if not batch:
                raise Exception(f"Batch {batch_id} not found")
            
            # Get timetable data
            query = db.query(Timetable).filter(
                Timetable.batch_id == batch_id,
                Timetable.status == "active"
            )
            
            if version_id:
                query = query.filter(Timetable.version_id == version_id)
            
            timetable_entries = query.all()
            
            if not timetable_entries:
                raise Exception(f"No timetable found for batch {batch_id}")
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"timetable_{batch_id}_{timestamp}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            # Create PDF
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                alignment=TA_CENTER,
                spaceAfter=30
            )
            
            title = Paragraph(
                f"Timetable - {batch.department} {batch.level} Semester {batch.semester}",
                title_style
            )
            story.append(title)
            
            # Batch info
            batch_info = [
                f"<b>Batch ID:</b> {batch.batch_id}",
                f"<b>Department:</b> {batch.department}",
                f"<b>Level:</b> {batch.level}",
                f"<b>Semester:</b> {batch.semester}",
                f"<b>Students:</b> {batch.student_count}",
                f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            for info in batch_info:
                story.append(Paragraph(info, styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # Create timetable grid
            grid_data = self._create_timetable_grid(timetable_entries, db)
            
            # Convert grid to table data
            table_data = [['Time'] + settings.DAYS]
            
            for hour in range(1, settings.HOURS_PER_DAY + 1):
                row = [f"Hour {hour}"]
                for day in settings.DAYS:
                    cell_data = grid_data.get(day, {}).get(hour, "")
                    if cell_data:
                        cell_text = f"{cell_data['subject']}\n{cell_data['faculty']}\n{cell_data['room']}"
                    else:
                        cell_text = ""
                    row.append(cell_text)
                table_data.append(row)
            
            # Create table
            table = Table(table_data, colWidths=[1*inch] + [1.2*inch]*5)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 30))
            
            # Add subjects summary
            subjects_summary = self._generate_subjects_summary(timetable_entries, db)
            
            story.append(Paragraph("<b>Subjects Summary</b>", styles['Heading2']))
            
            for subject_info in subjects_summary:
                subject_text = f"<b>{subject_info['name']}</b> - {subject_info['credits']} credits, {subject_info['hours_per_week']} hours/week, Faculty: {subject_info['faculty']}"
                story.append(Paragraph(subject_text, styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated PDF report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            raise
        finally:
            db.close()
    
    def generate_faculty_workload_report(self) -> str:
        """Generate faculty workload analysis report"""
        
        db = get_db_session()
        
        try:
            # Get all faculty and their workloads
            faculties = db.query(Faculty).all()
            workload_data = []
            
            for faculty in faculties:
                current_hours = db.query(Timetable).filter(
                    Timetable.faculty_id == faculty.employee_id,
                    Timetable.status == "active"
                ).count()
                
                # Get subjects taught
                subjects_taught = db.query(Timetable.subject_name).filter(
                    Timetable.faculty_id == faculty.employee_id,
                    Timetable.status == "active"
                ).distinct().all()
                
                subjects_count = len(subjects_taught)
                subjects_list = [s[0] for s in subjects_taught]
                
                # Get batches handled
                batches_handled = db.query(Timetable.batch_id).filter(
                    Timetable.faculty_id == faculty.employee_id,
                    Timetable.status == "active"
                ).distinct().count()
                
                workload_data.append({
                    'employee_id': faculty.employee_id,
                    'full_name': faculty.full_name,
                    'department': faculty.department,
                    'current_hours': current_hours,
                    'max_hours': faculty.max_hours_per_week,
                    'utilization_percentage': round((current_hours / faculty.max_hours_per_week) * 100, 1) if faculty.max_hours_per_week > 0 else 0,
                    'subjects_count': subjects_count,
                    'subjects_list': ', '.join(subjects_list),
                    'batches_handled': batches_handled
                })
            
            # Create DataFrame
            df = pd.DataFrame(workload_data)
            
            # Generate charts
            charts_data = self._generate_workload_charts(df)
            
            # Create PDF report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"faculty_workload_report_{timestamp}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph("Faculty Workload Analysis Report", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Summary statistics
            avg_utilization = df['utilization_percentage'].mean()
            overloaded_faculty = len(df[df['utilization_percentage'] > 90])
            underutilized_faculty = len(df[df['utilization_percentage'] < 50])
            
            summary_data = [
                ['Total Faculty', len(df)],
                ['Average Utilization', f"{avg_utilization:.1f}%"],
                ['Overloaded (>90%)', overloaded_faculty],
                ['Underutilized (<50%)', underutilized_faculty]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 30))
            
            # Detailed faculty table
            story.append(Paragraph("Detailed Faculty Workload", styles['Heading2']))
            
            # Create table data
            table_data = [['Faculty ID', 'Name', 'Department', 'Current Hours', 'Max Hours', 'Utilization %']]
            
            for _, row in df.iterrows():
                table_data.append([
                    row['employee_id'],
                    row['full_name'][:20] + ('...' if len(row['full_name']) > 20 else ''),
                    row['department'][:15] + ('...' if len(row['department']) > 15 else ''),
                    str(row['current_hours']),
                    str(row['max_hours']),
                    f"{row['utilization_percentage']}%"
                ])
            
            workload_table = Table(table_data, colWidths=[1*inch, 1.5*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            workload_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(workload_table)
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated faculty workload report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating faculty workload report: {e}")
            raise
        finally:
            db.close()
    
    def generate_room_utilization_report(self) -> str:
        """Generate room utilization analysis report"""
        
        db = get_db_session()
        
        try:
            rooms = db.query(Classroom).all()
            utilization_data = []
            
            max_slots = len(settings.DAYS) * settings.HOURS_PER_DAY
            
            for room in rooms:
                used_slots = db.query(Timetable).filter(
                    Timetable.room_id == room.class_id,
                    Timetable.status == "active"
                ).count()
                
                utilization_percentage = round((used_slots / max_slots) * 100, 1)
                
                # Get subjects taught in this room
                subjects = db.query(Timetable.subject_name).filter(
                    Timetable.room_id == room.class_id,
                    Timetable.status == "active"
                ).distinct().all()
                
                utilization_data.append({
                    'room_id': room.class_id,
                    'room_name': room.room_name,
                    'room_type': room.room_type,
                    'capacity': room.capacity,
                    'used_slots': used_slots,
                    'total_slots': max_slots,
                    'utilization_percentage': utilization_percentage,
                    'subjects_count': len(subjects)
                })
            
            # Create DataFrame
            df = pd.DataFrame(utilization_data)
            
            # Create PDF report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"room_utilization_report_{timestamp}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph("Room Utilization Analysis Report", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Summary statistics
            avg_utilization = df['utilization_percentage'].mean()
            overutilized_rooms = len(df[df['utilization_percentage'] > 80])
            underutilized_rooms = len(df[df['utilization_percentage'] < 30])
            
            summary_data = [
                ['Total Rooms', len(df)],
                ['Average Utilization', f"{avg_utilization:.1f}%"],
                ['Overutilized (>80%)', overutilized_rooms],
                ['Underutilized (<30%)', underutilized_rooms]
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 30))
            
            # Room utilization by type
            story.append(Paragraph("Room Utilization by Type", styles['Heading2']))
            
            type_summary = df.groupby('room_type').agg({
                'utilization_percentage': 'mean',
                'room_id': 'count'
            }).round(1)
            
            type_data = [['Room Type', 'Count', 'Avg Utilization %']]
            for room_type, row in type_summary.iterrows():
                type_data.append([
                    room_type,
                    str(int(row['room_id'])),
                    f"{row['utilization_percentage']}%"
                ])
            
            type_table = Table(type_data, colWidths=[2*inch, 1*inch, 1.5*inch])
            type_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(type_table)
            story.append(Spacer(1, 20))
            
            # Detailed room table
            story.append(Paragraph("Detailed Room Utilization", styles['Heading2']))
            
            table_data = [['Room ID', 'Room Name', 'Type', 'Capacity', 'Used Slots', 'Utilization %']]
            
            for _, row in df.sort_values('utilization_percentage', ascending=False).iterrows():
                table_data.append([
                    row['room_id'],
                    row['room_name'][:15] + ('...' if len(row['room_name']) > 15 else ''),
                    row['room_type'][:10] + ('...' if len(row['room_type']) > 10 else ''),
                    str(row['capacity']),
                    str(row['used_slots']),
                    f"{row['utilization_percentage']}%"
                ])
            
            room_table = Table(table_data, colWidths=[1*inch, 1.2*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
            room_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(room_table)
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated room utilization report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating room utilization report: {e}")
            raise
        finally:
            db.close()
    
    def generate_analytics_charts(self) -> Dict[str, str]:
        """Generate analytics charts and return base64 encoded images"""
        
        db = get_db_session()
        charts = {}
        
        try:
            # Faculty workload distribution chart
            faculty_data = self._get_faculty_workload_data(db)
            if faculty_data:
                charts['faculty_workload'] = self._create_faculty_workload_chart(faculty_data)
            
            # Room utilization chart
            room_data = self._get_room_utilization_data(db)
            if room_data:
                charts['room_utilization'] = self._create_room_utilization_chart(room_data)
            
            # Daily schedule distribution chart
            schedule_data = self._get_schedule_distribution_data(db)
            if schedule_data:
                charts['schedule_distribution'] = self._create_schedule_distribution_chart(schedule_data)
            
            # Subject type distribution chart
            subject_data = self._get_subject_type_data(db)
            if subject_data:
                charts['subject_types'] = self._create_subject_type_chart(subject_data)
            
            return charts
            
        except Exception as e:
            logger.error(f"Error generating analytics charts: {e}")
            return {}
        finally:
            db.close()
    
    def _create_timetable_grid(self, timetable_entries: List[Timetable], db: Session) -> Dict:
        """Create timetable grid structure"""
        
        grid = {}
        
        for entry in timetable_entries:
            day = entry.day
            hour = entry.hour
            
            if day not in grid:
                grid[day] = {}
            
            # Get faculty name
            faculty = db.query(Faculty).filter(
                Faculty.employee_id == entry.faculty_id
            ).first()
            faculty_name = faculty.full_name if faculty else entry.faculty_id
            
            # Get room name
            room = db.query(Classroom).filter(
                Classroom.class_id == entry.room_id
            ).first()
            room_name = room.room_name if room else entry.room_id
            
            grid[day][hour] = {
                'subject': entry.subject_name,
                'faculty': faculty_name,
                'room': room_name
            }
        
        return grid
    
    def _generate_subjects_summary(self, timetable_entries: List[Timetable], db: Session) -> List[Dict]:
        """Generate subjects summary"""
        
        subjects_data = {}
        
        for entry in timetable_entries:
            subject_name = entry.subject_name
            
            if subject_name not in subjects_data:
                # Get subject details
                subject = db.query(Subject).filter(
                    Subject.name == subject_name
                ).first()
                
                # Get faculty name
                faculty = db.query(Faculty).filter(
                    Faculty.employee_id == entry.faculty_id
                ).first()
                
                subjects_data[subject_name] = {
                    'name': subject_name,
                    'credits': subject.credits if subject else 0,
                    'type': subject.subject_type if subject else 'Unknown',
                    'faculty': faculty.full_name if faculty else entry.faculty_id,
                    'hours_per_week': 0
                }
            
            subjects_data[subject_name]['hours_per_week'] += 1
        
        return list(subjects_data.values())
    
    def _get_faculty_workload_data(self, db: Session) -> List[Dict]:
        """Get faculty workload data for charts"""
        
        faculties = db.query(Faculty).all()
        data = []
        
        for faculty in faculties:
            current_hours = db.query(Timetable).filter(
                Timetable.faculty_id == faculty.employee_id,
                Timetable.status == "active"
            ).count()
            
            utilization = (current_hours / faculty.max_hours_per_week * 100) if faculty.max_hours_per_week > 0 else 0
            
            data.append({
                'name': faculty.full_name,
                'current_hours': current_hours,
                'max_hours': faculty.max_hours_per_week,
                'utilization': utilization,
                'department': faculty.department
            })
        
        return data
    
    def _create_faculty_workload_chart(self, data: List[Dict]) -> str:
        """Create faculty workload chart"""
        
        df = pd.DataFrame(data)
        
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 1, 1)
        
        # Utilization bar chart
        plt.barh(df['name'][:10], df['utilization'][:10], color='skyblue')
        plt.xlabel('Utilization Percentage')
        plt.title('Faculty Workload Utilization (Top 10)')
        plt.grid(axis='x', alpha=0.3)
        
        plt.subplot(2, 1, 2)
        
        # Department-wise utilization
        dept_avg = df.groupby('department')['utilization'].mean()
        plt.bar(dept_avg.index, dept_avg.values, color='lightgreen')
        plt.xlabel('Department')
        plt.ylabel('Average Utilization %')
        plt.title('Average Faculty Utilization by Department')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return chart_base64
    
    def _get_room_utilization_data(self, db: Session) -> List[Dict]:
        """Get room utilization data for charts"""
        
        rooms = db.query(Classroom).all()
        data = []
        
        max_slots = len(settings.DAYS) * settings.HOURS_PER_DAY
        
        for room in rooms:
            used_slots = db.query(Timetable).filter(
                Timetable.room_id == room.class_id,
                Timetable.status == "active"
            ).count()
            
            utilization = (used_slots / max_slots * 100)
            
            data.append({
                'room_name': room.room_name,
                'room_type': room.room_type,
                'capacity': room.capacity,
                'used_slots': used_slots,
                'utilization': utilization
            })
        
        return data
    
    def _create_room_utilization_chart(self, data: List[Dict]) -> str:
        """Create room utilization chart"""
        
        df = pd.DataFrame(data)
        
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 1, 1)
        
        # Room type utilization
        type_avg = df.groupby('room_type')['utilization'].mean()
        plt.pie(type_avg.values, labels=type_avg.index, autopct='%1.1f%%', startangle=90)
        plt.title('Average Room Utilization by Type')
        
        plt.subplot(2, 1, 2)
        
        # Utilization distribution
        plt.hist(df['utilization'], bins=10, color='orange', alpha=0.7, edgecolor='black')
        plt.xlabel('Utilization Percentage')
        plt.ylabel('Number of Rooms')
        plt.title('Room Utilization Distribution')
        plt.grid(alpha=0.3)
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return chart_base64
    
    def _get_schedule_distribution_data(self, db: Session) -> List[Dict]:
        """Get schedule distribution data"""
        
        data = []
        
        for day in settings.DAYS:
            for hour in range(1, settings.HOURS_PER_DAY + 1):
                count = db.query(Timetable).filter(
                    Timetable.day == day,
                    Timetable.hour == hour,
                    Timetable.status == "active"
                ).count()
                
                data.append({
                    'day': day,
                    'hour': hour,
                    'count': count
                })
        
        return data
    
    def _create_schedule_distribution_chart(self, data: List[Dict]) -> str:
        """Create schedule distribution heatmap"""
        
        df = pd.DataFrame(data)
        pivot_df = df.pivot(index='hour', columns='day', values='count')
        
        plt.figure(figsize=(10, 6))
        sns.heatmap(pivot_df, annot=True, cmap='YlOrRd', fmt='d')
        plt.title('Class Distribution Heatmap')
        plt.xlabel('Day of Week')
        plt.ylabel('Hour of Day')
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return chart_base64
    
    def _get_subject_type_data(self, db: Session) -> List[Dict]:
        """Get subject type distribution data"""
        
        subjects = db.query(Subject).all()
        type_count = {}
        
        for subject in subjects:
            subject_type = subject.subject_type
            type_count[subject_type] = type_count.get(subject_type, 0) + 1
        
        return [{'type': k, 'count': v} for k, v in type_count.items()]
    
    def _create_subject_type_chart(self, data: List[Dict]) -> str:
        """Create subject type distribution chart"""
        
        df = pd.DataFrame(data)
        
        plt.figure(figsize=(8, 6))
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
        plt.pie(df['count'], labels=df['type'], autopct='%1.1f%%', 
                colors=colors[:len(df)], startangle=90)
        plt.title('Subject Type Distribution')
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return chart_base64
    
    def _generate_workload_charts(self, df: pd.DataFrame) -> Dict[str, str]:
        """Generate workload distribution charts"""
        
        charts = {}
        
        try:
            # Utilization histogram
            plt.figure(figsize=(10, 6))
            plt.hist(df['utilization_percentage'], bins=15, color='skyblue', 
                    edgecolor='black', alpha=0.7)
            plt.xlabel('Utilization Percentage')
            plt.ylabel('Number of Faculty')
            plt.title('Faculty Workload Distribution')
            plt.grid(alpha=0.3)
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            charts['utilization_histogram'] = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
        except Exception as e:
            logger.error(f"Error generating workload charts: {e}")
        
        return charts

# Global reporting service instance
reporting_service = TimetableReportingService()