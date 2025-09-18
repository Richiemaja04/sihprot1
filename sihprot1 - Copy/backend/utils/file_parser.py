import pandas as pd
import io
from fastapi import UploadFile, HTTPException, status
from typing import List, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

async def parse_uploaded_file(file: UploadFile) -> pd.DataFrame:
    """Parse uploaded CSV or Excel file"""
    try:
        # Read file content
        content = await file.read()
        
        # Parse based on file extension
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Only CSV and Excel files are allowed."
            )
        
        # Clean up data
        df = clean_dataframe(df)
        
        logger.info(f"Successfully parsed {file.filename} with {len(df)} rows and columns: {list(df.columns)}")
        return df
        
    except Exception as e:
        logger.error(f"Error parsing file {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing file: {str(e)}"
        )

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize dataframe"""
    # Remove completely empty rows and columns
    df = df.dropna(how='all').dropna(axis=1, how='all')
    
    # Strip whitespace from string columns
    string_columns = df.select_dtypes(include=['object']).columns
    df[string_columns] = df[string_columns].astype(str).apply(lambda x: x.str.strip())
    
    # Replace 'nan' strings with actual NaN
    df = df.replace(['nan', 'NaN', 'NULL', 'null', '', 'None'], pd.NA)
    
    # Clean column names - keep original names but also create cleaned versions for matching
    original_columns = df.columns.tolist()
    logger.info(f"Original columns: {original_columns}")
    
    return df

def normalize_column_name(col_name: str) -> str:
    """Normalize column name for comparison"""
    if pd.isna(col_name):
        return ""
    
    # Convert to string and strip whitespace
    normalized = str(col_name).strip()
    
    # Convert to lowercase
    normalized = normalized.lower()
    
    # Replace spaces and special characters with underscores
    normalized = re.sub(r'[^\w]', '_', normalized)
    
    # Remove multiple consecutive underscores
    normalized = re.sub(r'_+', '_', normalized)
    
    # Remove leading/trailing underscores
    normalized = normalized.strip('_')
    
    return normalized

def validate_csv_structure(df: pd.DataFrame, required_columns: List[str], file_type: str):
    """Validate CSV structure against required columns with flexible matching"""
    
    # Get actual column names and create normalized versions
    actual_columns = df.columns.tolist()
    
    # Create mapping of possible column name variations for each file type
    column_variations = {
        'batches': {
            'department': ['department', 'dept', 'department_name'],
            'level': ['level', 'program_level', 'degree_level'],
            'semester': ['semester', 'sem', 'semester_number'],
            'student_count': ['student_count', 'students', 'student_number', 'count'],
            'subjects': ['subjects', 'subject_list', 'subject_names']
        },
        'subjects': {
            'name': ['name', 'subject_name', 'subject', 'title'],
            'code': ['code', 'subject_code', 'course_code'],
            'credits': ['credits', 'credit', 'credit_hours'],
            'type': ['type', 'subject_type', 'course_type', 'category'],
            'department': ['department', 'dept', 'department_name']
        },
        'faculty': {
            'employee_id': ['employee_id', 'emp_id', 'faculty_id', 'id'],
            'full_name': ['full_name', 'name', 'faculty_name', 'teacher_name'],
            'email': ['email', 'email_address', 'mail'],
            'department': ['department', 'dept', 'department_name'],
            'subject_name': ['subject_name', 'subjects', 'subject_list', 'teaches']
        },
        'classrooms': {
            'class_id': ['class_id', 'room_id', 'classroom_id', 'id'],
            'room_name': ['room_name', 'name', 'classroom_name', 'room'],
            'capacity': ['capacity', 'max_capacity', 'seats', 'size'],
            'room_type': ['room_type', 'type', 'classroom_type', 'category'],
            'building': ['building', 'building_name', 'location']
        }
    }
    
    # Get variations for this file type
    variations = column_variations.get(file_type, {})
    
    # Create normalized mapping of actual columns
    normalized_actual = {normalize_column_name(col): col for col in actual_columns}
    
    # Find matches for each required column
    column_mapping = {}
    missing_columns = []
    
    for required_col in required_columns:
        found_match = None
        
        # Try to find a match using variations
        possible_names = variations.get(required_col, [required_col])
        
        for possible_name in possible_names:
            normalized_possible = normalize_column_name(possible_name)
            
            if normalized_possible in normalized_actual:
                found_match = normalized_actual[normalized_possible]
                break
        
        if found_match:
            column_mapping[found_match] = required_col
        else:
            missing_columns.append(required_col)
    
    # Report missing columns with helpful information
    if missing_columns:
        available_cols = ', '.join(actual_columns)
        error_msg = f"Missing required columns in {file_type} file: {', '.join(missing_columns)}. "
        error_msg += f"Available columns: [{available_cols}]. "
        error_msg += f"Please ensure your CSV has these exact columns: {', '.join(required_columns)}"
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Rename columns to match expected names
    if column_mapping:
        # Only rename columns that need renaming
        rename_dict = {old_name: new_name for old_name, new_name in column_mapping.items() 
                      if old_name != new_name}
        if rename_dict:
            df.rename(columns=rename_dict, inplace=True)
            logger.info(f"Renamed columns for {file_type}: {rename_dict}")
    
    # Validate data content
    if file_type == 'batches':
        validate_batches_data(df)
    elif file_type == 'subjects':
        validate_subjects_data(df)
    elif file_type == 'faculty':
        validate_faculty_data(df)
    elif file_type == 'classrooms':
        validate_classrooms_data(df)

def validate_batches_data(df: pd.DataFrame):
    """Validate batches data"""
    errors = []
    
    # Check for missing values in critical columns
    for col in ['department', 'level', 'semester', 'student_count']:
        if col in df.columns and df[col].isnull().any():
            errors.append(f"Missing values found in {col} column")
    
    # Validate student_count is numeric
    if 'student_count' in df.columns:
        try:
            df['student_count'] = pd.to_numeric(df['student_count'], errors='raise')
            if (df['student_count'] <= 0).any():
                errors.append("Student count must be positive")
        except (ValueError, TypeError):
            errors.append("Student count must be numeric")
    
    # Validate subjects column
    if 'subjects' in df.columns and df['subjects'].isnull().any():
        errors.append("Missing subjects data")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch data validation errors: {'; '.join(errors)}"
        )

def validate_subjects_data(df: pd.DataFrame):
    """Validate subjects data"""
    errors = []
    
    # Check for missing values
    for col in ['name', 'credits', 'type']:
        if col in df.columns and df[col].isnull().any():
            errors.append(f"Missing values found in {col} column")
    
    # Validate credits
    if 'credits' in df.columns:
        try:
            df['credits'] = pd.to_numeric(df['credits'], errors='raise')
            if (df['credits'] <= 0).any():
                errors.append("Credits must be positive")
        except (ValueError, TypeError):
            errors.append("Credits must be numeric")
    
    # Validate subject type
    if 'type' in df.columns:
        valid_types = ['Theory', 'Lab', 'Practical', 'theory', 'lab', 'practical']
        invalid_types = df[~df['type'].isin(valid_types)]['type'].dropna().unique()
        if len(invalid_types) > 0:
            errors.append(f"Invalid subject types found: {list(invalid_types)}. Valid types: Theory, Lab, Practical")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject data validation errors: {'; '.join(errors)}"
        )

def validate_faculty_data(df: pd.DataFrame):
    """Validate faculty data"""
    errors = []
    
    # Check for missing values
    for col in ['employee_id', 'full_name', 'subject_name']:
        if col in df.columns and df[col].isnull().any():
            errors.append(f"Missing values found in {col} column")
    
    # Check for duplicate employee IDs
    if 'employee_id' in df.columns and df['employee_id'].duplicated().any():
        errors.append("Duplicate employee IDs found")
    
    # Validate email format if provided
    if 'email' in df.columns:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        non_null_emails = df['email'].dropna()
        if len(non_null_emails) > 0:
            invalid_emails = non_null_emails[~non_null_emails.str.match(email_pattern, na=False)]
            if len(invalid_emails) > 0:
                errors.append(f"Invalid email format found: {list(invalid_emails.head(3))}")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faculty data validation errors: {'; '.join(errors)}"
        )

def validate_classrooms_data(df: pd.DataFrame):
    """Validate classrooms data"""
    errors = []
    
    # Check for missing values
    for col in ['class_id', 'room_name', 'capacity', 'room_type']:
        if col in df.columns and df[col].isnull().any():
            errors.append(f"Missing values found in {col} column")
    
    # Validate capacity
    if 'capacity' in df.columns:
        try:
            df['capacity'] = pd.to_numeric(df['capacity'], errors='raise')
            if (df['capacity'] <= 0).any():
                errors.append("Capacity must be positive")
        except (ValueError, TypeError):
            errors.append("Capacity must be numeric")
    
    # Check for duplicate class IDs
    if 'class_id' in df.columns and df['class_id'].duplicated().any():
        errors.append("Duplicate class IDs found")
    
    # Validate room type
    if 'room_type' in df.columns:
        valid_types = ['Laboratory', 'Lecture Hall', 'Classroom', 'Seminar Room', 
                       'laboratory', 'lecture hall', 'classroom', 'seminar room']
        invalid_types = df[~df['room_type'].isin(valid_types)]['room_type'].dropna().unique()
        if len(invalid_types) > 0:
            errors.append(f"Invalid room types found: {list(invalid_types)}. Valid types: Laboratory, Lecture Hall, Classroom, Seminar Room")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Classroom data validation errors: {'; '.join(errors)}"
        )

def generate_sample_csv(file_type: str) -> Dict[str, Any]:
    """Generate sample CSV structure for different file types"""
    
    samples = {
        'batches': {
            'columns': ['department', 'level', 'semester', 'student_count', 'subjects'],
            'sample_data': [
                ['Computer Science', 'UG', '1', '60', 'Mathematics,Physics,Programming'],
                ['Electronics', 'UG', '2', '55', 'Digital Electronics,Signals,Microprocessors']
            ]
        },
        'subjects': {
            'columns': ['name', 'code', 'credits', 'type', 'department'],
            'sample_data': [
                ['Mathematics', 'MATH101', '4', 'Theory', 'Computer Science'],
                ['Physics Lab', 'PHY101L', '2', 'Lab', 'Computer Science']
            ]
        },
        'faculty': {
            'columns': ['employee_id', 'full_name', 'email', 'department', 'subject_name'],
            'sample_data': [
                ['FAC001', 'Dr. John Smith', 'john.smith@university.edu', 'Computer Science', 'Mathematics,Programming'],
                ['FAC002', 'Prof. Jane Doe', 'jane.doe@university.edu', 'Electronics', 'Digital Electronics']
            ]
        },
        'classrooms': {
            'columns': ['class_id', 'room_name', 'capacity', 'room_type', 'building'],
            'sample_data': [
                ['CR001', 'Computer Lab 1', '40', 'Laboratory', 'Building A'],
                ['CR002', 'Lecture Hall 1', '100', 'Lecture Hall', 'Building B']
            ]
        }
    }
    
    return samples.get(file_type, {})

def export_to_csv(data: List[Dict[str, Any]], filename: str) -> str:
    """Export data to CSV file"""
    try:
        df = pd.DataFrame(data)
        file_path = f"./generated/reports/{filename}"
        df.to_csv(file_path, index=False)
        logger.info(f"Data exported to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error exporting to CSV: {str(e)}")
        raise

def export_to_excel(data: Dict[str, List[Dict[str, Any]]], filename: str) -> str:
    """Export data to Excel file with multiple sheets"""
    try:
        file_path = f"./generated/reports/{filename}"
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for sheet_name, sheet_data in data.items():
                df = pd.DataFrame(sheet_data)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        logger.info(f"Data exported to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        raise

def get_file_info(file: UploadFile) -> Dict[str, Any]:
    """Get information about uploaded file"""
    return {
        'filename': file.filename,
        'content_type': file.content_type,
        'size': file.size if hasattr(file, 'size') else 'Unknown'
    }