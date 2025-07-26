from sqlalchemy import Column, Integer, String, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # User information fields
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # User type field - "I am a" field from signup
    user_type = Column(String(50), nullable=False, default='healthcare')
    # Options: 'healthcare', 'researcher', 'student', 'other'
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    def __init__(self, first_name, last_name, email, password, user_type='healthcare'):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.set_password(password)
        self.user_type = user_type
    
    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches the hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self):
        """Convert user object to dictionary (excluding password)"""
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'user_type': self.user_type,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'full_name': self.get_full_name()
        }
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', name='{self.get_full_name()}')>"


# Database configuration for Neon PostgreSQL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_database_url():
    """Get database URL from environment variables"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        # Try to construct from individual components if DATABASE_URL is not set
        db_host = os.getenv('DB_HOST')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_port = os.getenv('DB_PORT', '5432')
        
        if all([db_host, db_name, db_user, db_password]):
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
        else:
            raise ValueError("DATABASE_URL environment variable is not set and individual DB components are missing")
    
    # Ensure the URL has SSL mode for Neon
    if 'sslmode=' not in database_url and 'neon.tech' in database_url:
        separator = '&' if '?' in database_url else '?'
        database_url += f"{separator}sslmode=require"
    
    return database_url

def create_database_engine():
    """Create database engine for Neon PostgreSQL"""
    try:
        database_url = get_database_url()
        
        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            pool_size=5,  # Reduced for better resource management
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={
                "sslmode": "require",
                "connect_timeout": 10
            },
            echo=False  # Set to True for SQL debugging
        )
        
        return engine
    except Exception as e:
        print(f"Failed to create database engine: {e}")
        raise

def get_session():
    """Get database session"""
    try:
        engine = create_database_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()
    except Exception as e:
        print(f"Failed to create database session: {e}")
        raise

def test_connection():
    """Test database connection"""
    try:
        engine = create_database_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

def create_tables():
    """Create all tables in the database"""
    try:
        engine = create_database_engine()
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Failed to create tables: {e}")
        raise

def drop_tables():
    """Drop all tables in the database"""
    engine = create_database_engine()
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped successfully!")

# User operations
class UserOperations:
    """Class for user database operations"""
    
    @staticmethod
    def create_user(first_name, last_name, email, password, user_type='healthcare'):
        """Create a new user"""
        session = get_session()
        try:
            # Check if user already exists
            existing_user = session.query(User).filter(User.email == email).first()
            if existing_user:
                raise ValueError("User with this email already exists")
            
            # Create new user
            new_user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                user_type=user_type
            )
            
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            
            return new_user
        
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def get_user_by_email(email):
        """Get user by email"""
        session = get_session()
        try:
            user = session.query(User).filter(User.email == email).first()
            if user:
                # Detach the user from the session to avoid issues
                session.expunge(user)
            return user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                # Detach the user from the session to avoid issues
                session.expunge(user)
            return user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def authenticate_user(email, password):
        """Authenticate user with email and password"""
        session = get_session()
        try:
            # Get user from database
            user = session.query(User).filter(User.email == email).first()
            
            if user and user.check_password(password) and user.is_active:
                # Update last login in the same session
                user.last_login = func.now()
                session.commit()
                session.refresh(user)
                return user
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def update_user(user_id, **kwargs):
        """Update user information"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Update allowed fields
            allowed_fields = ['first_name', 'last_name', 'user_type', 'is_active', 'is_verified']
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(user, field, value)
            
            session.commit()
            session.refresh(user)
            return user
        
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """Change user password"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            if not user.check_password(old_password):
                raise ValueError("Invalid old password")
            
            user.set_password(new_password)
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def delete_user(user_id):
        """Delete user (soft delete by setting is_active to False)"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            user.is_active = False
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


# Initialize database (run this once to create tables)
if __name__ == "__main__":
    try:
        create_tables()
        print("User model initialized successfully!")
        
        # Example usage
        # user = UserOperations.create_user(
        #     first_name="John",
        #     last_name="Doe",
        #     email="john.doe@example.com",
        #     password="securepassword123",
        #     user_type="healthcare"
        # )
        # print(f"Created user: {user.to_dict()}")
        
    except Exception as e:
        print(f"Error initializing database: {e}")