from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from config import settings
from database.model import Base
import logging

logger = logging.getLogger(__name__)

# Create engine
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG
    )
else:
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create default admin user if not exists
        with SessionLocal() as db:
            from database.model import User
            from utils.auth import get_password_hash
            
            admin_user = db.query(User).filter(User.email == "admin@timetable.com").first()
            if not admin_user:
                admin_user = User(
                    email="admin@timetable.com",
                    hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                    user_type="admin",
                    employee_id="ADMIN001",
                    full_name="System Administrator",
                    department="IT"
                )
                db.add(admin_user)
                db.commit()
                logger.info("Default admin user created")
                
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session() -> Session:
    """Get database session for internal use"""
    return SessionLocal()