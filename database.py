"""SQLAlchemy models and session factory."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from config import get_settings

_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_pw = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    profiles = relationship("FinancialProfile", back_populates="user", cascade="all, delete")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete")
    simulations = relationship("SimulationRun", back_populates="user", cascade="all, delete")


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    income = Column(Float, default=0)
    other_income = Column(Float, default=0)
    savings = Column(Float, default=0)
    min_balance = Column(Float, default=_settings.default_min_balance)
    rent = Column(Float, default=0)
    utilities = Column(Float, default=0)
    insurance = Column(Float, default=0)
    subscriptions = Column(Float, default=0)
    food = Column(Float, default=0)
    transport = Column(Float, default=0)
    dining = Column(Float, default=0)
    shopping = Column(Float, default=0)
    misc = Column(Float, default=0)
    emis = Column(JSON, default=list)
    horizon_months = Column(Integer, default=_settings.default_horizon_months)
    safety_target = Column(Float, default=_settings.safety_target_months)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="profiles")


class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    scenario_type = Column(String, nullable=False)
    params = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="scenarios")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_snapshot = Column(JSON)
    scenario_ids = Column(JSON)
    result = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="simulations")


Base.metadata.create_all(bind=engine)
